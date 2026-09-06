"""Job, match and preference models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from jobapply_shared.enums import EmploymentType, MatchRecommendation, RemoteType
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobapply_api.schemas.common import ORMModel


class JobSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list, max_length=20)
    titles: list[str] = Field(default_factory=list, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    remote_only: bool = False
    limit: int = Field(default=100, ge=1, le=500)
    #: Restrict to specific configured sources; empty means every enabled source.
    sources: list[str] = Field(default_factory=list, max_length=10)
    #: Score the newly discovered jobs against the caller's profile straight away.
    score_after_discovery: bool = True


class DiscoveryResult(BaseModel):
    fetched: int
    created: int
    duplicates: int
    scored: int
    errors: list[str] = Field(default_factory=list)


class MatchSummary(ORMModel):
    overall_score: int
    skills_score: int
    experience_score: int
    education_score: int
    location_score: int
    authorization_score: int
    title_score: int
    seniority_score: int
    recommendation: MatchRecommendation
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    hard_requirement_failed: bool = False
    explanation: str | None = None
    user_decision: str | None = None


class JobCard(ORMModel):
    """List view: everything a job card shows, and nothing more."""

    id: uuid.UUID
    company_name: str
    title: str
    location: str | None = None
    remote_type: RemoteType
    employment_type: EmploymentType
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    detected_ats: str | None = None
    apply_url: str | None = None
    status: str
    discovered_at: datetime
    expiration_date: date | None = None
    sponsorship_offered: bool | None = None
    match: MatchSummary | None = None
    application_status: str | None = None


class JobDetail(JobCard):
    description: str | None = None
    requirements: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: str | None = None
    experience_required_years: float | None = None
    seniority: str | None = None
    sponsorship_information: str | None = None
    posting_url: str | None = None
    source_slug: str | None = None


class JobDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(approve|skip)$")
    note: str | None = Field(default=None, max_length=500)


class MatchWeightsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: float = Field(default=0.30, ge=0, le=1)
    experience: float = Field(default=0.25, ge=0, le=1)
    title: float = Field(default=0.15, ge=0, le=1)
    education: float = Field(default=0.10, ge=0, le=1)
    location: float = Field(default=0.10, ge=0, le=1)
    authorization: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def check_positive_total(self) -> MatchWeightsInput:
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one match weight must be greater than zero")
        return self


class JobPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    target_titles: list[str] | None = None
    excluded_titles: list[str] | None = None
    target_companies: list[str] | None = None
    excluded_companies: list[str] | None = None
    locations: list[str] | None = None
    remote_preference: RemoteType | None = None
    salary_min: int | None = Field(default=None, ge=0, le=10_000_000)
    experience_min_years: float | None = Field(default=None, ge=0, le=70)
    experience_max_years: float | None = Field(default=None, ge=0, le=70)
    employment_types: list[EmploymentType] | None = None
    industries: list[str] | None = None
    keywords: list[str] | None = None
    excluded_keywords: list[str] | None = None
    requires_sponsorship: bool | None = None
    match_weights: MatchWeightsInput | None = None

    @model_validator(mode="after")
    def check_experience_range(self) -> JobPreferenceUpdate:
        if (
            self.experience_min_years is not None
            and self.experience_max_years is not None
            and self.experience_min_years > self.experience_max_years
        ):
            raise ValueError("experience_min_years cannot exceed experience_max_years")
        return self


class JobPreferenceResponse(ORMModel):
    id: uuid.UUID
    name: str
    is_active: bool
    target_titles: list[str] | None = None
    excluded_titles: list[str] | None = None
    target_companies: list[str] | None = None
    excluded_companies: list[str] | None = None
    locations: list[str] | None = None
    remote_preference: str | None = None
    salary_min: int | None = None
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    employment_types: list[str] | None = None
    industries: list[str] | None = None
    keywords: list[str] | None = None
    excluded_keywords: list[str] | None = None
    requires_sponsorship: bool | None = None
    match_weights: dict | None = None
    updated_at: datetime


class JobSourceResponse(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    kind: str
    enabled: bool
    last_run_at: datetime | None = None
    last_error: str | None = None
