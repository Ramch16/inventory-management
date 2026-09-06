"""Profile endpoints.

Work authorization has its own endpoint on purpose: it is legally significant, so it
is never updated as a side effect of a general profile save.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from jobapply_shared.errors import ValidationError_

from jobapply_api.deps import CurrentUser, ProfileServiceDep, SessionDep
from jobapply_api.schemas.profile import (
    CertificationCreate,
    CertificationResponse,
    EducationCreate,
    EducationResponse,
    ExperienceCreate,
    ExperienceResponse,
    OnboardingComplete,
    OnboardingStatus,
    ProfileCompleteness,
    ProfileResponse,
    ProfileUpdate,
    SkillCreate,
    SkillResponse,
    WorkAuthorizationResponse,
    WorkAuthorizationUpdate,
)
from jobapply_api.services import audit

router = APIRouter(prefix="/profile", tags=["profile"])


def _profile_response(profile) -> ProfileResponse:
    response = ProfileResponse.model_validate(profile)
    response.work_authorization = WorkAuthorizationResponse(
        authorization_country=profile.authorization_country,
        authorization_type=profile.authorization_type,
        authorization_expires_on=profile.authorization_expires_on,
        requires_sponsorship_now=profile.requires_sponsorship_now,
        requires_sponsorship_future=profile.requires_sponsorship_future,
        work_authorization_confirmed_at=profile.work_authorization_confirmed_at,
        declared=profile.work_authorization_declared,
    )
    return response


@router.get("", response_model=ProfileResponse)
def get_profile(user: CurrentUser, service: ProfileServiceDep, db: SessionDep) -> ProfileResponse:
    profile = service.get(user.id)
    db.commit()
    return _profile_response(profile)


@router.put("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> ProfileResponse:
    profile = service.update(user.id, payload)
    db.commit()
    db.refresh(profile)
    return _profile_response(profile)


@router.get("/work-authorization", response_model=WorkAuthorizationResponse)
def get_work_authorization(
    user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> WorkAuthorizationResponse:
    profile = service.get(user.id)
    db.commit()
    return _profile_response(profile).work_authorization


@router.put("/work-authorization", response_model=WorkAuthorizationResponse)
def update_work_authorization(
    payload: WorkAuthorizationUpdate,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> WorkAuthorizationResponse:
    profile = service.update_work_authorization(user.id, payload)
    db.commit()
    db.refresh(profile)
    return _profile_response(profile).work_authorization


@router.get("/onboarding", response_model=OnboardingStatus)
def onboarding_status(
    user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> OnboardingStatus:
    return OnboardingStatus(
        completed_at=user.onboarding_completed_at, **_onboarding_facts(db, user, service)
    )


@router.post("/onboarding/complete", response_model=OnboardingStatus)
def complete_onboarding(
    payload: OnboardingComplete,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> OnboardingStatus:
    """Record the user's confirmation that their profile is accurate."""
    facts = _onboarding_facts(db, user, service)
    if not facts["ready_for_automation"] or not facts["has_master_resume"]:
        raise ValidationError_(
            "Complete your profile and upload a master resume before finishing onboarding.",
            code="onboarding_incomplete",
            details={
                "missing": facts["missing"],
                "blocks_automation": facts["blocks_automation"],
                "has_master_resume": facts["has_master_resume"],
            },
        )

    _ = payload.confirmed  # validated above; recorded in the audit entry below
    user.onboarding_completed_at = datetime.now(tz=UTC)
    audit.record(
        db,
        action="profile.onboarding_completed",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return OnboardingStatus(completed_at=user.onboarding_completed_at, **facts)


def _onboarding_facts(db, user, service: ProfileServiceDep) -> dict:
    from jobapply_db.models import Resume
    from sqlalchemy import func, select

    completeness = service.completeness(user.id)
    has_master = (
        db.execute(
            select(func.count())
            .select_from(Resume)
            .where(
                Resume.user_id == user.id,
                Resume.is_master.is_(True),
                Resume.deleted_at.is_(None),
            )
        ).scalar_one()
        > 0
    )
    return {
        "ready_for_automation": completeness["ready_for_automation"],
        "missing": completeness["missing"],
        "blocks_automation": completeness["blocks_automation"],
        "has_master_resume": has_master,
    }


@router.get("/completeness", response_model=ProfileCompleteness)
def completeness(user: CurrentUser, service: ProfileServiceDep) -> ProfileCompleteness:
    return ProfileCompleteness(**service.completeness(user.id))


# ------------------------------------------------------------------------ education
@router.get("/education", response_model=list[EducationResponse])
def list_education(user: CurrentUser, service: ProfileServiceDep) -> list[EducationResponse]:
    return [EducationResponse.model_validate(item) for item in service.list_education(user.id)]


@router.post("/education", response_model=EducationResponse, status_code=status.HTTP_201_CREATED)
def add_education(
    payload: EducationCreate, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> EducationResponse:
    record = service.add_education(user.id, payload)
    db.commit()
    db.refresh(record)
    return EducationResponse.model_validate(record)


@router.put("/education/{record_id}", response_model=EducationResponse)
def update_education(
    record_id: uuid.UUID,
    payload: EducationCreate,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> EducationResponse:
    record = service.update_education(user.id, record_id, payload)
    db.commit()
    db.refresh(record)
    return EducationResponse.model_validate(record)


@router.delete("/education/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    record_id: uuid.UUID, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> None:
    service.delete_education(user.id, record_id)
    db.commit()


# ----------------------------------------------------------------------- experience
@router.get("/experience", response_model=list[ExperienceResponse])
def list_experience(user: CurrentUser, service: ProfileServiceDep) -> list[ExperienceResponse]:
    return [ExperienceResponse.model_validate(item) for item in service.list_experience(user.id)]


@router.post("/experience", response_model=ExperienceResponse, status_code=status.HTTP_201_CREATED)
def add_experience(
    payload: ExperienceCreate, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> ExperienceResponse:
    record = service.add_experience(user.id, payload)
    db.commit()
    db.refresh(record)
    return ExperienceResponse.model_validate(record)


@router.put("/experience/{record_id}", response_model=ExperienceResponse)
def update_experience(
    record_id: uuid.UUID,
    payload: ExperienceCreate,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> ExperienceResponse:
    record = service.update_experience(user.id, record_id, payload)
    db.commit()
    db.refresh(record)
    return ExperienceResponse.model_validate(record)


@router.delete("/experience/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    record_id: uuid.UUID, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> None:
    service.delete_experience(user.id, record_id)
    db.commit()


# --------------------------------------------------------------------------- skills
@router.get("/skills", response_model=list[SkillResponse])
def list_skills(user: CurrentUser, service: ProfileServiceDep) -> list[SkillResponse]:
    return [SkillResponse.model_validate(item) for item in service.list_skills(user.id)]


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def add_skill(
    payload: SkillCreate, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> SkillResponse:
    record = service.add_skill(user.id, payload)
    db.commit()
    db.refresh(record)
    return SkillResponse.model_validate(record)


@router.put("/skills/{record_id}", response_model=SkillResponse)
def update_skill(
    record_id: uuid.UUID,
    payload: SkillCreate,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> SkillResponse:
    record = service.update_skill(user.id, record_id, payload)
    db.commit()
    db.refresh(record)
    return SkillResponse.model_validate(record)


@router.delete("/skills/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    record_id: uuid.UUID, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> None:
    service.delete_skill(user.id, record_id)
    db.commit()


# ------------------------------------------------------------------- certifications
@router.get("/certifications", response_model=list[CertificationResponse])
def list_certifications(
    user: CurrentUser, service: ProfileServiceDep
) -> list[CertificationResponse]:
    return [
        CertificationResponse.model_validate(item) for item in service.list_certifications(user.id)
    ]


@router.post(
    "/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED
)
def add_certification(
    payload: CertificationCreate, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> CertificationResponse:
    record = service.add_certification(user.id, payload)
    db.commit()
    db.refresh(record)
    return CertificationResponse.model_validate(record)


@router.put("/certifications/{record_id}", response_model=CertificationResponse)
def update_certification(
    record_id: uuid.UUID,
    payload: CertificationCreate,
    user: CurrentUser,
    service: ProfileServiceDep,
    db: SessionDep,
) -> CertificationResponse:
    record = service.update_certification(user.id, record_id, payload)
    db.commit()
    db.refresh(record)
    return CertificationResponse.model_validate(record)


@router.delete("/certifications/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certification(
    record_id: uuid.UUID, user: CurrentUser, service: ProfileServiceDep, db: SessionDep
) -> None:
    service.delete_certification(user.id, record_id)
    db.commit()
