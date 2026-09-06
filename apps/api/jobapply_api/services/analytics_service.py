"""Analytics.

Every number here is computed from the user's own rows. Nothing is estimated or
extrapolated: an empty account produces zeros and empty series, not a plausible-looking
chart.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from jobapply_db.models import Application, Job, JobMatch
from jobapply_shared.enums import SUBMITTED_APPLICATION_STATUSES, ApplicationStatus
from sqlalchemy import func, select
from sqlalchemy.orm import Session

#: The funnel the dashboard and analytics page both describe.
FUNNEL_STAGES = (
    ("discovered", "Jobs discovered"),
    ("matched", "Matched to you"),
    ("applied", "Applications sent"),
    ("interview", "Interviews"),
    ("offer", "Offers"),
)

SCORE_BUCKETS = ((0, 39), (40, 59), (60, 74), (75, 89), (90, 100))


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ helpers
    def _submitted_statuses(self) -> list[str]:
        return [str(status) for status in SUBMITTED_APPLICATION_STATUSES]

    def _range_start(self, days: int) -> datetime:
        return datetime.now(tz=UTC) - timedelta(days=days)

    # ------------------------------------------------------------------- series
    def applications_per_day(self, user_id: uuid.UUID, days: int = 30) -> list[dict[str, Any]]:
        """One row per day in the window, including days with nothing.

        Bucketing happens in Python rather than in SQL: date truncation differs
        between PostgreSQL and SQLite, the row count per user is small, and this keeps
        one implementation that is provably identical on both.
        """
        start = self._range_start(days)
        rows = self.db.execute(
            select(Application.created_at, Application.submitted_at).where(
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.created_at >= start,
            )
        ).all()

        created_by_day: dict[date, int] = {}
        submitted_by_day: dict[date, int] = {}
        for created_at, submitted_at in rows:
            created_by_day[created_at.date()] = created_by_day.get(created_at.date(), 0) + 1
            if submitted_at is not None:
                key = submitted_at.date()
                submitted_by_day[key] = submitted_by_day.get(key, 0) + 1

        today = date.today()
        return [
            {
                "date": (day := today - timedelta(days=offset)).isoformat(),
                "created": created_by_day.get(day, 0),
                "submitted": submitted_by_day.get(day, 0),
            }
            for offset in range(days, -1, -1)
        ]

    def _breakdown(self, user_id: uuid.UUID, column: Any, days: int, limit: int = 10):
        start = self._range_start(days)
        rows = self.db.execute(
            select(column.label("label"), func.count().label("count"))
            .select_from(Application)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
                Application.created_at >= start,
            )
            .group_by(column)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        return [{"label": row.label or "Not stated", "count": int(row.count)} for row in rows]

    def by_company(self, user_id: uuid.UUID, days: int = 90) -> list[dict[str, Any]]:
        return self._breakdown(user_id, Job.company_name, days)

    def by_role(self, user_id: uuid.UUID, days: int = 90) -> list[dict[str, Any]]:
        return self._breakdown(user_id, Job.normalized_title, days)

    def by_location(self, user_id: uuid.UUID, days: int = 90) -> list[dict[str, Any]]:
        return self._breakdown(user_id, Job.location, days)

    def match_score_distribution(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        scores = list(
            self.db.execute(
                select(JobMatch.overall_score).where(JobMatch.user_id == user_id)
            ).scalars()
        )
        buckets = []
        for low, high in SCORE_BUCKETS:
            buckets.append(
                {
                    "label": f"{low}–{high}",
                    "count": sum(1 for score in scores if low <= score <= high),
                }
            )
        return buckets

    def funnel(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        submitted = self._submitted_statuses()
        counts = {
            "discovered": int(
                self.db.execute(
                    select(func.count()).select_from(Job).where(Job.deleted_at.is_(None))
                ).scalar_one()
            ),
            "matched": int(
                self.db.execute(
                    select(func.count()).select_from(JobMatch).where(JobMatch.user_id == user_id)
                ).scalar_one()
            ),
            "applied": int(
                self.db.execute(
                    select(func.count())
                    .select_from(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.deleted_at.is_(None),
                        Application.status.in_(submitted),
                    )
                ).scalar_one()
            ),
            "interview": self._status_count(user_id, ApplicationStatus.INTERVIEW),
            "offer": self._status_count(user_id, ApplicationStatus.OFFER),
        }
        return [
            {"stage": key, "label": label, "count": counts[key]} for key, label in FUNNEL_STAGES
        ]

    def _status_count(self, user_id: uuid.UUID, status: ApplicationStatus) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.user_id == user_id,
                    Application.deleted_at.is_(None),
                    Application.status == str(status),
                )
            ).scalar_one()
        )

    def outcomes(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Response rate is only meaningful once something has been submitted."""
        submitted = self._submitted_statuses()
        total_submitted = int(
            self.db.execute(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.user_id == user_id,
                    Application.deleted_at.is_(None),
                    Application.status.in_(submitted),
                )
            ).scalar_one()
        )
        responses = sum(
            self._status_count(user_id, status)
            for status in (
                ApplicationStatus.INTERVIEW,
                ApplicationStatus.ASSESSMENT,
                ApplicationStatus.REJECTED,
                ApplicationStatus.OFFER,
            )
        )
        interviews = self._status_count(user_id, ApplicationStatus.INTERVIEW)
        return {
            "submitted": total_submitted,
            "responses": responses,
            "interviews": interviews,
            "offers": self._status_count(user_id, ApplicationStatus.OFFER),
            "rejections": self._status_count(user_id, ApplicationStatus.REJECTED),
            "response_rate": round(100 * responses / total_submitted, 1)
            if total_submitted
            else 0.0,
            "interview_rate": round(100 * interviews / total_submitted, 1)
            if total_submitted
            else 0.0,
        }

    def automation_health(self, user_id: uuid.UUID) -> dict[str, Any]:
        """How the automation itself is doing, separately from hiring outcomes."""
        submitted = self._submitted_statuses()
        counts = dict(
            self.db.execute(
                select(Application.status, func.count())
                .where(Application.user_id == user_id, Application.deleted_at.is_(None))
                .group_by(Application.status)
            ).all()
        )
        succeeded = sum(counts.get(status, 0) for status in submitted)
        failed = counts.get(str(ApplicationStatus.FAILED), 0)
        paused = counts.get(str(ApplicationStatus.WAITING_FOR_VERIFICATION), 0)
        finished = succeeded + failed
        unconfirmed = counts.get(str(ApplicationStatus.SUBMISSION_UNCONFIRMED), 0)
        return {
            "succeeded": succeeded,
            "failed": failed,
            "awaiting_user": paused,
            "unconfirmed": unconfirmed,
            "success_rate": round(100 * succeeded / finished, 1) if finished else 0.0,
            "failure_rate": round(100 * failed / finished, 1) if finished else 0.0,
            "intervention_rate": round(100 * paused / max(finished + paused, 1), 1),
        }

    def report(self, user_id: uuid.UUID, days: int = 30) -> dict[str, Any]:
        return {
            "range_days": days,
            "applications_per_day": self.applications_per_day(user_id, days),
            "by_company": self.by_company(user_id, days),
            "by_role": self.by_role(user_id, days),
            "by_location": self.by_location(user_id, days),
            "match_score_distribution": self.match_score_distribution(user_id),
            "funnel": self.funnel(user_id),
            "outcomes": self.outcomes(user_id),
            "automation": self.automation_health(user_id),
        }
