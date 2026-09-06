"""Job sources, companies, normalized jobs, per-user match results and preferences."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from jobapply_shared.enums import JobStatus, RemoteType
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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


class JobSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A place jobs come from: a public feed, an employer careers page the user asked
    us to watch, or a manual paste."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("slug", name="uq_job_sources_slug"),)

    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    jobs: Mapped[list[Job]] = relationship(back_populates="source")


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_companies_normalized_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255))
    careers_url: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str | None] = mapped_column(String(180))
    size: Mapped[str | None] = mapped_column(String(60))

    jobs: Mapped[list[Job]] = relationship(back_populates="company")


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_jobs_source_job"),
        UniqueConstraint("dedupe_key", name="uq_jobs_dedupe_key"),
        Index("ix_jobs_company_title", "company_id", "normalized_title"),
        Index("ix_jobs_normalized_company_title", "normalized_company", "normalized_title"),
        Index("ix_jobs_status_discovered", "status", "discovered_at"),
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("job_sources.id", ondelete="SET NULL"), index=True
    )
    source_job_id: Mapped[str | None] = mapped_column(String(255))
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Denormalized so duplicate detection can compare without joining companies.
    normalized_company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    normalized_location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[str] = mapped_column(String(20), default=RemoteType.UNKNOWN, nullable=False)
    employment_type: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(20))

    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    preferred_qualifications: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    skills: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    education: Mapped[str | None] = mapped_column(String(255))
    experience_required_years: Mapped[float | None] = mapped_column(Numeric(4, 1))
    seniority: Mapped[str | None] = mapped_column(String(40))
    #: What the posting itself says about sponsorship, verbatim. Never inferred.
    sponsorship_information: Mapped[str | None] = mapped_column(Text)
    sponsorship_offered: Mapped[bool | None] = mapped_column(Boolean)

    apply_url: Mapped[str | None] = mapped_column(String(1000))
    posting_url: Mapped[str | None] = mapped_column(String(1000))
    detected_ats: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[str] = mapped_column(String(20), default=JobStatus.DISCOVERED, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiration_date: Mapped[date | None] = mapped_column(Date)

    #: sha256(company|title|location|source_job_id) — the exact-duplicate key.
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: sha256 of the description, used to detect re-posts with an identical body.
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)

    source: Mapped[JobSource | None] = relationship(back_populates="jobs")
    company: Mapped[Company | None] = relationship(back_populates="jobs")
    matches: Mapped[list[JobMatch]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def is_expired(self) -> bool:
        return self.expiration_date is not None and self.expiration_date < date.today()


class JobMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
        Index("ix_job_matches_user_score", "user_id", "overall_score"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skills_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    experience_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    education_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    authorization_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seniority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_skills: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    missing_skills: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    #: Hard-requirement failures and other reasons a human should look before applying.
    risks: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    hard_requirement_failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    weights: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    user_decision: Mapped[str | None] = mapped_column(String(20))

    job: Mapped[Job] = relationship(back_populates="matches")


class JobPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One saved search / targeting profile per user (multiple allowed)."""

    __tablename__ = "job_preferences"
    __table_args__ = (Index("ix_job_preferences_user_active", "user_id", "is_active"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), default="Default", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    target_titles: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    excluded_titles: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    target_companies: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    excluded_companies: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    locations: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    remote_preference: Mapped[str | None] = mapped_column(String(20))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    experience_min_years: Mapped[float | None] = mapped_column(Numeric(4, 1))
    experience_max_years: Mapped[float | None] = mapped_column(Numeric(4, 1))
    employment_types: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    industries: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    keywords: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    excluded_keywords: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    requires_sponsorship: Mapped[bool | None] = mapped_column(Boolean)
    match_weights: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
