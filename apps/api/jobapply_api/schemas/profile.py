"""Profile, education, experience, skills and certification models.

Work-authorization fields live in their own request model and their own endpoint: they
are legally significant, so they are never set as a side effect of another update and
never derived from an uploaded resume.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from jobapply_shared.enums import (
    AuthorizationType,
    EmploymentType,
    RemoteType,
    SkillCategory,
)
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from jobapply_api.schemas.common import ORMModel


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    linkedin_url: str | None = Field(default=None, max_length=500)
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)

    current_title: str | None = Field(default=None, max_length=200)
    years_experience: float | None = Field(default=None, ge=0, le=70)
    summary: str | None = Field(default=None, max_length=4000)
    desired_titles: list[str] | None = None
    desired_industries: list[str] | None = None
    desired_employment_types: list[EmploymentType] | None = None
    desired_locations: list[str] | None = None
    remote_preference: RemoteType | None = None
    salary_min: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    open_to_relocation: bool | None = None

    @model_validator(mode="after")
    def check_salary_range(self) -> ProfileUpdate:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot exceed salary_max")
        return self


class WorkAuthorizationUpdate(BaseModel):
    """Explicit, user-declared work authorization.

    Every field is required: a partially answered authorization block is treated as
    undeclared, and undeclared authorization blocks automated submission.
    """

    model_config = ConfigDict(extra="forbid")

    authorization_country: str = Field(min_length=2, max_length=120)
    authorization_type: AuthorizationType
    authorization_expires_on: date | None = None
    requires_sponsorship_now: bool
    requires_sponsorship_future: bool
    confirmed: bool = Field(description="The user affirms these answers are accurate")

    @model_validator(mode="after")
    def require_confirmation(self) -> WorkAuthorizationUpdate:
        if not self.confirmed:
            raise ValueError("Work authorization must be explicitly confirmed by the user")
        return self


class WorkAuthorizationResponse(ORMModel):
    authorization_country: str | None = None
    authorization_type: str | None = None
    authorization_expires_on: date | None = None
    requires_sponsorship_now: bool | None = None
    requires_sponsorship_future: bool | None = None
    work_authorization_confirmed_at: date | None = None
    declared: bool = False


class ProfileResponse(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    preferred_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    current_title: str | None = None
    years_experience: float | None = None
    summary: str | None = None
    desired_titles: list[str] | None = None
    desired_industries: list[str] | None = None
    desired_employment_types: list[str] | None = None
    desired_locations: list[str] | None = None
    remote_preference: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    open_to_relocation: bool | None = None
    work_authorization: WorkAuthorizationResponse | None = None
    updated_at: datetime


# ------------------------------------------------------------------------- education
class EducationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str = Field(min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=180)
    field_of_study: str | None = Field(default=None, max_length=180)
    location: str | None = Field(default=None, max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    gpa: float | None = Field(default=None, ge=0, le=5)
    relevant_coursework: list[str] = Field(default_factory=list)
    sort_order: int = 0

    @model_validator(mode="after")
    def check_dates(self) -> EducationBase:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        return self


class EducationCreate(EducationBase):
    pass


class EducationResponse(ORMModel, EducationBase):
    id: uuid.UUID


# ------------------------------------------------------------------------ experience
class ExperienceBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=180)
    employment_type: EmploymentType | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=8000)
    accomplishments: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    sort_order: int = 0

    @model_validator(mode="after")
    def check_dates(self) -> ExperienceBase:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if self.is_current and self.end_date:
            raise ValueError("A current position cannot have an end date")
        return self


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceResponse(ORMModel, ExperienceBase):
    id: uuid.UUID


# ---------------------------------------------------------------------------- skills
class SkillBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    category: SkillCategory = SkillCategory.OTHER
    years_experience: float | None = Field(default=None, ge=0, le=70)
    proficiency: str | None = Field(default=None, max_length=20)
    is_verified: bool = True
    last_used_year: int | None = Field(default=None, ge=1950, le=2100)


class SkillCreate(SkillBase):
    pass


class SkillResponse(ORMModel, SkillBase):
    id: uuid.UUID


# -------------------------------------------------------------------- certifications
class CertificationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    issuer: str | None = Field(default=None, max_length=255)
    issued_on: date | None = None
    expires_on: date | None = None
    credential_id: str | None = Field(default=None, max_length=180)
    credential_url: str | None = Field(default=None, max_length=500)
    is_verified: bool = True


class CertificationCreate(CertificationBase):
    pass


class CertificationResponse(ORMModel, CertificationBase):
    id: uuid.UUID


# ------------------------------------------------------------------------ completeness
class ProfileCompleteness(BaseModel):
    score: int
    missing: list[str]
    blocks_automation: list[str]
    ready_for_automation: bool
