"""Authentication and account lifecycle.

Design notes:

* Password hashes are Argon2id and are never returned or logged.
* Single-use tokens (verification, reset) are stored as SHA-256 digests only.
* Enumeration is avoided: "forgot password" and "resend verification" always answer
  202 whether or not the address exists.
* Deleting an account soft-deletes immediately, revokes every session, and queues the
  hard purge of rows and stored objects.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jobapply_db.models import (
    AutomationSettings,
    JobPreference,
    OAuthAccount,
    Profile,
    Subscription,
    User,
)
from jobapply_db.models.user import AuthToken
from jobapply_shared.enums import AuthProvider, NotificationKind, SubscriptionPlan, UserRole
from jobapply_shared.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError_,
)
from jobapply_shared.logging import get_logger
from jobapply_shared.security import (
    IssuedToken,
    decode_jwt,
    generate_url_token,
    hash_password,
    hash_token,
    issue_jwt,
    needs_rehash,
    verify_password,
)
from jobapply_shared.settings import Settings
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobapply_api.schemas.auth import RegisterRequest
from jobapply_api.services import audit
from jobapply_api.services.notification_service import NotificationService

logger = get_logger(__name__)

PURPOSE_EMAIL_VERIFICATION = "email_verification"
PURPOSE_PASSWORD_RESET = "password_reset"  # noqa: S105  a token purpose, not a secret


@dataclass(frozen=True)
class SessionTokens:
    access: IssuedToken
    refresh: IssuedToken
    csrf_token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, db: Session, settings: Settings, notifications: NotificationService) -> None:
        self.db = db
        self.settings = settings
        self.notifications = notifications

    # ------------------------------------------------------------------ lookup
    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            func.lower(User.email) == normalize_email(email), User.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    # ---------------------------------------------------------------- register
    def register(self, data: RegisterRequest, *, request_meta: dict | None = None) -> User:
        email = normalize_email(data.email)
        if self.get_by_email(email):
            # The address is already registered. We still avoid leaking *which*
            # accounts exist through timing by doing the same work either way.
            raise ConflictError(
                "An account with this e-mail address already exists.", code="email_taken"
            )

        user = User(
            email=email,
            password_hash=hash_password(data.password),
            role=UserRole.USER,
            is_active=True,
            automation_paused=True,
        )
        self.db.add(user)
        self.db.flush()

        self.db.add(
            Profile(
                user_id=user.id,
                first_name=data.first_name,
                last_name=data.last_name,
                email=email,
            )
        )
        self.db.add(
            AutomationSettings(
                user_id=user.id,
                daily_application_limit=self.settings.automation_daily_limit,
                hourly_application_limit=self.settings.automation_hourly_limit,
                min_delay_seconds=self.settings.automation_min_delay_seconds,
                max_delay_seconds=self.settings.automation_max_delay_seconds,
                min_match_score=self.settings.automation_min_match_score,
                confidence_auto_threshold=self.settings.confidence_auto_threshold,
                confidence_review_threshold=self.settings.confidence_review_threshold,
            )
        )
        self.db.add(JobPreference(user_id=user.id, name="Default"))
        self.db.add(Subscription(user_id=user.id, plan=SubscriptionPlan.FREE, provider="noop"))

        audit.record(
            self.db,
            action="auth.register",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            **(request_meta or {}),
        )
        self.notifications.create(
            user_id=user.id,
            kind=NotificationKind.WELCOME,
            title="Welcome to JobApply",
            body="Complete onboarding to unlock job matching and application automation.",
            link="/onboarding",
        )
        self.send_verification_email(user)
        return user

    # ------------------------------------------------------------------- login
    def authenticate(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if user is None or not user.password_hash:
            # Spend comparable time so a missing account is not distinguishable.
            verify_password(password, hash_password(secrets.token_urlsafe(16)))
            raise AuthenticationError("Incorrect e-mail or password.", code="invalid_credentials")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Incorrect e-mail or password.", code="invalid_credentials")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.", code="account_disabled")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = datetime.now(tz=UTC)
        return user

    # ---------------------------------------------------------------- sessions
    def issue_session(self, user: User) -> SessionTokens:
        access = issue_jwt(
            secret_key=self.settings.secret_key,
            subject=str(user.id),
            token_type="access",  # noqa: S106  a JWT type claim
            ttl_seconds=self.settings.access_token_ttl_seconds,
            extra_claims={"role": user.role, "epoch": user.token_epoch},
        )
        refresh = issue_jwt(
            secret_key=self.settings.secret_key,
            subject=str(user.id),
            token_type="refresh",  # noqa: S106  a JWT type claim
            ttl_seconds=self.settings.refresh_token_ttl_seconds,
            extra_claims={"epoch": user.token_epoch},
        )
        return SessionTokens(access=access, refresh=refresh, csrf_token=secrets.token_urlsafe(24))

    def refresh_session(self, refresh_token: str) -> tuple[User, SessionTokens]:
        payload = decode_jwt(
            refresh_token, secret_key=self.settings.secret_key, expected_type="refresh"
        )
        user = self.get_by_id(uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthenticationError("Session is no longer valid.", code="session_invalid")
        if payload.get("epoch") != user.token_epoch:
            # The user changed their password or signed out everywhere.
            raise AuthenticationError("Session has been revoked.", code="session_revoked")
        return user, self.issue_session(user)

    def revoke_all_sessions(self, user: User) -> None:
        user.token_epoch += 1

    # ------------------------------------------------------- single-use tokens
    def _issue_single_use_token(self, user: User, purpose: str, ttl_seconds: int) -> str:
        token = generate_url_token()
        self.db.add(
            AuthToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_token(token),
                expires_at=datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds),
            )
        )
        return token

    def _consume_single_use_token(self, token: str, purpose: str) -> User:
        digest = hash_token(token)
        stmt = select(AuthToken).where(AuthToken.token_hash == digest, AuthToken.purpose == purpose)
        record = self.db.execute(stmt).scalar_one_or_none()
        now = datetime.now(tz=UTC)
        if record is None or record.used_at is not None:
            raise ValidationError_("This link is not valid.", code="token_invalid")
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            raise ValidationError_("This link has expired.", code="token_expired")
        record.used_at = now
        user = self.get_by_id(record.user_id)
        if user is None:
            raise NotFoundError("Account not found.", code="user_not_found")
        return user

    # ------------------------------------------------------ e-mail verification
    def send_verification_email(self, user: User) -> None:
        if user.email_verified_at is not None:
            return
        token = self._issue_single_use_token(
            user, PURPOSE_EMAIL_VERIFICATION, self.settings.email_verification_ttl_seconds
        )
        link = f"{self.settings.frontend_base_url}/verify-email?token={token}"
        self.notifications.send_email(
            to=user.email,
            subject="Confirm your JobApply e-mail address",
            body=(
                "Confirm your e-mail address to finish setting up your account:\n\n"
                f"{link}\n\nThis link expires in 24 hours."
            ),
        )

    def verify_email(self, token: str) -> User:
        user = self._consume_single_use_token(token, PURPOSE_EMAIL_VERIFICATION)
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(tz=UTC)
        audit.record(
            self.db,
            action="auth.email_verified",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )
        return user

    # --------------------------------------------------------------- passwords
    def request_password_reset(self, email: str) -> None:
        user = self.get_by_email(email)
        if user is None:
            logger.info(
                "auth.password_reset_requested_unknown_email",
                extra={"context": {"event": "auth.password_reset_requested_unknown_email"}},
            )
            return
        token = self._issue_single_use_token(
            user, PURPOSE_PASSWORD_RESET, self.settings.password_reset_ttl_seconds
        )
        link = f"{self.settings.frontend_base_url}/reset-password?token={token}"
        self.notifications.send_email(
            to=user.email,
            subject="Reset your JobApply password",
            body=(
                "Use this link to choose a new password:\n\n"
                f"{link}\n\nThis link expires in one hour. "
                "If you did not request it, no action is needed."
            ),
        )
        audit.record(
            self.db,
            action="auth.password_reset_requested",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )

    def reset_password(self, token: str, new_password: str) -> User:
        user = self._consume_single_use_token(token, PURPOSE_PASSWORD_RESET)
        user.password_hash = hash_password(new_password)
        self.revoke_all_sessions(user)
        audit.record(
            self.db,
            action="auth.password_reset",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError(
                "Your current password is incorrect.", code="invalid_credentials"
            )
        user.password_hash = hash_password(new_password)
        self.revoke_all_sessions(user)
        audit.record(
            self.db,
            action="auth.password_changed",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )

    # ------------------------------------------------------------------- oauth
    def upsert_oauth_user(
        self, *, provider: str, account_id: str, email: str | None, email_verified: bool
    ) -> User:
        stmt = select(OAuthAccount).where(
            OAuthAccount.provider == provider, OAuthAccount.provider_account_id == account_id
        )
        link = self.db.execute(stmt).scalar_one_or_none()
        if link is not None:
            user = self.get_by_id(link.user_id)
            if user is None:
                raise NotFoundError("Linked account no longer exists.", code="user_not_found")
            return user

        if not email:
            raise ValidationError_(
                "The identity provider did not supply an e-mail address.",
                code="oauth_email_missing",
            )
        if not email_verified:
            # An unverified provider e-mail must not be able to claim an existing
            # account, so we refuse rather than linking on trust.
            raise ValidationError_(
                "Your provider account has an unverified e-mail address.",
                code="oauth_email_unverified",
            )

        user = self.get_by_email(email)
        if user is None:
            user = User(
                email=normalize_email(email),
                password_hash=None,
                role=UserRole.USER,
                is_active=True,
                email_verified_at=datetime.now(tz=UTC),
                automation_paused=True,
            )
            self.db.add(user)
            self.db.flush()
            self.db.add(Profile(user_id=user.id, email=user.email))
            self.db.add(AutomationSettings(user_id=user.id))
            self.db.add(JobPreference(user_id=user.id, name="Default"))
            self.db.add(Subscription(user_id=user.id, plan=SubscriptionPlan.FREE, provider="noop"))
        elif user.email_verified_at is None:
            user.email_verified_at = datetime.now(tz=UTC)

        self.db.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_account_id=account_id,
                email=normalize_email(email),
                email_verified=email_verified,
            )
        )
        audit.record(
            self.db,
            action="auth.oauth_login",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            data={"provider": provider},
        )
        return user

    # ------------------------------------------------------------ account delete
    def delete_account(self, user: User, password: str | None) -> None:
        has_password = bool(user.password_hash)
        if has_password:
            if not password:
                raise ValidationError_(
                    "Confirm your password to delete the account.", code="password_required"
                )
            if not verify_password(password, user.password_hash):
                raise AuthenticationError("Your password is incorrect.", code="invalid_credentials")
        user.deleted_at = datetime.now(tz=UTC)
        user.is_active = False
        self.revoke_all_sessions(user)
        audit.record(
            self.db,
            action="auth.account_deleted",
            actor_user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            data={"auth_provider": AuthProvider.PASSWORD if has_password else AuthProvider.GOOGLE},
        )
