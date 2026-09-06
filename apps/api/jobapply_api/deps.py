"""FastAPI dependencies: database session, current user, CSRF, RBAC, rate limits.

Authorization is enforced here rather than inside handlers, and every service call
downstream is scoped by ``user_id``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from jobapply_db.models import User
from jobapply_db.session import get_sessionmaker
from jobapply_shared.email import EmailSender, build_email_sender
from jobapply_shared.errors import AuthenticationError, PermissionError_, RateLimitError
from jobapply_shared.ratelimit import InMemoryRateLimiter, RateLimiter, RedisRateLimiter
from jobapply_shared.security import decode_jwt, tokens_equal
from jobapply_shared.settings import Settings, get_settings
from jobapply_shared.storage import ObjectStorage, build_storage
from sqlalchemy.orm import Session

from jobapply_api.services.auth_service import AuthService
from jobapply_api.services.dashboard_service import DashboardService
from jobapply_api.services.notification_service import NotificationService
from jobapply_api.services.profile_service import ProfileService
from jobapply_api.services.resume_service import ResumeService

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def db_session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def settings_dep() -> Settings:
    return get_settings()


@lru_cache
def _storage() -> ObjectStorage:
    return build_storage(get_settings())


@lru_cache
def _email_sender() -> EmailSender:
    return build_email_sender(get_settings())


@lru_cache
def _rate_limiter() -> RateLimiter:
    settings = get_settings()
    if settings.environment == "test":
        return InMemoryRateLimiter()
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
        return RedisRateLimiter(client)
    except Exception:  # pragma: no cover - falls back when Redis is unavailable
        return InMemoryRateLimiter()


def storage_dep() -> ObjectStorage:
    return _storage()


def email_dep() -> EmailSender:
    return _email_sender()


def rate_limiter_dep() -> RateLimiter:
    return _rate_limiter()


SessionDep = Annotated[Session, Depends(db_session)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]
StorageDep = Annotated[ObjectStorage, Depends(storage_dep)]
EmailDep = Annotated[EmailSender, Depends(email_dep)]
RateLimiterDep = Annotated[RateLimiter, Depends(rate_limiter_dep)]


# ------------------------------------------------------------------------ services
def notification_service(db: SessionDep, sender: EmailDep) -> NotificationService:
    return NotificationService(db, sender)


NotificationServiceDep = Annotated[NotificationService, Depends(notification_service)]


def auth_service(
    db: SessionDep, settings: SettingsDep, notifications: NotificationServiceDep
) -> AuthService:
    return AuthService(db, settings, notifications)


def profile_service(db: SessionDep) -> ProfileService:
    return ProfileService(db)


def resume_service(db: SessionDep, storage: StorageDep, settings: SettingsDep) -> ResumeService:
    return ResumeService(db, storage, settings.upload_max_bytes)


def dashboard_service(db: SessionDep) -> DashboardService:
    return DashboardService(db)


AuthServiceDep = Annotated[AuthService, Depends(auth_service)]
ProfileServiceDep = Annotated[ProfileService, Depends(profile_service)]
ResumeServiceDep = Annotated[ResumeService, Depends(resume_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(dashboard_service)]


# ----------------------------------------------------------------------- identity
def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def _check_csrf(request: Request, settings: Settings, used_cookie_auth: bool) -> None:
    """Double-submit CSRF, required only for cookie-authenticated unsafe requests.

    Bearer-token clients are not subject to CSRF because the browser never attaches a
    bearer header automatically.
    """
    if not used_cookie_auth or request.method in SAFE_METHODS:
        return
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    if not cookie_token or not header_token or not tokens_equal(cookie_token, header_token):
        raise PermissionError_("CSRF token missing or invalid.", code="csrf_failed")


def current_user(request: Request, db: SessionDep, settings: SettingsDep) -> User:
    token = _bearer_token(request)
    used_cookie_auth = False
    if token is None:
        token = request.cookies.get(settings.access_cookie_name)
        used_cookie_auth = token is not None
    if not token:
        raise AuthenticationError("Sign in to continue.", code="not_authenticated")

    payload = decode_jwt(token, secret_key=settings.secret_key, expected_type="access")
    _check_csrf(request, settings, used_cookie_auth)

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.deleted_at is not None or not user.is_active:
        raise AuthenticationError("Session is no longer valid.", code="session_invalid")
    if payload.get("epoch") != user.token_epoch:
        raise AuthenticationError("Session has been revoked.", code="session_revoked")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def current_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise PermissionError_("Administrator access is required.", code="admin_required")
    return user


CurrentAdmin = Annotated[User, Depends(current_admin)]


# --------------------------------------------------------------------- rate limits
def enforce_rate_limit(
    request: Request, limiter: RateLimiter, *, bucket: str, limit: int, window_seconds: int
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    decision = limiter.check(f"{bucket}:{client_ip}", limit, window_seconds)
    if not decision.allowed:
        raise RateLimitError(
            "Too many attempts. Try again shortly.",
            code="rate_limited",
            details={"retry_after_seconds": decision.retry_after_seconds},
        )


def auth_rate_limit(request: Request, limiter: RateLimiterDep) -> None:
    """10 authentication attempts per IP per five minutes."""
    enforce_rate_limit(request, limiter, bucket="auth", limit=10, window_seconds=300)


def request_meta(request: Request) -> dict[str, str | None]:
    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    return {"ip_address": client_ip, "user_agent": request.headers.get("user-agent")}


RequestMeta = Annotated[dict, Depends(request_meta)]
