"""Contracts for form understanding and application automation.

These are plain data models with no Playwright dependency, so form analysis, field
mapping and answer resolution are unit-testable without a browser.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jobapply_shared.enums import (
    AnswerSource,
    AtsKind,
    FieldType,
    InterventionType,
    QuestionCategory,
)
from pydantic import BaseModel, ConfigDict, Field


class FieldOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class NormalizedField(BaseModel):
    """One form control, described independently of the page that produced it."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    label: str | None = None
    name: str | None = None
    dom_id: str | None = None
    type: FieldType = FieldType.UNKNOWN
    required: bool = False
    options: list[FieldOption] = Field(default_factory=list)
    placeholder: str | None = None
    #: Text near the control that clarifies what is being asked.
    context_text: str | None = None
    max_length: int | None = None
    #: The question as a person would read it.
    question: str | None = None
    selector: str | None = None


class FormSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    ats: AtsKind = AtsKind.UNKNOWN
    fields: list[NormalizedField] = Field(default_factory=list)
    submit_selector: str | None = None
    page_title: str | None = None

    def required_fields(self) -> list[NormalizedField]:
        return [field for field in self.fields if field.required]


class MappingTarget(BaseModel):
    """Where a field's value comes from."""

    model_config = ConfigDict(extra="forbid")

    key: str
    #: True for anything legally significant or protected: these may only be answered
    #: from an explicit profile field, never generated.
    sensitive: bool = False
    category: QuestionCategory = QuestionCategory.OTHER


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    target: str | None = None
    category: QuestionCategory = QuestionCategory.OTHER
    is_sensitive: bool = False
    confidence: float = 0.0
    strategy: str = "deterministic"
    rationale: str | None = None


class ResolvedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    answer: str | None = None
    confidence: float = 0.0
    source: AnswerSource = AnswerSource.DEFAULT
    source_ids: list[str] = Field(default_factory=list)
    requires_review: bool = True
    category: QuestionCategory = QuestionCategory.OTHER
    is_sensitive: bool = False
    reason: str | None = None
    #: Set once a person has looked at a reviewed answer and accepted it.
    approved_by_user: bool = False

    @property
    def can_autofill(self) -> bool:
        return self.answer is not None and (not self.requires_review or self.approved_by_user)

    @property
    def needs_person(self) -> bool:
        return self.requires_review and not self.approved_by_user


class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ats: AtsKind = AtsKind.UNKNOWN
    confidence: float = 0.0
    #: Every signal that agreed, so a detection can be audited rather than trusted.
    signals: list[str] = Field(default_factory=list)


class FillOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    filled: bool
    #: What the page actually contained after the write, read back for verification.
    observed_value: str | None = None
    error: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    missing_required: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VerificationSignal(BaseModel):
    """A point where the run must stop and hand control to the user."""

    model_config = ConfigDict(extra="forbid")

    type: InterventionType
    reason: str
    selector: str | None = None
    detected_at: datetime | None = None
    evidence: list[str] = Field(default_factory=list)


class SubmissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submitted: bool
    blocked_by: VerificationSignal | None = None
    error: str | None = None


class ConfirmationResult(BaseModel):
    """Absent hard evidence, a submission is reported as unconfirmed, never as applied."""

    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    confirmation_id: str | None = None
    url: str | None = None
    text: str | None = None
    screenshot_key: str | None = None
    signals: list[str] = Field(default_factory=list)


class RunContext(BaseModel):
    """Everything an adapter needs for one application run."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    application_id: str
    user_id: str
    job_id: str
    apply_url: str
    ats: AtsKind = AtsKind.UNKNOWN
    answers: dict[str, ResolvedAnswer] = Field(default_factory=dict)
    resume_path: str | None = None
    cover_letter_path: str | None = None
    auto_submit: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
