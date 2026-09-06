"""Audit trail helper.

Audit rows are written in the same transaction as the action they describe, so an
action can never be committed without its audit record.
"""

from __future__ import annotations

import uuid
from typing import Any

from jobapply_db.models import AuditLog
from jobapply_shared.logging import get_logger, redact
from sqlalchemy.orm import Session

logger = get_logger(__name__)


def record(
    db: Session,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    data: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
        data=redact(data or {}),
    )
    db.add(entry)
    logger.info(
        action,
        extra={
            "context": {
                "event": action,
                "user_id": str(actor_user_id) if actor_user_id else None,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
            }
        },
    )
    return entry
