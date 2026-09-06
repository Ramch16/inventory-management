"""Cross-cutting platform tables: settings, notifications, billing and the credential
vault."""

from __future__ import annotations

import uuid
from datetime import datetime

from jobapply_shared.enums import SubscriptionPlan, SubscriptionStatus
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from jobapply_db.base import (
    Base,
    JSONColumn,
    TimestampMixin,
    UUIDColumn,
    UUIDPrimaryKeyMixin,
)


class AutomationSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user automation policy. Automation stays off until the user completes
    onboarding and explicitly enables it."""

    __tablename__ = "automation_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_automation_settings_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_submit_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_review_before_submit: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    allow_browser_verification: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generate_cover_letters: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    daily_application_limit: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    hourly_application_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    min_delay_seconds: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    max_delay_seconds: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    min_match_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)

    default_resume_template: Mapped[str] = mapped_column(
        String(40), default="ats_classic", nullable=False
    )
    resume_max_pages: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    confidence_auto_threshold: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)
    confidence_review_threshold: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)

    notification_preferences: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))
    payload: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Credential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted vault entry.

    Prefer OAuth where a provider supports it; passwords are only collected when the
    user explicitly adds them, and the ciphertext is decrypted solely inside an
    automation worker.
    """

    __tablename__ = "credentials"
    __table_args__ = (Index("ix_credentials_user_kind", "user_id", "kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    #: AES-256-GCM ciphertext. Excluded from every response model.
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscriptions_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(20), default=SubscriptionPlan.FREE, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=SubscriptionStatus.ACTIVE, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), default="noop", nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(String(120))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(120))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UsageRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metered usage per billing period (applications, AI tokens, resume renders)."""

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "metric", name="uq_usage_records_period_metric"),
        Index("ix_usage_records_user_period", "user_id", "period"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
