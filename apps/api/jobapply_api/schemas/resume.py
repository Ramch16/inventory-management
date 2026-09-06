"""Resume upload, parse and version models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from jobapply_shared.enums import ResumeTemplate
from pydantic import BaseModel, ConfigDict, Field

from jobapply_api.schemas.common import ORMModel


class ResumeTextCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=40, max_length=200_000)
    set_as_master: bool = True


class ResumeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)


class ParsedContact(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


class ParsedPositionOut(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)


class ParsedEducationOut(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    end_date: date | None = None
    gpa: float | None = None


class ParsedResumeOut(BaseModel):
    contact: ParsedContact = Field(default_factory=ParsedContact)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    positions: list[ParsedPositionOut] = Field(default_factory=list)
    education: list[ParsedEducationOut] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumeResponse(ORMModel):
    id: uuid.UUID
    title: str
    source_kind: str
    is_master: bool
    original_filename: str | None = None
    original_content_type: str | None = None
    original_size_bytes: int | None = None
    parse_status: str
    parse_error: str | None = None
    parsed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    structured: ParsedResumeOut | None = None


class ResumeSummary(ORMModel):
    """List view: no parsed body, so listing a hundred resumes stays cheap."""

    id: uuid.UUID
    title: str
    source_kind: str
    is_master: bool
    original_filename: str | None = None
    parse_status: str
    created_at: datetime


class ResumeImportRequest(BaseModel):
    """Copy selected parsed records into the profile as approved source data."""

    model_config = ConfigDict(extra="forbid")

    import_contact: bool = True
    import_summary: bool = True
    import_skills: bool = True
    import_experience: bool = True
    import_education: bool = True
    import_certifications: bool = True


class ResumeImportResult(BaseModel):
    experience_added: int = 0
    education_added: int = 0
    skills_added: int = 0
    certifications_added: int = 0
    profile_updated: bool = False
    #: Imported skills land unverified: the user confirms them during onboarding.
    notes: list[str] = Field(default_factory=list)


class ResumeVersionResponse(ORMModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID | None = None
    version: int
    label: str | None = None
    template: ResumeTemplate
    quality: dict | None = None
    docx_storage_key: str | None = None
    pdf_storage_key: str | None = None
    created_at: datetime


class DownloadResponse(BaseModel):
    url: str
    expires_in: int
