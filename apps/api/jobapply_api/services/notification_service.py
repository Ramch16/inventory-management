"""In-app notifications and transactional e-mail.

E-mail is only ever sent to the account owner's own address, and only for the
transactional purposes listed in ``NotificationKind``. Nothing is sent to a third
party.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jobapply_db.models import AutomationSettings, Notification, User
from jobapply_shared.email import EmailMessage, EmailSender
from jobapply_shared.enums import NotificationChannel, NotificationKind
from jobapply_shared.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = get_logger(__name__)

#: Kinds that get an e-mail copy unless the user says otherwise. These are the ones
#: where waiting for the next sign-in would cost the user something.
DEFAULT_EMAIL_KINDS = frozenset(
    {
        str(NotificationKind.CAPTCHA_REQUIRED),
        str(NotificationKind.OTP_REQUIRED),
        str(NotificationKind.MFA_REQUIRED),
        str(NotificationKind.HUMAN_REVIEW_REQUIRED),
        str(NotificationKind.APPLICATION_FAILED),
        str(NotificationKind.INTERVIEW_DETECTED),
    }
)


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
        email: bool | None = None,
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

        # An e-mail copy goes out only for the kinds the user asked to be told about.
        if email is None:
            email = self._wants_email(user_id, str(kind))
        if email:
            self._email_copy(user_id, title, body, link)
        return notification

    def _wants_email(self, user_id: uuid.UUID, kind: str) -> bool:
        settings = self.db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user_id)
        ).scalar_one_or_none()
        preferences = (settings.notification_preferences if settings else None) or {}
        email_preferences = preferences.get("email")
        if isinstance(email_preferences, dict):
            return bool(email_preferences.get(kind, kind in DEFAULT_EMAIL_KINDS))
        if isinstance(email_preferences, bool):
            return email_preferences
        return kind in DEFAULT_EMAIL_KINDS

    def _email_copy(
        self, user_id: uuid.UUID, title: str, body: str | None, link: str | None
    ) -> None:
        user = self.db.get(User, user_id)
        if user is None or not user.email or user.deleted_at is not None:
            return
        lines = [body or title]
        if link:
            lines.append(f"\nOpen: {link}")
        try:
            self.send_email(to=user.email, subject=title, body="\n".join(lines))
        except Exception:  # noqa: BLE001 - a failed e-mail must not lose the in-app copy
            logger.warning(
                "notification.email_failed",
                extra={"context": {"event": "notification.email_failed", "kind": title}},
            )

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
