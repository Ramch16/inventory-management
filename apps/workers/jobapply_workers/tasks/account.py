"""Account lifecycle tasks.

Deletion is two-stage: the API soft-deletes immediately (the account stops working at
once), and this task performs the irreversible purge of rows and stored objects after
the grace period.
"""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from jobapply_db.models import Resume, ResumeVersion, User
from jobapply_db.session import session_scope
from jobapply_shared.dates import utcnow
from jobapply_shared.logging import get_logger
from jobapply_shared.settings import get_settings
from jobapply_shared.storage import build_storage
from sqlalchemy import select

logger = get_logger(__name__)

GRACE_PERIOD = timedelta(days=7)


@shared_task(name="account.purge_deleted", bind=True)
def purge_deleted_accounts(self) -> dict:
    """Hard-delete accounts whose grace period has elapsed.

    Object storage is cleaned first: an orphaned row is recoverable, an orphaned
    private document is not acceptable.
    """
    settings = get_settings()
    storage = build_storage(settings)
    cutoff = utcnow() - GRACE_PERIOD
    purged = 0

    with session_scope() as db:
        users = (
            db.execute(select(User).where(User.deleted_at.is_not(None), User.deleted_at < cutoff))
            .scalars()
            .all()
        )
        for user in users:
            keys: list[str] = []
            for resume in db.execute(select(Resume).where(Resume.user_id == user.id)).scalars():
                if resume.original_storage_key:
                    keys.append(resume.original_storage_key)
            for version in db.execute(
                select(ResumeVersion).where(ResumeVersion.user_id == user.id)
            ).scalars():
                keys.extend(
                    key
                    for key in (
                        version.docx_storage_key,
                        version.pdf_storage_key,
                        version.cover_letter_storage_key,
                    )
                    if key
                )
            for key in keys:
                try:
                    storage.delete(key)
                except Exception:
                    logger.warning(
                        "account.purge_object_failed",
                        extra={"context": {"event": "account.purge_object_failed"}},
                    )
            # Every user-owned table cascades from users.id.
            db.delete(user)
            purged += 1

    logger.info("account.purged", extra={"context": {"event": "account.purged", "count": purged}})
    return {"purged": purged}
