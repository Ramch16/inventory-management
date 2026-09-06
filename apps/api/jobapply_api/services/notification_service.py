"""In-app notifications and transactional e-mail.

E-mail is only ever sent to the account owner's own address, and only for the
transactional purposes listed in ``NotificationKind``. Nothing is sent to a third
party.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jobapply_db.models import Notification
from jobapply_shared.email import EmailMessage, EmailSender
from jobapply_shared.enums import NotificationChannel, NotificationKind
from jobapply_shared.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, db: Session, email_sender: EmailSender) -> None:
        self.db = db
        self.email_sender = email_sender

    def create(
        self,
        *,
        user_id: uuid.UUID,
        kind: NotificationKind | str,
        title: str,
        body: str | None = None,
        link: str | None = None,
        channel: NotificationChannel | str = NotificationChannel.IN_APP,
        payload: dict | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            kind=str(kind),
            channel=str(channel),
            title=title,
            body=body,
            link=link,
            payload=payload or {},
        )
        self.db.add(notification)
        return notification

    def send_email(self, *, to: str, subject: str, body: str) -> None:
        self.email_sender.send(EmailMessage(to=to, subject=subject, text_body=body))

    def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        total = self.db.execute(
            select(func.count()).select_from(Notification).where(*conditions)
        ).scalar_one()
        rows = (
            self.db.execute(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification | None:
        notification = self.db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        ).scalar_one_or_none()
        if notification and notification.read_at is None:
            notification.read_at = datetime.now(tz=UTC)
        return notification

    def mark_all_read(self, user_id: uuid.UUID) -> int:
        rows = (
            self.db.execute(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.read_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(tz=UTC)
        for row in rows:
            row.read_at = now
        return len(rows)

    def unread_count(self, user_id: uuid.UUID) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            ).scalar_one()
        )
