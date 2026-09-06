"""Scheduled job discovery and matching.

Workers reuse the same service layer the API calls, so a job discovered by the
scheduler goes through exactly the code path a user-initiated search does.
"""

from __future__ import annotations

import uuid

from celery import shared_task
from jobapply_api.schemas.job import JobSearchRequest
from jobapply_api.services.job_service import JobService
from jobapply_db.models import AutomationSettings, User
from jobapply_db.session import session_scope
from jobapply_shared.errors import TransientError, ValidationError_
from jobapply_shared.logging import get_logger
from sqlalchemy import select

logger = get_logger(__name__)


@shared_task(
    name="jobs.discover_for_user",
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def discover_for_user(self, user_id: str) -> dict:
    """Run discovery using the user's active preference."""
    with session_scope() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None or user.deleted_at is not None or not user.is_active:
            return {"skipped": "user_unavailable"}
        service = JobService(db)
        try:
            result = service.discover(user.id, JobSearchRequest())
        except ValidationError_ as exc:
            # No enabled source is a configuration state, not a failure to retry.
            return {"skipped": exc.code}
        logger.info(
            "jobs.scheduled_discovery",
            extra={"context": {"event": "jobs.scheduled_discovery", "user_id": user_id, **result}},
        )
        return result


@shared_task(name="jobs.discover_for_all_active_users", bind=True)
def discover_for_all_active_users(self) -> dict:
    """Fan out discovery to every user who has automation switched on.

    Users who never enabled automation are not polled: discovery on their behalf
    would be work they did not ask for.
    """
    with session_scope() as db:
        user_ids = [
            str(row)
            for row in db.execute(
                select(User.id)
                .join(AutomationSettings, AutomationSettings.user_id == User.id)
                .where(
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                    User.automation_paused.is_(False),
                    AutomationSettings.enabled.is_(True),
                )
            ).scalars()
        ]
    for user_id in user_ids:
        discover_for_user.delay(user_id)
    return {"queued": len(user_ids)}


@shared_task(name="match.rescore_user", bind=True)
def rescore_user(self, user_id: str) -> dict:
    """Re-run matching for one user, after a profile or preference change."""
    with session_scope() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None or user.deleted_at is not None:
            return {"skipped": "user_unavailable"}
        count = JobService(db).rescore_all(user.id)
        return {"rescored": count}


@shared_task(name="jobs.expire_stale", bind=True)
def expire_stale(self) -> dict:
    """Mark jobs past their stated expiration date so they stop being recommended."""
    with session_scope() as db:
        return {"expired": JobService(db).expire_stale_jobs()}
