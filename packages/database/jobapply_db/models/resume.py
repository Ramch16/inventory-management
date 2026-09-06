"""Master resumes and the per-job tailored versions generated from them.

The uploaded original is immutable: tailoring always writes a new ``ResumeVersion``
row and new storage objects, so the user's own document is never rewritten.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from jobapply_shared.enums import ResumeTemplate
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobapply_db.base import (
    Base,
    JSONColumn,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDColumn,
    UUIDPrimaryKeyMixin,
)


class Resume(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "resumes"
    __table_args__ = (Index("ix_resumes_user_master", "user_id", "is_master"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Immutable original as uploaded.
    original_filename: Mapped[str | None] = mapped_column(String(255))
    original_content_type: Mapped[str | None] = mapped_column(String(120))
    original_size_bytes: Mapped[int | None] = mapped_column(Integer)
    original_storage_key: Mapped[str | None] = mapped_column(String(500))
    original_checksum: Mapped[str | None] = mapped_column(String(64))

    #: Extracted plain text and the structured parse (contact, skills, positions,
    #: education, certifications, projects).
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list[ResumeVersion]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class ResumeVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """One tailored rendition of a master resume for one job."""

    __tablename__ = "resume_versions"
    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", "version", name="uq_resume_versions_job_version"),
        Index("ix_resume_versions_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDColumn, ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    template: Mapped[str] = mapped_column(
        String(40), default=ResumeTemplate.ATS_CLASSIC, nullable=False
    )

    #: Structured tailored document (summary, skills, experience bullets, projects).
    content: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)
    #: Per-statement provenance: {"generated_text", "source_ids", "confidence"}.
    provenance: Mapped[list | None] = mapped_column(JSONColumn, default=list)
    #: ResumeScore: ats, keywords, skills, experience, formatting, factual, overall.
    quality: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)

    docx_storage_key: Mapped[str | None] = mapped_column(String(500))
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500))
    cover_letter_text: Mapped[str | None] = mapped_column(Text)
    cover_letter_storage_key: Mapped[str | None] = mapped_column(String(500))

    ai_provider: Mapped[str | None] = mapped_column(String(40))
    ai_model: Mapped[str | None] = mapped_column(String(120))
    truth_report: Mapped[dict | None] = mapped_column(JSONColumn, default=dict)

    resume: Mapped[Resume] = relationship(back_populates="versions")
