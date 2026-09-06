"""Application, intervention and automation-settings models."""

from __future__ import annotations

import uuid
from datetime import datetime

from jobapply_shared.enums import ApplicationStatus, ResumeTemplate
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobapply_api.schemas.common import ORMModel


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: uuid.UUID
    #: Overrides the account default for this one application.
    auto_submit: bool | None = None
    #: Generate the tailored resume first if one does not exist yet.
    generate_resume: bool = True


class ApplicationSummary(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: ApplicationStatus
    run_state: str | None = None
    auto_submit: bool
    requires_review: bool
    detected_ats: str | None = None
    match_score: int | None = None
    attempts: int
    failure_reason: str | None = None
    submitted_at: datetime | None = None
    created_at: datetime
    company_name: str | None = None
    title: str | None = None
    open_interventions: int = 0


class StepOut(ORMModel):
    id: uuid.UUID
    name: str
    status: str
    message: str | None = None
    duration_ms: int | None = None
    data: dict | None = None
    created_at: datetime


class QuestionOut(BaseModel):
    id: uuid.UUID
    field_id: str
    label: str | None = None
    question: str | None = None
    field_type: str
    category: str
    required: bool
    is_sensitive: bool
    options: list[dict] = Field(default_factory=list)
    answer: str | None = None
    confidence: float = 0.0
    source: str | None = None
    requires_review: bool = True
    approved_by_user_at: datetime | None = None
    reason: str | None = None


class AutomationLogOut(ORMModel):
    id: uuid.UUID
    event: str
    level: str
    status: str | None = None
    ats: str | None = None
    duration_ms: int | None = None
    message: str | None = None
    data: dict | None = None
    created_at: datetime


class ApplicationDetail(ApplicationSummary):
    apply_url: str | None = None
    confirmation_id: str | None = None
    confirmation_url: str | None = None
    confirmation_text: str | None = None
    failure_detail: str | None = None
    notes: str | None = None
    completed_at: datetime | None = None
    resume_version_id: uuid.UUID | None = None
    resume_template: ResumeTemplate | None = None
    resume_quality: dict | None = None
    cover_letter_text: str | None = None
    steps: list[StepOut] = Field(default_factory=list)
    questions: list[QuestionOut] = Field(default_factory=list)
    logs: list[AutomationLogOut] = Field(default_factory=list)
    can_retry: bool = False


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=2000)


class InterventionOut(ORMModel):
    id: uuid.UUID
    application_id: uuid.UUID
    type: str
    status: str
    current_step: str | None = None
    reason: str
    page_url: str | None = None
    page_title: str | None = None
    payload: dict | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    company_name: str | None = None
    title: str | None = None
    screenshot_url: str | None = None
    #: True when the user has to act in a browser themselves (CAPTCHA, MFA, sign-in).
    requires_browser: bool = False


class InterventionContinue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Answers keyed by the form's field id.
    answers: dict[str, str] = Field(default_factory=dict)
    #: A one-time code. Passed to the worker in memory and never stored.
    otp_code: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def require_something(self) -> InterventionContinue:
        if not self.answers and not self.otp_code:
            # Continuing with nothing is valid for a CAPTCHA the user just solved.
            return self
        return self


class AutomationSettingsOut(ORMModel):
    id: uuid.UUID
    enabled: bool
    auto_submit_enabled: bool
    require_review_before_submit: bool
    allow_browser_verification: bool
    generate_cover_letters: bool
    daily_application_limit: int
    hourly_application_limit: int
    min_delay_seconds: int
    max_delay_seconds: int
    min_match_score: int
    default_resume_template: ResumeTemplate
    resume_max_pages: int
    confidence_auto_threshold: float
    confidence_review_threshold: float
    notification_preferences: dict | None = None
    paused_at: datetime | None = None
    enabled_at: datetime | None = None
    automation_paused: bool = True


class AutomationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    auto_submit_enabled: bool | None = None
    require_review_before_submit: bool | None = None
    allow_browser_verification: bool | None = None
    generate_cover_letters: bool | None = None
    daily_application_limit: int | None = Field(default=None, ge=1, le=100)
    hourly_application_limit: int | None = Field(default=None, ge=1, le=25)
    min_delay_seconds: int | None = Field(default=None, ge=0, le=3600)
    max_delay_seconds: int | None = Field(default=None, ge=0, le=7200)
    min_match_score: int | None = Field(default=None, ge=0, le=100)
    default_resume_template: ResumeTemplate | None = None
    resume_max_pages: int | None = Field(default=None, ge=1, le=3)
    confidence_auto_threshold: float | None = Field(default=None, ge=0.5, le=1.0)
    confidence_review_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    notification_preferences: dict | None = None

    @model_validator(mode="after")
    def check_ranges(self) -> AutomationSettingsUpdate:
        if (
            self.min_delay_seconds is not None
            and self.max_delay_seconds is not None
            and self.min_delay_seconds > self.max_delay_seconds
        ):
            raise ValueError("min_delay_seconds cannot exceed max_delay_seconds")
        if (
            self.confidence_review_threshold is not None
            and self.confidence_auto_threshold is not None
            and self.confidence_review_threshold > self.confidence_auto_threshold
        ):
            raise ValueError("confidence_review_threshold cannot exceed confidence_auto_threshold")
        return self


class PauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paused: bool
