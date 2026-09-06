"""Applications and everything the automation run produces: steps, questions and
answers, browser sessions, interventions, logs and queue tasks."""

from __future__ import annotations

import uuid
from datetime import datetime

from jobapply_shared.enums import ApplicationStatus, InterventionStatus, TaskStatus
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobapply_db.base import (
    Base,
    JSONColumn,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDColumn,
    UUIDPrimaryKeyMixin,
)


class Application(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "applications"
    __table_args__ = (
        # One application per user per job, enforced in the database rather than only
        # in code, so a race between two workers cannot produce a double submission.
        UniqueConstraint("user_id", "dedupe_hash", name="uq_applications_user_dedupe"),
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("resume_versions.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(40), default=ApplicationStatus.APPROVED, nullable=False
    )
    run_state: Mapped[str | None] = mapped_column(String(40))
    auto_submit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    detected_ats: Mapped[str | None] = mapped_column(String(40))
    apply_url: Mapped[str | None] = mapped_column(String(1000))

    #: sha256 over normalized company + title + employer job id + apply url.
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Only set when a confirmation was actually observed. Absent confirmation the
    #: status is SUBMISSION_UNCONFIRMED — never a fabricated "Applied".
    confirmation_id: Mapped[str | None] = mapped_column(String(255))
    confirmation_url: Mapped[str | None] = mapped_column(String(1000))
    confirmation_text: Mapped[str | None] = mapped_column(Text)
    confirmation_screenshot_key: Mapped[str | None] = mapped_column(String(500))
    confirmation_source: Mapped[str | None] = mapped_column(String(40))

    failure_reason: Mapped[str | None] = mapped_column(String(40))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    match_score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="automation", nullable=False)

    steps: Mapped[list[ApplicationStep]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    questions: Mapped[list[ApplicationQuestion]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    interventions: Mapped[list[Intervention]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Timeline entry for one workflow transition or automation action."""

    __tablename__ = "application_steps"
    __table_args__ = (Index("ix_application_steps_app_created", "application_id", "created_at"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    screenshot_key: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)

    application: Mapped[Application] = relationship(back_populates="steps")


class ApplicationQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_questions"
    __table_args__ = (Index("ix_application_questions_app", "application_id", "created_at"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_id: Mapped[str] = mapped_column(String(255), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    context_text: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="questions")
    answer: Mapped[ApplicationAnswer] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class ApplicationAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_answers"
    __table_args__ = (UniqueConstraint("question_id", name="uq_application_answers_question"),)

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn,
        ForeignKey("application_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    #: Profile/experience/skill record ids that ground this answer.
    source_ids: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_user_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(Text)

    question: Mapped[ApplicationQuestion] = relationship(back_populates="answer")


class BrowserSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One isolated Playwright context.

    ``state_blob`` is AES-GCM ciphertext and is never returned by the API. Sessions are
    destroyed at the end of a run unless parked for user verification, in which case a
    reaper removes them at ``expires_at``.
    """

    __tablename__ = "browser_sessions"
    __table_args__ = (Index("ix_browser_sessions_app_state", "application_id", "state"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="SET NULL")
    )
    ats: Mapped[str | None] = mapped_column(String(40))
    state: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    current_url: Mapped[str | None] = mapped_column(String(1000))
    state_blob: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Intervention(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A point where the platform stopped and asked the user to take over.

    Created for CAPTCHA, MFA/OTP, legal attestations, low-confidence answers,
    unsupported forms and missing data. The platform never attempts to satisfy these
    itself.
    """

    __tablename__ = "interventions"
    __table_args__ = (Index("ix_interventions_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=InterventionStatus.OPEN, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(1000))
    page_title: Mapped[str | None] = mapped_column(String(500))
    screenshot_key: Mapped[str | None] = mapped_column(String(500))
    #: Questions/fields needing a human answer, with the automation's best draft.
    payload: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(40))

    application: Mapped[Application] = relationship(back_populates="interventions")


class AutomationLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured automation event, mirrored from the JSON log stream so the user can
    see what happened without shell access. Never contains credentials or OTP codes."""

    __tablename__ = "automation_logs"
    __table_args__ = (Index("ix_automation_logs_app_created", "application_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="SET NULL")
    )
    event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), default="INFO", nullable=False)
    status: Mapped[str | None] = mapped_column(String(30))
    ats: Mapped[str | None] = mapped_column(String(40))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    screenshot_key: Mapped[str | None] = mapped_column(String(500))
    stack_trace: Mapped[str | None] = mapped_column(Text)


class ApplicationTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable mirror of a queued automation task, so the dashboard can show queue
    state even if the broker is flushed."""

    __tablename__ = "application_tasks"
    __table_args__ = (
        Index("ix_application_tasks_status_priority", "status", "priority"),
        Index("ix_application_tasks_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="SET NULL")
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="apply", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.QUEUED, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    broker_task_id: Mapped[str | None] = mapped_column(String(120))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(40))
    failure_detail: Mapped[str | None] = mapped_column(Text)
