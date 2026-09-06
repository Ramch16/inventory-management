"""Master resume storage, parsing and import into the profile.

Two invariants:

* the uploaded file is stored byte-for-byte and never modified;
* parsed data is a *suggestion* until the user imports it, and importing never sets
  work-authorization fields.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from jobapply_db.models import Certification, Education, Experience, Resume, ResumeVersion, Skill
from jobapply_resume.extract import extract_text
from jobapply_resume.models import ParsedResume
from jobapply_resume.parser import parse_resume
from jobapply_shared.enums import ResumeSourceKind, SkillCategory
from jobapply_shared.errors import NotFoundError, ValidationError_
from jobapply_shared.logging import get_logger
from jobapply_shared.storage import ObjectStorage, build_key
from jobapply_shared.text import normalize_text
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobapply_api.schemas.resume import ResumeImportRequest, ResumeTextCreate
from jobapply_api.services import audit
from jobapply_api.services.profile_service import ProfileService

logger = get_logger(__name__)

KIND_TO_SOURCE = {
    "pdf": ResumeSourceKind.UPLOAD_PDF,
    "docx": ResumeSourceKind.UPLOAD_DOCX,
    "txt": ResumeSourceKind.PASTED_TEXT,
}


class ResumeService:
    def __init__(self, db: Session, storage: ObjectStorage, max_bytes: int) -> None:
        self.db = db
        self.storage = storage
        self.max_bytes = max_bytes

    # ------------------------------------------------------------------ upload
    def upload(
        self, user_id: uuid.UUID, *, data: bytes, filename: str, content_type: str | None
    ) -> Resume:
        if len(data) > self.max_bytes:
            raise ValidationError_(
                f"The file is larger than the {self.max_bytes // (1024 * 1024)} MB limit.",
                code="file_too_large",
            )
        text, kind = extract_text(data, filename=filename, content_type=content_type)

        key = build_key("resumes", str(user_id), filename=filename or f"resume.{kind}")
        stored = self.storage.put(key, data, content_type)

        resume = Resume(
            user_id=user_id,
            title=(filename or "Resume").rsplit(".", 1)[0][:200],
            source_kind=str(KIND_TO_SOURCE[kind]),
            original_filename=filename,
            original_content_type=stored.content_type,
            original_size_bytes=stored.size,
            original_storage_key=stored.key,
            original_checksum=hashlib.sha256(data).hexdigest(),
            raw_text=text,
        )
        self.db.add(resume)
        self.db.flush()
        self._parse_into(resume, text)
        self._ensure_master(user_id, resume)
        audit.record(
            self.db,
            action="resume.uploaded",
            actor_user_id=user_id,
            entity_type="resume",
            entity_id=resume.id,
            data={"filename": filename, "kind": kind, "size": stored.size},
        )
        return resume

    def create_from_text(self, user_id: uuid.UUID, data: ResumeTextCreate) -> Resume:
        resume = Resume(
            user_id=user_id,
            title=data.title,
            source_kind=str(ResumeSourceKind.PASTED_TEXT),
            raw_text=data.content,
            original_size_bytes=len(data.content.encode("utf-8")),
            original_checksum=hashlib.sha256(data.content.encode("utf-8")).hexdigest(),
        )
        self.db.add(resume)
        self.db.flush()
        self._parse_into(resume, data.content)
        if data.set_as_master:
            self._ensure_master(user_id, resume, force=True)
        else:
            self._ensure_master(user_id, resume)
        audit.record(
            self.db,
            action="resume.created_from_text",
            actor_user_id=user_id,
            entity_type="resume",
            entity_id=resume.id,
        )
        return resume

    def _parse_into(self, resume: Resume, text: str) -> ParsedResume:
        try:
            parsed = parse_resume(text)
            resume.structured = parsed.model_dump(mode="json", exclude={"raw_text"})
            resume.parse_status = "parsed"
            resume.parse_error = None
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("resume.parse_failed")
            resume.parse_status = "failed"
            resume.parse_error = str(exc)[:1000]
            parsed = ParsedResume(raw_text=text)
        resume.parsed_at = datetime.now(tz=UTC)
        return parsed

    def _ensure_master(self, user_id: uuid.UUID, resume: Resume, *, force: bool = False) -> None:
        existing = (
            self.db.execute(
                select(Resume).where(
                    Resume.user_id == user_id,
                    Resume.is_master.is_(True),
                    Resume.deleted_at.is_(None),
                    Resume.id != resume.id,
                )
            )
            .scalars()
            .all()
        )
        if force:
            for other in existing:
                other.is_master = False
            resume.is_master = True
        elif not existing:
            resume.is_master = True

    # -------------------------------------------------------------------- read
    def list(self, user_id: uuid.UUID) -> list[Resume]:
        return list(
            self.db.execute(
                select(Resume)
                .where(Resume.user_id == user_id, Resume.deleted_at.is_(None))
                .order_by(Resume.is_master.desc(), Resume.created_at.desc())
            )
            .scalars()
            .all()
        )

    def get(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        resume = self.db.execute(
            select(Resume).where(
                Resume.id == resume_id, Resume.user_id == user_id, Resume.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
        if resume is None:
            raise NotFoundError("Resume not found.", code="resume_not_found")
        return resume

    def get_master(self, user_id: uuid.UUID) -> Resume | None:
        return self.db.execute(
            select(Resume).where(
                Resume.user_id == user_id,
                Resume.is_master.is_(True),
                Resume.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def rename(self, user_id: uuid.UUID, resume_id: uuid.UUID, title: str) -> Resume:
        resume = self.get(user_id, resume_id)
        resume.title = title
        return resume

    def set_master(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        resume = self.get(user_id, resume_id)
        self._ensure_master(user_id, resume, force=True)
        audit.record(
            self.db,
            action="resume.master_changed",
            actor_user_id=user_id,
            entity_type="resume",
            entity_id=resume.id,
        )
        return resume

    def delete(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        resume = self.get(user_id, resume_id)
        resume.deleted_at = datetime.now(tz=UTC)
        resume.is_master = False
        audit.record(
            self.db,
            action="resume.deleted",
            actor_user_id=user_id,
            entity_type="resume",
            entity_id=resume.id,
        )

    def download_url(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> tuple[str, int]:
        resume = self.get(user_id, resume_id)
        if not resume.original_storage_key:
            # The resume exists; it simply has no stored file. That is a state of the
            # resource, not a lookup failure, so it is reported as a 422 with a
            # specific code rather than a 404.
            raise ValidationError_(
                "This resume has no stored file — it was created from pasted text.",
                code="no_original_file",
            )
        expires_in = 900
        return self.storage.presign(resume.original_storage_key, expires_in), expires_in

    def list_versions(self, user_id: uuid.UUID, resume_id: uuid.UUID) -> list[ResumeVersion]:
        self.get(user_id, resume_id)
        return list(
            self.db.execute(
                select(ResumeVersion)
                .where(
                    ResumeVersion.resume_id == resume_id,
                    ResumeVersion.user_id == user_id,
                    ResumeVersion.deleted_at.is_(None),
                )
                .order_by(ResumeVersion.created_at.desc())
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------ import
    def import_into_profile(
        self, user_id: uuid.UUID, resume_id: uuid.UUID, options: ResumeImportRequest
    ) -> dict[str, Any]:
        """Copy parsed records into the profile so they become approved sources.

        Imported skills are marked unverified so the user confirms them in onboarding,
        and no work-authorization field is ever written here.
        """
        resume = self.get(user_id, resume_id)
        structured: dict[str, Any] = resume.structured or {}
        if not structured:
            raise ValidationError_(
                "This resume has not been parsed successfully.", code="resume_not_parsed"
            )

        profile_service = ProfileService(self.db)
        result: dict[str, Any] = {
            "experience_added": 0,
            "education_added": 0,
            "skills_added": 0,
            "certifications_added": 0,
            "profile_updated": False,
            "notes": [],
        }

        contact = structured.get("contact") or {}
        if options.import_contact or options.import_summary:
            profile = profile_service.get(user_id)
            if options.import_contact:
                full_name = contact.get("full_name") or ""
                parts = full_name.split()
                if parts and not profile.first_name:
                    profile.first_name = parts[0]
                if len(parts) > 1 and not profile.last_name:
                    profile.last_name = " ".join(parts[1:])
                for field, value in (
                    ("phone", contact.get("phone")),
                    ("linkedin_url", contact.get("linkedin_url")),
                    ("github_url", contact.get("github_url")),
                    ("portfolio_url", contact.get("portfolio_url")),
                ):
                    if value and not getattr(profile, field):
                        setattr(profile, field, value)
                result["profile_updated"] = True
            if options.import_summary and structured.get("summary") and not profile.summary:
                profile.summary = structured["summary"][:4000]
                result["profile_updated"] = True

        existing_experience = {
            (normalize_text(item.company), normalize_text(item.title))
            for item in profile_service.list_experience(user_id)
        }
        if options.import_experience:
            for index, position in enumerate(structured.get("positions") or []):
                company = (position.get("company") or "").strip()
                title = (position.get("title") or "").strip()
                if not company or not title:
                    continue
                if (normalize_text(company), normalize_text(title)) in existing_experience:
                    continue
                self.db.add(
                    Experience(
                        user_id=user_id,
                        company=company[:255],
                        title=title[:255],
                        location=(position.get("location") or None),
                        start_date=_as_date(position.get("start_date")),
                        end_date=_as_date(position.get("end_date")),
                        is_current=bool(position.get("is_current")),
                        accomplishments=[
                            bullet for bullet in position.get("bullets") or [] if bullet
                        ],
                        sort_order=index,
                    )
                )
                result["experience_added"] += 1

        if options.import_education:
            existing_education = {
                normalize_text(item.institution) for item in profile_service.list_education(user_id)
            }
            for index, record in enumerate(structured.get("education") or []):
                institution = (record.get("institution") or "").strip()
                if not institution or normalize_text(institution) in existing_education:
                    continue
                self.db.add(
                    Education(
                        user_id=user_id,
                        institution=institution[:255],
                        degree=record.get("degree"),
                        field_of_study=record.get("field_of_study"),
                        end_date=_as_date(record.get("end_date")),
                        gpa=record.get("gpa"),
                        sort_order=index,
                    )
                )
                result["education_added"] += 1

        if options.import_skills:
            existing_skills = {
                item.normalized_name for item in profile_service.list_skills(user_id)
            }
            for name in structured.get("skills") or []:
                normalized = normalize_text(name)
                if not normalized or normalized in existing_skills:
                    continue
                existing_skills.add(normalized)
                self.db.add(
                    Skill(
                        user_id=user_id,
                        name=name[:120],
                        normalized_name=normalized,
                        category=str(SkillCategory.OTHER),
                        # Parsed from a document rather than confirmed by the user.
                        is_verified=False,
                    )
                )
                result["skills_added"] += 1
            if result["skills_added"]:
                result["notes"].append(
                    "Imported skills are marked unverified until you confirm them."
                )

        if options.import_certifications:
            existing_certifications = {
                normalize_text(item.name) for item in profile_service.list_certifications(user_id)
            }
            for record in structured.get("certifications") or []:
                name = (record.get("name") or "").strip()
                if not name or normalize_text(name) in existing_certifications:
                    continue
                self.db.add(
                    Certification(
                        user_id=user_id,
                        name=name[:255],
                        issuer=record.get("issuer"),
                        issued_on=_as_date(record.get("issued_on")),
                        is_verified=False,
                    )
                )
                result["certifications_added"] += 1

        result["notes"].append(
            "Work authorization is never imported from a resume — declare it explicitly "
            "in your profile."
        )
        audit.record(
            self.db,
            action="resume.imported_to_profile",
            actor_user_id=user_id,
            entity_type="resume",
            entity_id=resume.id,
            data={key: value for key, value in result.items() if key != "notes"},
        )
        return result


def _as_date(value: Any):
    if not value:
        return None
    if hasattr(value, "year"):
        return value
    from datetime import date

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
