"""Profile CRUD and readiness checks.

The completeness score is not cosmetic: automated submission is blocked until the
profile contains everything an application needs, including an explicit work
authorization declaration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date
from typing import Any, TypeVar

from jobapply_db.models import Certification, Education, Experience, Profile, Project, Skill
from jobapply_shared.errors import ConflictError, NotFoundError
from jobapply_shared.text import normalize_text
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobapply_api.schemas.profile import (
    CertificationCreate,
    EducationCreate,
    ExperienceCreate,
    ProfileUpdate,
    SkillCreate,
    WorkAuthorizationUpdate,
)
from jobapply_api.services import audit

T = TypeVar("T", Education, Experience, Skill, Certification, Project)

#: Fields that must be present before automated applications may run.
AUTOMATION_REQUIRED_FIELDS = (
    ("first_name", "First name"),
    ("last_name", "Last name"),
    ("email", "Contact e-mail"),
    ("phone", "Phone number"),
    ("city", "City"),
    ("country", "Country"),
)


class ProfileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------------------------------------------- profile
    def get(self, user_id: uuid.UUID) -> Profile:
        profile = self.db.execute(
            select(Profile).where(Profile.user_id == user_id)
        ).scalar_one_or_none()
        if profile is None:
            profile = Profile(user_id=user_id)
            self.db.add(profile)
            self.db.flush()
        return profile

    def update(self, user_id: uuid.UUID, data: ProfileUpdate) -> Profile:
        profile = self.get(user_id)
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            if isinstance(value, list):
                value = [str(item) for item in value]
            setattr(profile, key, value)
        audit.record(
            self.db,
            action="profile.updated",
            actor_user_id=user_id,
            entity_type="profile",
            entity_id=profile.id,
            data={"fields": sorted(payload)},
        )
        return profile

    def update_work_authorization(
        self, user_id: uuid.UUID, data: WorkAuthorizationUpdate
    ) -> Profile:
        """Set the legally significant fields. Only ever called from the dedicated
        endpoint, with the user's explicit confirmation."""
        profile = self.get(user_id)
        profile.authorization_country = data.authorization_country
        profile.authorization_type = str(data.authorization_type)
        profile.authorization_expires_on = data.authorization_expires_on
        profile.requires_sponsorship_now = data.requires_sponsorship_now
        profile.requires_sponsorship_future = data.requires_sponsorship_future
        profile.work_authorization_confirmed_at = date.today()
        audit.record(
            self.db,
            action="profile.work_authorization_declared",
            actor_user_id=user_id,
            entity_type="profile",
            entity_id=profile.id,
            data={
                "authorization_country": data.authorization_country,
                "authorization_type": str(data.authorization_type),
                "requires_sponsorship_now": data.requires_sponsorship_now,
                "requires_sponsorship_future": data.requires_sponsorship_future,
            },
        )
        return profile

    # ------------------------------------------------------------- collections
    def _list(self, model: type[T], user_id: uuid.UUID, order_by: Any) -> list[T]:
        return list(
            self.db.execute(
                select(model)
                .where(model.user_id == user_id, model.deleted_at.is_(None))
                .order_by(order_by)
            )
            .scalars()
            .all()
        )

    def _get_owned(self, model: type[T], user_id: uuid.UUID, record_id: uuid.UUID) -> T:
        record = self.db.execute(
            select(model).where(
                model.id == record_id, model.user_id == user_id, model.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
        if record is None:
            raise NotFoundError(f"{model.__name__} not found.", code="record_not_found")
        return record

    def _soft_delete(self, model: type[T], user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        from datetime import datetime

        record = self._get_owned(model, user_id, record_id)
        record.deleted_at = datetime.now(tz=UTC)

    # education
    def list_education(self, user_id: uuid.UUID) -> list[Education]:
        return self._list(Education, user_id, Education.sort_order)

    def add_education(self, user_id: uuid.UUID, data: EducationCreate) -> Education:
        record = Education(user_id=user_id, **data.model_dump())
        self.db.add(record)
        self.db.flush()
        return record

    def update_education(
        self, user_id: uuid.UUID, record_id: uuid.UUID, data: EducationCreate
    ) -> Education:
        record = self._get_owned(Education, user_id, record_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return record

    def delete_education(self, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        self._soft_delete(Education, user_id, record_id)

    # experience
    def list_experience(self, user_id: uuid.UUID) -> list[Experience]:
        return self._list(Experience, user_id, Experience.sort_order)

    def add_experience(self, user_id: uuid.UUID, data: ExperienceCreate) -> Experience:
        payload = data.model_dump()
        payload["employment_type"] = (
            str(payload["employment_type"]) if payload.get("employment_type") else None
        )
        record = Experience(user_id=user_id, **payload)
        self.db.add(record)
        self.db.flush()
        return record

    def update_experience(
        self, user_id: uuid.UUID, record_id: uuid.UUID, data: ExperienceCreate
    ) -> Experience:
        record = self._get_owned(Experience, user_id, record_id)
        payload = data.model_dump()
        payload["employment_type"] = (
            str(payload["employment_type"]) if payload.get("employment_type") else None
        )
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    def delete_experience(self, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        self._soft_delete(Experience, user_id, record_id)

    # skills
    def list_skills(self, user_id: uuid.UUID) -> list[Skill]:
        return self._list(Skill, user_id, Skill.name)

    def add_skill(self, user_id: uuid.UUID, data: SkillCreate) -> Skill:
        normalized = normalize_text(data.name)
        existing = self.db.execute(
            select(Skill).where(Skill.user_id == user_id, Skill.normalized_name == normalized)
        ).scalar_one_or_none()
        if existing is not None and existing.deleted_at is None:
            raise ConflictError(f"'{data.name}' is already in your skills.", code="skill_exists")
        if existing is not None:
            existing.deleted_at = None
            existing.name = data.name
            existing.category = str(data.category)
            existing.years_experience = data.years_experience
            existing.proficiency = data.proficiency
            existing.is_verified = data.is_verified
            existing.last_used_year = data.last_used_year
            return existing
        record = Skill(
            user_id=user_id,
            name=data.name,
            normalized_name=normalized,
            category=str(data.category),
            years_experience=data.years_experience,
            proficiency=data.proficiency,
            is_verified=data.is_verified,
            last_used_year=data.last_used_year,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def update_skill(self, user_id: uuid.UUID, record_id: uuid.UUID, data: SkillCreate) -> Skill:
        record = self._get_owned(Skill, user_id, record_id)
        record.name = data.name
        record.normalized_name = normalize_text(data.name)
        record.category = str(data.category)
        record.years_experience = data.years_experience
        record.proficiency = data.proficiency
        record.is_verified = data.is_verified
        record.last_used_year = data.last_used_year
        return record

    def delete_skill(self, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        self._soft_delete(Skill, user_id, record_id)

    # certifications
    def list_certifications(self, user_id: uuid.UUID) -> list[Certification]:
        return self._list(Certification, user_id, Certification.name)

    def add_certification(self, user_id: uuid.UUID, data: CertificationCreate) -> Certification:
        record = Certification(user_id=user_id, **data.model_dump())
        self.db.add(record)
        self.db.flush()
        return record

    def update_certification(
        self, user_id: uuid.UUID, record_id: uuid.UUID, data: CertificationCreate
    ) -> Certification:
        record = self._get_owned(Certification, user_id, record_id)
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        return record

    def delete_certification(self, user_id: uuid.UUID, record_id: uuid.UUID) -> None:
        self._soft_delete(Certification, user_id, record_id)

    def list_projects(self, user_id: uuid.UUID) -> list[Project]:
        return self._list(Project, user_id, Project.sort_order)

    # ------------------------------------------------------------ completeness
    def completeness(self, user_id: uuid.UUID) -> dict[str, Any]:
        profile = self.get(user_id)
        experiences = self.list_experience(user_id)
        education = self.list_education(user_id)
        skills = self.list_skills(user_id)

        missing: list[str] = []
        blockers: list[str] = []

        for field, label in AUTOMATION_REQUIRED_FIELDS:
            if not getattr(profile, field, None):
                missing.append(label)
                blockers.append(f"{label} is required before an application can be submitted.")

        if not profile.current_title:
            missing.append("Current title")
        if profile.years_experience is None:
            missing.append("Years of experience")
        if not experiences:
            missing.append("At least one work experience")
            blockers.append(
                "Add at least one position: tailoring may only use experience you have "
                "entered or approved."
            )
        if not education:
            missing.append("Education")
        if not skills:
            missing.append("Skills")
            blockers.append("Add your skills so job matching has something to compare.")
        if not profile.work_authorization_declared:
            missing.append("Work authorization")
            blockers.append(
                "Declare your work authorization explicitly. It is never inferred from your resume."
            )

        sections = {
            "identity": all(
                getattr(profile, field, None) for field, _ in AUTOMATION_REQUIRED_FIELDS
            ),
            "professional": bool(profile.current_title) and profile.years_experience is not None,
            "authorization": profile.work_authorization_declared,
            "experience": bool(experiences),
            "education": bool(education),
            "skills": bool(skills),
        }
        score = round(100 * sum(1 for value in sections.values() if value) / len(sections))

        return {
            "score": score,
            "missing": missing,
            "blocks_automation": blockers,
            "ready_for_automation": not blockers,
        }
