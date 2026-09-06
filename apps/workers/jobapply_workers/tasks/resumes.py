"""Resume processing tasks.

Parsing runs synchronously on upload so the user sees the result immediately; this
task exists for re-parsing after a parser improvement and for bulk backfills.
"""

from __future__ import annotations

import uuid

from celery import shared_task
from jobapply_db.models import Resume
from jobapply_db.session import session_scope
from jobapply_resume.parser import parse_resume
from jobapply_shared.dates import utcnow
from jobapply_shared.logging import get_logger

logger = get_logger(__name__)


@shared_task(name="resume.reparse", bind=True, max_retries=2)
def reparse_resume(self, resume_id: str) -> dict:
    with session_scope() as db:
        resume = db.get(Resume, uuid.UUID(resume_id))
        if resume is None or resume.deleted_at is not None:
            return {"skipped": "resume_missing"}
        if not resume.raw_text:
            resume.parse_status = "failed"
            resume.parse_error = "No extracted text is stored for this resume."
            return {"skipped": "no_text"}
        try:
            parsed = parse_resume(resume.raw_text)
            resume.structured = parsed.model_dump(mode="json", exclude={"raw_text"})
            resume.parse_status = "parsed"
            resume.parse_error = None
        except Exception as exc:
            logger.exception("resume.reparse_failed")
            resume.parse_status = "failed"
            resume.parse_error = str(exc)[:1000]
            return {"parsed": False}
        finally:
            resume.parsed_at = utcnow()
        return {"parsed": True, "positions": len(parsed.positions)}
