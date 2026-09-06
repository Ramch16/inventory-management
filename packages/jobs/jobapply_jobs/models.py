"""Job discovery and matching contracts.

``RawJob`` is whatever a source gave us. ``NormalizedJob`` is the single shape the
rest of the platform works with. Nothing between the two invents a fact: a field the
posting does not state stays ``None``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from jobapply_shared.enums import EmploymentType, MatchRecommendation, RemoteType
from pydantic import BaseModel, ConfigDict, Field


class JobQuery(BaseModel):
    """What to ask a source for."""

    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_only: bool = False
    posted_within_days: int | None = None
    limit: int = 100


class RawJob(BaseModel):
    """A posting exactly as the source returned it."""

    model_config = ConfigDict(extra="forbid")

    source_slug: str
    source_job_id: str
    company: str
    title: str
    location: str | None = None
    description: str | None = None
    apply_url: str | None = None
    posting_url: str | None = None
    posted_at: datetime | None = None
    employment_type: str | None = None
    remote_hint: str | None = None
    salary_text: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedJob(BaseModel):
    """The canonical job shape stored in ``jobs``."""

    model_config = ConfigDict(extra="forbid")

    source_slug: str
    source_job_id: str
    company_name: str
    normalized_company: str
    title: str
    normalized_title: str
    location: str | None = None
    normalized_location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    description: str | None = None
    requirements: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: str | None = None
    experience_required_years: float | None = None
    seniority: str | None = None
    #: Verbatim sponsorship language from the posting, or None. Never inferred.
    sponsorship_information: str | None = None
    sponsorship_offered: bool | None = None
    apply_url: str | None = None
    posting_url: str | None = None
    detected_ats: str | None = None
    posted_at: datetime | None = None
    expiration_date: date | None = None
    dedupe_key: str
    content_hash: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------------- matching
class MatchWeights(BaseModel):
    """Configurable component weights. They are normalized before use, so a partial
    override cannot silently change the scale."""

    model_config = ConfigDict(extra="forbid")

    skills: float = 0.30
    experience: float = 0.25
    title: float = 0.15
    education: float = 0.10
    location: float = 0.10
    authorization: float = 0.10

    def normalized(self) -> dict[str, float]:
        values = self.model_dump()
        total = sum(values.values())
        if total <= 0:
            raise ValueError("Match weights must sum to a positive number")
        return {key: value / total for key, value in values.items()}


class MatchProfile(BaseModel):
    """The user-side inputs to scoring. Every field comes from approved profile data."""

    model_config = ConfigDict(extra="forbid")

    titles: list[str] = Field(default_factory=list)
    current_title: str | None = None
    years_experience: float | None = None
    skills: list[str] = Field(default_factory=list)
    skill_years: dict[str, float] = Field(default_factory=dict)
    education_level: str | None = None
    locations: list[str] = Field(default_factory=list)
    remote_preference: RemoteType | None = None
    salary_min: int | None = None
    open_to_relocation: bool | None = None
    requires_sponsorship_now: bool | None = None
    requires_sponsorship_future: bool | None = None
    authorization_country: str | None = None
    excluded_companies: list[str] = Field(default_factory=list)
    excluded_titles: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int
    skills_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    location_score: int = 0
    authorization_score: int = 0
    title_score: int = 0
    seniority_score: int = 0
    recommendation: MatchRecommendation
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    #: Reasons a person should look before applying.
    risks: list[str] = Field(default_factory=list)
    #: True when the user demonstrably fails a stated hard requirement.
    hard_requirement_failed: bool = False
    explanation: str = ""
    weights: dict[str, float] = Field(default_factory=dict)


class DuplicateVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_duplicate: bool
    reason: str | None = None
    similarity: float = 0.0
    matched_id: str | None = None
