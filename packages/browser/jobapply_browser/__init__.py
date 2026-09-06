"""Form understanding, field mapping, answer resolution and ATS adapters."""

from jobapply_browser.mapping import TARGETS, map_field, map_fields, unmapped
from jobapply_browser.models import (
    ConfirmationResult,
    DetectionResult,
    FieldMapping,
    FormSpec,
    NormalizedField,
    ResolvedAnswer,
    RunContext,
    SubmissionResult,
    ValidationReport,
    VerificationSignal,
)
from jobapply_browser.questions import AnswerContext, ApplicationQuestionService

__all__ = [
    "TARGETS",
    "AnswerContext",
    "ApplicationQuestionService",
    "ConfirmationResult",
    "DetectionResult",
    "FieldMapping",
    "FormSpec",
    "NormalizedField",
    "ResolvedAnswer",
    "RunContext",
    "SubmissionResult",
    "ValidationReport",
    "VerificationSignal",
    "map_field",
    "map_fields",
    "unmapped",
]
