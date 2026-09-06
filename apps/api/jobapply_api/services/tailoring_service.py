"""Generate a tailored resume (and optional cover letter) for one job.

Every version is a new row and new stored objects: the master resume is never
rewritten. The truth report and the quality score are stored alongside, so a user can
see exactly what was generated, from which records, and how it scored — before it is
ever attached to an application.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from jobapply_db.models import AutomationSettings, ResumeVersion
from jobapply_resume.cover_letter import CoverLetterService, should_generate_cover_letter
from jobapply_resume.models import ContactInfo
from jobapply_resume.quality import score_resume
from jobapply_resume.renderers import DocxRenderer, PdfRenderer
from jobapply_resume.sources import build_source_records
from jobapply_resume.tailoring import ResumeTailoringService, TailoringInputs
from jobapply_resume.truth import ResumeTruthLayer, build_source_index
from jobapply_shared.enums import ResumeTemplate
from jobapply_shared.errors import ValidationError_
from jobapply_shared.logging import get_logger
from jobapply_shared.storage import ObjectStorage
from jobapply_shared.text import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobapply_api.services import audit
from jobapply_api.services.job_service import JobService
from jobapply_api.services.profile_service import ProfileService
from jobapply_api.services.resume_service import ResumeService

logger = get_logger(__name__)


def _row_to_dict(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(row, name, None) for name in fields}


class TailoringService:
    def __init__(
        self,
        db: Session,
        storage: ObjectStorage,
        provider: Any | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.provider = provider

    # ------------------------------------------------------------------ inputs
    def build_inputs(self, user_id: uuid.UUID) -> TailoringInputs:
        profile_service = ProfileService(self.db)
        profile = profile_service.get(user_id)
        experiences = [
            _row_to_dict(
                item,
                (
                    "id",
                    "company",
                    "title",
                    "location",
                    "start_date",
                    "end_date",
                    "is_current",
                    "description",
                    "accomplishments",
                    "technologies",
                    "skills",
                ),
            )
            for item in profile_service.list_experience(user_id)
        ]
        education = [
            _row_to_dict(
                item,
                (
                    "id",
                    "institution",
                    "degree",
                    "field_of_study",
                    "end_date",
                    "gpa",
                    "relevant_coursework",
                ),
            )
            for item in profile_service.list_education(user_id)
        ]
        skills = [
            _row_to_dict(item, ("id", "name", "years_experience"))
            for item in profile_service.list_skills(user_id)
        ]
        certifications = [
            _row_to_dict(item, ("id", "name", "issuer"))
            for item in profile_service.list_certifications(user_id)
        ]
        projects = [
            _row_to_dict(item, ("id", "name", "role", "description", "highlights", "technologies"))
            for item in profile_service.list_projects(user_id)
        ]
        profile_dict = _row_to_dict(
            profile,
            (
                "first_name",
                "last_name",
                "current_title",
                "summary",
                "city",
                "state",
                "country",
                "years_experience",
            ),
        )

        sources = build_source_records(
            profile=profile_dict,
            experiences=experiences,
            education=education,
            skills=skills,
            certifications=certifications,
            projects=projects,
        )

        return TailoringInputs(
            contact=ContactInfo(
                full_name=profile.full_name or None,
                email=profile.email,
                phone=profile.phone,
                location=", ".join(
                    part for part in (profile.city, profile.state, profile.country) if part
                )
                or None,
                linkedin_url=profile.linkedin_url,
                github_url=profile.github_url,
                portfolio_url=profile.portfolio_url,
            ),
            sources=sources,
            experiences=experiences,
            education=education,
            skills=[item["name"] for item in skills],
            certifications=[item["name"] for item in certifications],
            projects=projects,
            summary=profile.summary,
        )

    # ---------------------------------------------------------------- generate
    def generate(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        template: str | None = None,
        max_pages: int | None = None,
        include_cover_letter: bool | None = None,
    ) -> ResumeVersion:
        resume_service = ResumeService(self.db, self.storage, max_bytes=0)
        master = resume_service.get_master(user_id)
        if master is None:
            raise ValidationError_(
                "Upload a master resume before generating a tailored version.",
                code="no_master_resume",
            )

        inputs = self.build_inputs(user_id)
        if not inputs.experiences:
            raise ValidationError_(
                "Add at least one position to your profile: tailoring may only use "
                "experience you have entered or approved.",
                code="no_experience_records",
            )

        job = JobService(self.db).get_job(job_id)
        job_dict = _row_to_dict(
            job,
            (
                "title",
                "company_name",
                "skills",
                "requirements",
                "preferred_qualifications",
                "description",
                "seniority",
            ),
        )

        settings = self.db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user_id)
        ).scalar_one_or_none()
        chosen_template = template or (
            settings.default_resume_template if settings else str(ResumeTemplate.ATS_CLASSIC)
        )
        pages = max_pages or (settings.resume_max_pages if settings else 2)
        wants_letter = (
            include_cover_letter
            if include_cover_letter is not None
            else bool(settings and settings.generate_cover_letters)
        )

        outcome = asyncio.run(
            ResumeTailoringService(self.provider).tailor(
                inputs, job_dict, max_pages=pages, template=chosen_template
            )
        )
        document = outcome.document

        layer = ResumeTruthLayer(build_source_index(inputs.sources))
        truth = layer.verify_document(document)
        quality = score_resume(document, job_dict, truth)

        # --- render and store ------------------------------------------------
        slug = slugify(f"{job.company_name}-{job.title}") or "resume"
        base_key = f"resumes/{user_id}/tailored/{job_id}"
        docx_key = f"{base_key}/{slug}.docx"
        pdf_key = f"{base_key}/{slug}.pdf"
        self.storage.put(
            docx_key,
            DocxRenderer(chosen_template).render(document),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.storage.put(pdf_key, PdfRenderer(chosen_template).render(document), "application/pdf")

        # --- optional cover letter -------------------------------------------
        letter_text: str | None = None
        letter_key: str | None = None
        if wants_letter:
            decision = should_generate_cover_letter(
                user_enabled=True, employer_requires=None, job=job_dict
            )
            if decision.should_generate:
                letter = asyncio.run(
                    CoverLetterService(self.provider).generate(
                        sources=inputs.sources,
                        job=job_dict,
                        applicant_name=inputs.contact.full_name,
                    )
                )
                if letter is not None:
                    letter_text = letter.text
                    letter_key = f"{base_key}/{slug}-cover-letter.txt"
                    self.storage.put(letter_key, letter.text.encode("utf-8"), "text/plain")

        next_version = (
            self.db.execute(
                select(func.coalesce(func.max(ResumeVersion.version), 0)).where(
                    ResumeVersion.resume_id == master.id, ResumeVersion.job_id == job_id
                )
            ).scalar_one()
            + 1
        )

        version = ResumeVersion(
            user_id=user_id,
            resume_id=master.id,
            job_id=job_id,
            version=next_version,
            label=f"{job.company_name} — {job.title}",
            template=chosen_template,
            content=document.model_dump(mode="json"),
            provenance=[record.model_dump(mode="json") for record in document.provenance],
            quality=quality.model_dump(mode="json"),
            docx_storage_key=docx_key,
            pdf_storage_key=pdf_key,
            cover_letter_text=letter_text,
            cover_letter_storage_key=letter_key,
            ai_provider=outcome.ai_provider,
            ai_model=outcome.ai_model,
            truth_report={
                "allowed": truth.allowed,
                "reasons": truth.reasons,
                "rejected_statements": truth.rejected_statements,
                "rejected_by_generator": outcome.rejected,
                "used_ai": outcome.used_ai,
            },
        )
        self.db.add(version)
        self.db.flush()

        audit.record(
            self.db,
            action="resume.tailored",
            actor_user_id=user_id,
            entity_type="resume_version",
            entity_id=version.id,
            data={
                "job_id": str(job_id),
                "template": chosen_template,
                "used_ai": outcome.used_ai,
                "quality": quality.overall,
                "rejected": len(outcome.rejected),
            },
        )
        logger.info(
            "resume.tailored",
            extra={
                "context": {
                    "event": "resume.tailored",
                    "user_id": str(user_id),
                    "job_id": str(job_id),
                    "used_ai": outcome.used_ai,
                    "quality": quality.overall,
                    "truth_allowed": truth.allowed,
                }
            },
        )
        return version

    # -------------------------------------------------------------------- read
    def get_version(self, user_id: uuid.UUID, version_id: uuid.UUID) -> ResumeVersion:
        version = self.db.execute(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == user_id,
                ResumeVersion.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if version is None:
            from jobapply_shared.errors import NotFoundError

            raise NotFoundError("Tailored resume not found.", code="resume_version_not_found")
        return version

    def list_versions_for_job(self, user_id: uuid.UUID, job_id: uuid.UUID) -> list[ResumeVersion]:
        return list(
            self.db.execute(
                select(ResumeVersion)
                .where(
                    ResumeVersion.user_id == user_id,
                    ResumeVersion.job_id == job_id,
                    ResumeVersion.deleted_at.is_(None),
                )
                .order_by(ResumeVersion.version.desc())
            )
            .scalars()
            .all()
        )

    def latest_for_job(self, user_id: uuid.UUID, job_id: uuid.UUID) -> ResumeVersion | None:
        versions = self.list_versions_for_job(user_id, job_id)
        return versions[0] if versions else None
