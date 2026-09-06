"""Dashboard counters and readiness.

The dashboard has to answer four questions immediately: how many applications went
out, how many succeeded, what needs my attention, and which jobs are my strongest
matches.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jobapply_db.models import (
    Application,
    AutomationSettings,
    Intervention,
    Job,
    JobMatch,
    Resume,
    User,
)
from jobapply_shared.enums import (
    SUBMITTED_APPLICATION_STATUSES,
    ApplicationStatus,
    InterventionStatus,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobapply_api.services.profile_service import ProfileService

IN_PROGRESS_STATUSES = (
    ApplicationStatus.RESUME_GENERATING,
    ApplicationStatus.RESUME_READY,
    ApplicationStatus.APPLICATION_STARTING,
    ApplicationStatus.FORM_ANALYZING,
    ApplicationStatus.FORM_FILLING,
    ApplicationStatus.WAITING_FOR_VERIFICATION,
    ApplicationStatus.READY_TO_SUBMIT,
    ApplicationStatus.SUBMITTING,
)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _count(self, model: Any, *conditions: Any) -> int:
        return int(
            self.db.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()
        )

    def counters(self, user_id: uuid.UUID) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        submitted = [str(status) for status in SUBMITTED_APPLICATION_STATUSES]
        in_progress = [str(status) for status in IN_PROGRESS_STATUSES]

        applications_total = self._count(
            Application, Application.user_id == user_id, Application.deleted_at.is_(None)
        )
        applications_submitted = self._count(
            Application,
            Application.user_id == user_id,
            Application.deleted_at.is_(None),
            Application.status.in_(submitted),
        )
        applications_failed = self._count(
            Application,
            Application.user_id == user_id,
            Application.deleted_at.is_(None),
            Application.status == str(ApplicationStatus.FAILED),
        )
        finished = applications_submitted + applications_failed

        average_score = self.db.execute(
            select(func.avg(JobMatch.overall_score)).where(JobMatch.user_id == user_id)
        ).scalar()

        return {
            "jobs_discovered": self._count(Job, Job.deleted_at.is_(None)),
            "jobs_matched": self._count(JobMatch, JobMatch.user_id == user_id),
            "applications_total": applications_total,
            "applications_submitted": applications_submitted,
            "applications_this_week": self._count(
                Application,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.submitted_at.is_not(None),
                Application.submitted_at >= week_ago,
            ),
            "applications_this_month": self._count(
                Application,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.submitted_at.is_not(None),
                Application.submitted_at >= month_ago,
            ),
            "applications_failed": applications_failed,
            "applications_in_progress": self._count(
                Application,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.status.in_(in_progress),
            ),
            "interviews": self._count(
                Application,
                Application.user_id == user_id,
                Application.status == str(ApplicationStatus.INTERVIEW),
            ),
            "offers": self._count(
                Application,
                Application.user_id == user_id,
                Application.status == str(ApplicationStatus.OFFER),
            ),
            "rejections": self._count(
                Application,
                Application.user_id == user_id,
                Application.status == str(ApplicationStatus.REJECTED),
            ),
            "open_interventions": self._count(
                Intervention,
                Intervention.user_id == user_id,
                Intervention.status == str(InterventionStatus.OPEN),
            ),
            "average_match_score": round(float(average_score or 0.0), 1),
            "automation_success_rate": round(100 * applications_submitted / finished, 1)
            if finished
            else 0.0,
            "failure_rate": round(100 * applications_failed / finished, 1) if finished else 0.0,
        }

    def readiness(self, user: User) -> dict[str, Any]:
        profile_service = ProfileService(self.db)
        completeness = profile_service.completeness(user.id)
        has_master = (
            self.db.execute(
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
        settings = self.db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user.id)
        ).scalar_one_or_none()
        profile = profile_service.get(user.id)

        blockers = list(completeness["blocks_automation"])
        if not has_master:
            blockers.append("Upload a master resume so applications have something to tailor.")
        if settings is None or not settings.enabled:
            blockers.append("Automation has not been enabled yet.")

        return {
            "profile_score": completeness["score"],
            "has_master_resume": has_master,
            "work_authorization_declared": profile.work_authorization_declared,
            "automation_enabled": bool(settings and settings.enabled),
            "automation_paused": user.automation_paused,
            "blockers": blockers,
        }

    def recent_applications(self, user_id: uuid.UUID, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.user_id == user_id, Application.deleted_at.is_(None))
            .order_by(Application.created_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "id": str(application.id),
                "status": application.status,
                "company": job.company_name,
                "title": job.title,
                "match_score": application.match_score,
                "submitted_at": application.submitted_at.isoformat()
                if application.submitted_at
                else None,
                "created_at": application.created_at.isoformat(),
            }
            for application, job in rows
        ]

    def attention_required(self, user_id: uuid.UUID, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Intervention, Application, Job)
            .join(Application, Application.id == Intervention.application_id)
            .join(Job, Job.id == Application.job_id)
            .where(
                Intervention.user_id == user_id,
                Intervention.status == str(InterventionStatus.OPEN),
            )
            .order_by(Intervention.created_at.asc())
            .limit(limit)
        ).all()
        return [
            {
                "id": str(intervention.id),
                "application_id": str(application.id),
                "type": intervention.type,
                "reason": intervention.reason,
                "current_step": intervention.current_step,
                "company": job.company_name,
                "title": job.title,
                "created_at": intervention.created_at.isoformat(),
            }
            for intervention, application, job in rows
        ]
