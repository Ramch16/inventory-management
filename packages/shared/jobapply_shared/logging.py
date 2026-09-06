"""Structured JSON logging with mandatory redaction.

Credentials, cookies, tokens and OTP codes must never reach a log sink. Redaction is
implemented as a logging filter so it applies to third-party loggers too, not only to
call sites we control.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "cookie",
    "set-cookie",
    "otp",
    "otp_code",
    "code",
    "secret",
    "client_secret",
    "api_key",
    "secret_key",
    "session_state",
    "state_blob",
    "password_hash",
}

REDACTED = "[redacted]"

_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}")


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively strip sensitive values out of a payload."""
    if _depth > 6:
        return value
    if isinstance(value, dict):
        return {
            key: (REDACTED if str(key).lower() in SENSITIVE_KEYS else redact(val, _depth + 1))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth + 1) for item in value]
    if isinstance(value, str):
        cleaned = _BEARER_RE.sub("Bearer " + REDACTED, value)
        return _JWT_RE.sub(REDACTED, cleaned)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.args, dict):
            record.args = redact(record.args)
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            record.context = redact(extra)
        record.msg = redact(record.msg)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactionFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s :: %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").handlers.clear()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **context: Any,
) -> None:
    """Emit one structured automation/application event.

    Callers pass ``user_id``, ``application_id``, ``job_id``, ``ats``, ``status``
    and ``duration_ms`` where they apply; the redaction filter handles the rest.
    """
    logger.log(level, event, extra={"context": {"event": event, **context}})
