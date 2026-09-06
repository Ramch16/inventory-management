"""Transactional e-mail delivery.

Delivery is a task so a slow or briefly unavailable SMTP server never blocks an HTTP
request, and so a failed send is retried with backoff instead of being lost.
"""

from __future__ import annotations

from celery import shared_task
from jobapply_shared.email import EmailMessage, build_email_sender
from jobapply_shared.errors import TransientError
from jobapply_shared.logging import get_logger
from jobapply_shared.settings import get_settings

logger = get_logger(__name__)


@shared_task(
    name="email.send",
    bind=True,
    autoretry_for=(TransientError, OSError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def send_email(self, *, to: str, subject: str, body: str) -> dict:
    sender = build_email_sender(get_settings())
    sender.send(EmailMessage(to=to, subject=subject, text_body=body))
    logger.info(
        "email.delivered",
        extra={
            "context": {"event": "email.delivered", "subject": subject, "task_id": self.request.id}
        },
    )
    return {"delivered": True}
