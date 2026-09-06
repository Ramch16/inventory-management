"""Application error hierarchy.

Every error carries a stable machine-readable ``code`` so the frontend can branch on
it without parsing prose, and an HTTP status so the API edge can translate without a
lookup table.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all expected, user-visible failures."""

    code: str = "internal_error"
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError_(AppError):
    code = "validation_error"
    status_code = 422


class AuthenticationError(AppError):
    code = "not_authenticated"
    status_code = 401


class PermissionError_(AppError):
    code = "forbidden"
    status_code = 403


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class RateLimitError(AppError):
    code = "rate_limited"
    status_code = 429


class ProviderError(AppError):
    """An external provider (LLM, storage, e-mail) failed."""

    code = "provider_error"
    status_code = 502


class TransientError(ProviderError):
    """Retryable failure: network blip, timeout, 5xx from a dependency."""

    code = "transient_error"
