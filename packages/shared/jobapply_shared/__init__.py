"""Cross-cutting utilities shared by every service in the platform.

This package must never import from ``apps/*`` or from another domain package.
"""

from jobapply_shared.errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionError_,
    RateLimitError,
    ValidationError_,
)
from jobapply_shared.settings import Settings, get_settings

__all__ = [
    "AppError",
    "AuthenticationError",
    "ConflictError",
    "NotFoundError",
    "PermissionError_",
    "RateLimitError",
    "Settings",
    "ValidationError_",
    "get_settings",
]
