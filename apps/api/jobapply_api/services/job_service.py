"""Job discovery, persistence, matching and preferences.

Discovery writes jobs once, globally: two users watching the same board share the
stored posting. Matches are per user, so nothing about one user's profile is visible
in another's results.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime
from typing import Any

from jobapply_db.models import (
    Application,
    Company,
    Education,
    Job,
    JobMatch,
    JobPreference,
)
from jobapply_db.models import (
    JobSource as JobSourceModel,
)
from jobapply_jobs.dedupe import ExistingJob
from jobapply_jobs.discovery import JobDiscoveryService
from jobapply_jobs.matching import JobMatchingService
from jobapply_jobs.models import JobQuery, MatchProfile, MatchResult, MatchWeights, NormalizedJob
from jobapply_jobs.sources import build_source
from jobapply_shared.enums import EmploymentType, JobStatus, RemoteType
from jobapply_shared.errors import NotFoundError, ValidationError_
from jobapply_shared.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobapply_api.schemas.job import JobPreferenceUpdate, JobSearchRequest
from jobapply_api.services import audit
from jobapply_api.services.profile_service import ProfileService

logger = get_logger(__name__)

#: Sources present on a fresh database. Only the offline sample source is enabled by
#: default: reaching out to a third party is an explicit choice, not a default.
DEFAULT_SOURCES = (
    {
        "slug": "sample",
        "name": "Sample postings (local fixture data)",
        "kind": "feed",
        "enabled": True,
        "config": {},
    },
    {
        "slug": "greenhouse",
        "name": "Greenhouse job boards",
        "kind": "career_page",
        "base_url": "https://boards-api.greenhouse.io",
        "enabled": False,
        "config": {"board_tokens": []},
    },
    {
        "slug": "lever",
        "name": "Lever job boards",
        "kind": "career_page",
        "base_url": "https://api.lever.co",
        "enabled": False,
        "config": {"companies": []},
    },
)


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.matcher = JobMatchingService()

    # ------------------------------------------------------------------- sources
    def ensure_default_sources(self) -> list[JobSourceModel]:
        existing = {
            row.slug: row for row in self.db.execute(select(JobSourceModel)).scalars().all()
        }
        for spec in DEFAULT_SOURCES:
            if spec["slug"] not in existing:
                source = JobSourceModel(**spec)
                self.db.add(source)
                existing[spec["slug"]] = source
        self.db.flush()
        return list(existing.values())

    def list_sources(self) -> list[JobSourceModel]:
        return list(
            self.db.execute(select(JobSourceModel).order_by(JobSourceModel.slug)).scalars().all()
        )

    # ----------------------------------------------------------------- discovery
    def discover(self, user_id: uuid.UUID, request: JobSearchRequest) -> dict[str, Any]:
        sources = self.ensure_default_sources()
        selected = [
            source
            for source in sources
            if source.enabled and (not request.sources or source.slug in request.sources)
        ]
        if not selected:
            raise ValidationError_(
                "No job sources are enabled. Enable one in settings before searching.",
                code="no_sources_enabled",
            )

        preference = self.get_preference(user_id)
        query = JobQuery(
            keywords=request.keywords or list(preference.keywords or []),
            titles=request.titles or list(preference.target_titles or []),
            locations=request.locations or list(preference.locations or []),
            remote_only=request.remote_only,
            limit=request.limit,
        )

        adapters = [build_source(source.slug, source.config or {}) for source in selected]
        service = JobDiscoveryService(adapters)
        report = asyncio.run(service.discover(query, self._existing_jobs()))

        created = 0
        created_jobs: list[Job] = []
        for normalized in report.jobs:
            job = self._persist(normalized)
            if job is not None:
                created += 1
                created_jobs.append(job)

        now = datetime.now(tz=UTC)
        for source in selected:
            source.last_run_at = now
            source.last_error = "; ".join(report.errors)[:1000] or None

        scored = 0
        if request.score_after_discovery and created_jobs:
            profile = self.build_match_profile(user_id)
            for job in created_jobs:
                self._score_and_store(user_id, job, profile)
                scored += 1

        audit.record(
            self.db,
            action="jobs.discovery_run",
            actor_user_id=user_id,
            entity_type="job_source",
            data={
                "sources": [source.slug for source in selected],
                "fetched": report.fetched,
                "created": created,
                "duplicates": report.duplicates,
            },
        )
        return {
            "fetched": report.fetched,
            "created": created,
            "duplicates": report.duplicates + (report.normalized - created),
            "scored": scored,
            "errors": report.errors,
        }

    def _existing_jobs(self) -> list[ExistingJob]:
        rows = self.db.execute(
            select(
                Job.id,
                Job.normalized_company,
                Job.normalized_title,
                Job.normalized_location,
                Job.dedupe_key,
                Job.content_hash,
            ).where(Job.deleted_at.is_(None))
        ).all()
        return [
            ExistingJob(
                id=str(row.id),
                normalized_company=row.normalized_company,
                normalized_title=row.normalized_title,
                normalized_location=row.normalized_location,
                dedupe_key=row.dedupe_key,
                content_hash=row.content_hash,
            )
            for row in rows
        ]

    def _persist(self, normalized: NormalizedJob) -> Job | None:
        """Insert a normalized job, or return ``None`` if it is already stored.

        The uniqueness check is repeated here even though discovery already
        de-duplicated: two concurrent runs can both believe a job is new, and the
        database constraint is the real guarantee.
        """
        existing = self.db.execute(
            select(Job).where(Job.dedupe_key == normalized.dedupe_key)
        ).scalar_one_or_none()
        if existing is not None:
            return None

        source = self.db.execute(
            select(JobSourceModel).where(JobSourceModel.slug == normalized.source_slug)
        ).scalar_one_or_none()

        company = self.db.execute(
            select(Company).where(Company.normalized_name == normalized.normalized_company)
        ).scalar_one_or_none()
        if company is None:
            company = Company(
                name=normalized.company_name, normalized_name=normalized.normalized_company
            )
            self.db.add(company)
            self.db.flush()

        job = Job(
            source_id=source.id if source else None,
            source_job_id=normalized.source_job_id,
            company_id=company.id,
            company_name=normalized.company_name,
            normalized_company=normalized.normalized_company,
            title=normalized.title,
            normalized_title=normalized.normalized_title,
            location=normalized.location,
            normalized_location=normalized.normalized_location,
            remote_type=str(normalized.remote_type),
            employment_type=str(normalized.employment_type),
            salary_min=normalized.salary_min,
            salary_max=normalized.salary_max,
            salary_currency=normalized.salary_currency,
            salary_period=normalized.salary_period,
            description=normalized.description,
            requirements=normalized.requirements,
            preferred_qualifications=normalized.preferred_qualifications,
            skills=normalized.skills,
            education=normalized.education,
            experience_required_years=normalized.experience_required_years,
            seniority=normalized.seniority,
            sponsorship_information=normalized.sponsorship_information,
            sponsorship_offered=normalized.sponsorship_offered,
            apply_url=normalized.apply_url,
            posting_url=normalized.posting_url,
            detected_ats=normalized.detected_ats,
            status=str(JobStatus.DISCOVERED),
            discovered_at=datetime.now(tz=UTC),
            posted_at=normalized.posted_at,
            dedupe_key=normalized.dedupe_key,
            content_hash=normalized.content_hash,
            raw=normalized.raw,
        )
        self.db.add(job)
        self.db.flush()
        return job

    # ------------------------------------------------------------------ matching
    def build_match_profile(self, user_id: uuid.UUID) -> MatchProfile:
        profile_service = ProfileService(self.db)
        profile = profile_service.get(user_id)
        skills = profile_service.list_skills(user_id)
        preference = self.get_preference(user_id)

        education = (
            self.db.execute(
                select(Education)
                .where(Education.user_id == user_id, Education.deleted_at.is_(None))
                .order_by(Education.end_date.desc().nullslast())
            )
            .scalars()
            .first()
        )

        remote_preference = preference.remote_preference or profile.remote_preference
        return MatchProfile(
            titles=list(preference.target_titles or profile.desired_titles or []),
            current_title=profile.current_title,
            years_experience=float(profile.years_experience)
            if profile.years_experience is not None
            else None,
            skills=[skill.name for skill in skills],
            skill_years={
                skill.normalized_name: float(skill.years_experience)
                for skill in skills
                if skill.years_experience is not None
            },
            education_level=education.degree if education else None,
            locations=list(preference.locations or profile.desired_locations or []),
            remote_preference=RemoteType(remote_preference) if remote_preference else None,
            salary_min=preference.salary_min or profile.salary_min,
            open_to_relocation=profile.open_to_relocation,
            requires_sponsorship_now=profile.requires_sponsorship_now,
            requires_sponsorship_future=profile.requires_sponsorship_future,
            authorization_country=profile.authorization_country,
            excluded_companies=list(preference.excluded_companies or []),
            excluded_titles=list(preference.excluded_titles or []),
            excluded_keywords=list(preference.excluded_keywords or []),
            employment_types=[
                EmploymentType(value) for value in (preference.employment_types or [])
            ],
        )

    def _to_normalized(self, job: Job) -> NormalizedJob:
        """Rebuild the matching input from a stored row."""
        return NormalizedJob(
            source_slug=job.source.slug if job.source else "unknown",
            source_job_id=job.source_job_id or str(job.id),
            company_name=job.company_name,
            normalized_company=job.normalized_company,
            title=job.title,
            normalized_title=job.normalized_title,
            location=job.location,
            normalized_location=job.normalized_location,
            remote_type=RemoteType(job.remote_type),
            employment_type=EmploymentType(job.employment_type),
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            description=job.description,
            requirements=list(job.requirements or []),
            preferred_qualifications=list(job.preferred_qualifications or []),
            skills=list(job.skills or []),
            education=job.education,
            experience_required_years=float(job.experience_required_years)
            if job.experience_required_years is not None
            else None,
            seniority=job.seniority,
            sponsorship_information=job.sponsorship_information,
            sponsorship_offered=job.sponsorship_offered,
            apply_url=job.apply_url,
            posting_url=job.posting_url,
            detected_ats=job.detected_ats,
            posted_at=job.posted_at,
            expiration_date=job.expiration_date,
            dedupe_key=job.dedupe_key,
            content_hash=job.content_hash,
        )

    def _score_and_store(
        self, user_id: uuid.UUID, job: Job, profile: MatchProfile
    ) -> tuple[JobMatch, MatchResult]:
        preference = self.get_preference(user_id)
        weights = (
            MatchWeights(**preference.match_weights) if preference.match_weights else MatchWeights()
        )
        result = self.matcher.score(profile, self._to_normalized(job), weights)

        match = self.db.execute(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id)
        ).scalar_one_or_none()
        if match is None:
            match = JobMatch(user_id=user_id, job_id=job.id)
            self.db.add(match)

        match.overall_score = result.score
        match.skills_score = result.skills_score
        match.experience_score = result.experience_score
        match.education_score = result.education_score
        match.location_score = result.location_score
        match.authorization_score = result.authorization_score
        match.title_score = result.title_score
        match.seniority_score = result.seniority_score
        match.recommendation = str(result.recommendation)
        match.matched_skills = result.matched_skills
        match.missing_skills = result.missing_skills
        match.risks = result.risks
        match.hard_requirement_failed = result.hard_requirement_failed
        match.explanation = result.explanation
        match.weights = result.weights

        if job.status == str(JobStatus.DISCOVERED):
            job.status = str(JobStatus.MATCHED)
        self.db.flush()
        return match, result

    def score_job(self, user_id: uuid.UUID, job_id: uuid.UUID) -> JobMatch:
        job = self.get_job(job_id)
        match, _ = self._score_and_store(user_id, job, self.build_match_profile(user_id))
        return match

    def rescore_all(self, user_id: uuid.UUID) -> int:
        profile = self.build_match_profile(user_id)
        jobs = self.db.execute(select(Job).where(Job.deleted_at.is_(None))).scalars().all()
        for job in jobs:
            self._score_and_store(user_id, job, profile)
        return len(jobs)

    # --------------------------------------------------------------------- reads
    def get_job(self, job_id: uuid.UUID) -> Job:
        job = self.db.execute(
            select(Job).where(Job.id == job_id, Job.deleted_at.is_(None))
        ).scalar_one_or_none()
        if job is None:
            raise NotFoundError("Job not found.", code="job_not_found")
        return job

    def list_jobs(
        self,
        user_id: uuid.UUID,
        *,
        min_score: int | None = None,
        recommendation: str | None = None,
        company: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[tuple[Job, JobMatch | None, str | None]], int]:
        conditions = [Job.deleted_at.is_(None)]
        if company:
            conditions.append(Job.company_name.ilike(f"%{company}%"))

        statement = (
            select(Job, JobMatch, Application.status)
            .outerjoin(JobMatch, (JobMatch.job_id == Job.id) & (JobMatch.user_id == user_id))
            .outerjoin(
                Application,
                (Application.job_id == Job.id)
                & (Application.user_id == user_id)
                & (Application.deleted_at.is_(None)),
            )
            .where(*conditions)
        )
        if min_score is not None:
            statement = statement.where(JobMatch.overall_score >= min_score)
        if recommendation:
            statement = statement.where(JobMatch.recommendation == recommendation)

        total = self.db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()

        rows = self.db.execute(
            statement.order_by(JobMatch.overall_score.desc().nullslast(), Job.discovered_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows], int(total)

    def get_job_with_match(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> tuple[Job, JobMatch | None, str | None]:
        job = self.get_job(job_id)
        match = self.db.execute(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
        ).scalar_one_or_none()
        application_status = self.db.execute(
            select(Application.status).where(
                Application.user_id == user_id,
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        return job, match, application_status

    def set_decision(self, user_id: uuid.UUID, job_id: uuid.UUID, decision: str) -> JobMatch:
        job = self.get_job(job_id)
        match = self.db.execute(
            select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job_id)
        ).scalar_one_or_none()
        if match is None:
            match, _ = self._score_and_store(user_id, job, self.build_match_profile(user_id))

        if decision == "approve" and match.hard_requirement_failed:
            # The user may still apply manually, but the platform will not mark a job
            # approved for automation when a hard requirement fails.
            raise ValidationError_(
                "This job fails a hard requirement or one of your exclusions, so it "
                "cannot be approved for automated application.",
                code="hard_requirement_failed",
                details={"risks": list(match.risks or [])},
            )

        match.user_decision = decision
        audit.record(
            self.db,
            action=f"jobs.{decision}",
            actor_user_id=user_id,
            entity_type="job",
            entity_id=job_id,
        )
        return match

    def expire_stale_jobs(self, today: date | None = None) -> int:
        cutoff = today or date.today()
        jobs = (
            self.db.execute(
                select(Job).where(
                    Job.deleted_at.is_(None),
                    Job.expiration_date.is_not(None),
                    Job.expiration_date < cutoff,
                    Job.status != str(JobStatus.EXPIRED),
                )
            )
            .scalars()
            .all()
        )
        for job in jobs:
            job.status = str(JobStatus.EXPIRED)
        return len(jobs)

    # --------------------------------------------------------------- preferences
    def get_preference(self, user_id: uuid.UUID) -> JobPreference:
        preference = (
            self.db.execute(
                select(JobPreference).where(
                    JobPreference.user_id == user_id, JobPreference.is_active.is_(True)
                )
            )
            .scalars()
            .first()
        )
        if preference is None:
            preference = JobPreference(user_id=user_id, name="Default")
            self.db.add(preference)
            self.db.flush()
        return preference

    def update_preference(self, user_id: uuid.UUID, data: JobPreferenceUpdate) -> JobPreference:
        preference = self.get_preference(user_id)
        payload = data.model_dump(exclude_unset=True)
        weights = payload.pop("match_weights", None)
        for key, value in payload.items():
            if isinstance(value, list):
                value = [str(item) for item in value]
            elif hasattr(value, "value"):
                value = str(value)
            setattr(preference, key, value)
        if weights is not None:
            preference.match_weights = weights
        audit.record(
            self.db,
            action="jobs.preferences_updated",
            actor_user_id=user_id,
            entity_type="job_preference",
            entity_id=preference.id,
            data={"fields": sorted(payload)},
        )
        return preference
