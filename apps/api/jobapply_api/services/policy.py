"""Pre-application policy checks.

Everything that must be true before an application may be created or submitted, in
one place, so the rules are auditable rather than scattered through the run.

A check either passes or produces a ``PolicyViolation`` with a stable code the UI can
explain. Nothing here is advisory: a violation stops the application.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from jobapply_db.models import Application, AutomationSettings, Job, JobMatch, JobPreference, User
from jobapply_jobs.dedupe import application_dedupe_hash
from jobapply_shared.enums import (
    SUBMITTED_APPLICATION_STATUSES,
    ApplicationStatus,
    EmploymentType,
    RemoteType,
)
from jobapply_shared.text import normalize_company, normalize_location
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PolicyViolation:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecision:
    allowed: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    dedupe_hash: str = ""
    #: Populated when the block is a rate limit, so the UI can say when to retry.
    retry_after_seconds: int | None = None

    @property
    def first(self) -> PolicyViolation | None:
        return self.violations[0] if self.violations else None


def build_dedupe_hash(job: Job) -> str:
    return application_dedupe_hash(
        company=job.company_name,
        title=job.title,
        employer_job_id=job.source_job_id,
        apply_url=job.apply_url,
    )


class ApplicationPolicy:
    """Every gate between "this job looks good" and "submit it"."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, user: User, job: Job, *, at: datetime | None = None) -> PolicyDecision:
        now = at or datetime.now(tz=UTC)
        violations: list[PolicyViolation] = []
        retry_after: int | None = None

        settings = self.db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user.id)
        ).scalar_one_or_none()
        preference = (
            self.db.execute(
                select(JobPreference).where(
                    JobPreference.user_id == user.id, JobPreference.is_active.is_(True)
                )
            )
            .scalars()
            .first()
        )
        match = self.db.execute(
            select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
        ).scalar_one_or_none()

        dedupe_hash = build_dedupe_hash(job)

        # -- duplicates -------------------------------------------------------
        existing = (
            self.db.execute(
                select(Application).where(
                    Application.user_id == user.id,
                    Application.dedupe_hash == dedupe_hash,
                    Application.deleted_at.is_(None),
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            violations.append(
                PolicyViolation(
                    "already_applied",
                    f"You already have an application for this role ({existing.status}).",
                    {"application_id": str(existing.id), "status": existing.status},
                )
            )

        # -- the posting ------------------------------------------------------
        if job.deleted_at is not None or job.status == "expired":
            violations.append(PolicyViolation("job_expired", "This posting is no longer open."))
        elif job.expiration_date and job.expiration_date < date.today():
            violations.append(PolicyViolation("job_expired", "This posting has expired."))
        if not job.apply_url:
            violations.append(
                PolicyViolation("no_apply_url", "This posting has no application URL to open.")
            )

        # -- match quality ----------------------------------------------------
        minimum = settings.min_match_score if settings else 70
        if match is None:
            violations.append(
                PolicyViolation("not_matched", "Score this job against your profile first.")
            )
        else:
            if match.hard_requirement_failed:
                violations.append(
                    PolicyViolation(
                        "hard_requirement_failed",
                        "This job fails a hard requirement or one of your exclusions.",
                        {"risks": list(match.risks or [])},
                    )
                )
            if match.overall_score < minimum:
                violations.append(
                    PolicyViolation(
                        "below_minimum_score",
                        f"The match score ({match.overall_score}) is below your minimum "
                        f"({minimum}).",
                        {"score": match.overall_score, "minimum": minimum},
                    )
                )

        # -- the user's own filters -------------------------------------------
        if preference is not None:
            excluded = {normalize_company(name) for name in (preference.excluded_companies or [])}
            if job.normalized_company in excluded:
                violations.append(
                    PolicyViolation("company_excluded", "This company is on your excluded list.")
                )

            if preference.salary_min and job.salary_max and job.salary_max < preference.salary_min:
                violations.append(
                    PolicyViolation(
                        "salary_below_minimum",
                        f"The stated maximum salary ({job.salary_max:,}) is below your "
                        f"minimum ({preference.salary_min:,}).",
                    )
                )

            employment_types = [
                EmploymentType(value) for value in (preference.employment_types or [])
            ]
            if (
                employment_types
                and job.employment_type != EmploymentType.UNKNOWN.value
                and EmploymentType(job.employment_type) not in employment_types
            ):
                violations.append(
                    PolicyViolation(
                        "employment_type_excluded",
                        f"You are not looking for {job.employment_type.replace('_', ' ')} roles.",
                    )
                )

            if not self._location_acceptable(job, preference):
                violations.append(
                    PolicyViolation(
                        "location_unacceptable",
                        "This job's location does not match your preferences.",
                    )
                )

        # -- work authorization ------------------------------------------------
        profile = user.profile
        if profile is None or not profile.work_authorization_declared:
            violations.append(
                PolicyViolation(
                    "work_authorization_undeclared",
                    "Declare your work authorization before applying automatically.",
                )
            )
        elif (
            profile.requires_sponsorship_now or profile.requires_sponsorship_future
        ) and job.sponsorship_offered is False:
            violations.append(
                PolicyViolation(
                    "sponsorship_unavailable",
                    "This posting states it does not provide sponsorship, which you require.",
                )
            )

        # -- automation switches ------------------------------------------------
        if user.automation_paused:
            violations.append(
                PolicyViolation("automation_paused", "Automation is paused for your account.")
            )
        if settings is None or not settings.enabled:
            violations.append(
                PolicyViolation("automation_disabled", "Automation has not been enabled yet.")
            )

        # -- rate limits --------------------------------------------------------
        if settings is not None:
            daily = self._submitted_since(user.id, now - timedelta(days=1))
            hourly = self._submitted_since(user.id, now - timedelta(hours=1))
            if daily >= settings.daily_application_limit:
                retry_after = 3600
                violations.append(
                    PolicyViolation(
                        "daily_limit_reached",
                        f"You have reached your daily limit of "
                        f"{settings.daily_application_limit} applications.",
                        {"submitted": daily, "limit": settings.daily_application_limit},
                    )
                )
            elif hourly >= settings.hourly_application_limit:
                retry_after = 900
                violations.append(
                    PolicyViolation(
                        "hourly_limit_reached",
                        f"You have reached your hourly limit of "
                        f"{settings.hourly_application_limit} applications.",
                        {"submitted": hourly, "limit": settings.hourly_application_limit},
                    )
                )

        return PolicyDecision(
            allowed=not violations,
            violations=violations,
            dedupe_hash=dedupe_hash,
            retry_after_seconds=retry_after,
        )

    # ------------------------------------------------------------------ helpers
    def _submitted_since(self, user_id: uuid.UUID, since: datetime) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.user_id == user_id,
                    Application.deleted_at.is_(None),
                    Application.submitted_at.is_not(None),
                    Application.submitted_at >= since,
                    Application.status.in_(
                        [str(status) for status in SUBMITTED_APPLICATION_STATUSES]
                    ),
                )
            ).scalar_one()
        )

    @staticmethod
    def _location_acceptable(job: Job, preference: JobPreference) -> bool:
        wanted = [normalize_location(item) for item in (preference.locations or []) if item]
        remote_preference = preference.remote_preference

        if job.remote_type == RemoteType.REMOTE.value:
            return remote_preference != RemoteType.ONSITE.value
        if remote_preference == RemoteType.REMOTE.value:
            return False
        if not wanted or not job.normalized_location:
            return True
        return any(
            candidate in job.normalized_location or job.normalized_location.startswith(candidate)
            for candidate in wanted
        )


def resume_ready(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> bool:
    """A tailored resume must exist before an application may start."""
    from jobapply_db.models import ResumeVersion

    return (
        db.execute(
            select(func.count())
            .select_from(ResumeVersion)
            .where(
                ResumeVersion.user_id == user_id,
                ResumeVersion.job_id == job_id,
                ResumeVersion.deleted_at.is_(None),
                ResumeVersion.pdf_storage_key.is_not(None),
            )
        ).scalar_one()
        > 0
    )


def next_delay_seconds(settings: AutomationSettings | None) -> int:
    """A randomized pause between applications.

    This protects the user's own account standing and keeps automation from looking
    like a burst. It is not a way to get around an employer's rate limits.
    """
    import random

    if settings is None:
        return 60
    low = max(0, settings.min_delay_seconds)
    high = max(low, settings.max_delay_seconds)
    return random.randint(low, high)  # noqa: S311 - jitter, not cryptography


STATUS_TRANSITIONS: dict[str, set[str]] = {
    str(ApplicationStatus.SUBMITTED): {
        str(ApplicationStatus.INTERVIEW),
        str(ApplicationStatus.ASSESSMENT),
        str(ApplicationStatus.REJECTED),
        str(ApplicationStatus.OFFER),
        str(ApplicationStatus.WITHDRAWN),
    },
}


def manual_status_allowed(current: str, target: str) -> bool:
    """Manual tracker updates.

    The user may record any real-world outcome, but may not mark an application
    submitted by hand — that claim has to come from the automation observing it.
    """
    if target in {
        str(ApplicationStatus.SUBMITTED),
        str(ApplicationStatus.CONFIRMATION_CAPTURED),
        str(ApplicationStatus.SUBMISSION_UNCONFIRMED),
    }:
        return False
    return target in {
        str(ApplicationStatus.INTERVIEW),
        str(ApplicationStatus.ASSESSMENT),
        str(ApplicationStatus.REJECTED),
        str(ApplicationStatus.OFFER),
        str(ApplicationStatus.WITHDRAWN),
        str(ApplicationStatus.CANCELLED),
    }
