"""Structured resume contracts.

These models are the boundary between "what the user actually told us" (``ParsedResume``,
profile records) and "what we generated" (``TailoredResume``). Everything generated
carries provenance so it can be checked against the source records.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContactInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


class ParsedPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    date_text: str | None = None
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class ParsedEducation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: float | None = None
    date_text: str | None = None


class ParsedCertification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    issuer: str | None = None
    issued_on: date | None = None


class ParsedProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class ParsedResume(BaseModel):
    """The structured view of an uploaded or pasted resume.

    Parsing is best effort and explicitly *suggestive*: nothing here is treated as
    confirmed profile data until the user reviews it. Legally significant facts
    (work authorization, sponsorship, clearances) are never extracted here at all.
    """

    model_config = ConfigDict(extra="forbid")

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    positions: list[ParsedPosition] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    certifications: list[ParsedCertification] = Field(default_factory=list)
    projects: list[ParsedProject] = Field(default_factory=list)
    raw_text: str = ""
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.positions or self.education or self.skills or self.summary)


# --------------------------------------------------------------------------- generated
class ProvenanceRecord(BaseModel):
    """Traceability for one generated statement."""

    model_config = ConfigDict(extra="forbid")

    generated_text: str
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    section: str | None = None


class TailoredBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class TailoredExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experience_id: str
    company: str
    title: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredEducation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    education_id: str
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    end_date: date | None = None
    gpa: float | None = None


class TailoredProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    highlights: list[TailoredBullet] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class TailoredResume(BaseModel):
    """A job-specific rendition assembled only from approved source records."""

    model_config = ConfigDict(extra="forbid")

    contact: ContactInfo
    summary: str | None = None
    summary_source_ids: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[TailoredExperience] = Field(default_factory=list)
    education: list[TailoredEducation] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[TailoredProject] = Field(default_factory=list)
    template: str = "ats_classic"
    max_pages: int = 2
    provenance: list[ProvenanceRecord] = Field(default_factory=list)


class ResumeScore(BaseModel):
    """Quality gate applied before a tailored resume is rendered and uploaded."""

    model_config = ConfigDict(extra="forbid")

    ats_readability: int = 0
    keyword_coverage: int = 0
    skill_coverage: int = 0
    experience_relevance: int = 0
    formatting_quality: int = 0
    factual_consistency: int = 0
    overall: int = 0
    notes: list[str] = Field(default_factory=list)


class TruthVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    matched_source_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class TruthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    verdicts: list[TruthVerdict] = Field(default_factory=list)
    rejected_statements: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


SourceKind = Literal["experience", "education", "skill", "certification", "project", "profile"]


class SourceRecord(BaseModel):
    """One approved fact the generator is allowed to draw on."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: SourceKind
    text: str
    entities: list[str] = Field(default_factory=list)
    numbers: dict[str, float] = Field(default_factory=dict)
