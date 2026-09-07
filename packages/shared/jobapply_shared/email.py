"""E-mail delivery abstraction.

The console backend is a development sink: it stands in for an inbox, so it prints
the whole message — verification link included — to stdout, and keeps an in-process
outbox for tests. The structured log line stays free of the body, because that is
what ships to a log aggregator. ``_production_guards`` refuses this backend outside
development, so a real deployment cannot silently drop its mail.

No e-mail is ever sent to a third party without explicit user configuration.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from typing import Protocol

from jobapply_shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Development sink. Prints the message and keeps an in-process outbox for tests.

    Printing the body is the entire point: without it there is no way to reach the
    verification or password-reset link when running locally, and the account cannot
    be verified at all. It goes to stdout rather than through ``logger`` so a token
    never reaches structured logs.
    """

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
        print(  # noqa: T201 - this backend exists to be read by a person
            "\n"
            "─── e-mail (console backend; not delivered anywhere) ───\n"
            f"To:      {message.to}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.text_body}\n"
            "───────────────────────────────────────────────────────",
            flush=True,
        )
        logger.info(
            "email.sent",
            extra={
                "context": {"event": "email.sent", "to": message.to, "subject": message.subject}
            },
        )


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        sender: str = "no-reply@jobapply.local",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._sender = sender

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        for key, value in message.headers.items():
            mime[key] = value
        mime.set_content(message.text_body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")
        with smtplib.SMTP(self._host, self._port, timeout=15) as client:
            if self._use_tls:
                client.starttls()
            if self._username and self._password:
                client.login(self._username, self._password)
            client.send_message(mime)
        logger.info(
            "email.sent",
            extra={
                "context": {"event": "email.sent", "to": message.to, "subject": message.subject}
            },
        )


def build_email_sender(settings: object) -> EmailSender:
    if getattr(settings, "email_backend", "console") == "smtp":
        return SmtpEmailSender(
            getattr(settings, "smtp_host", "localhost"),
            getattr(settings, "smtp_port", 25),
            username=getattr(settings, "smtp_username", None),
            password=getattr(settings, "smtp_password", None),
            use_tls=getattr(settings, "smtp_use_tls", False),
            sender=getattr(settings, "email_from", "no-reply@jobapply.local"),
        )
    return ConsoleEmailSender()
