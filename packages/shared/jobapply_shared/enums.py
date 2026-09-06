"""Enumerations shared by the database, the API and the workers.

These are string enums so they serialise cleanly to JSON and read well in the database.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    PASSWORD = "password"  # noqa: S105  a sign-in method name
    GOOGLE = "google"


class RemoteType(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class SkillCategory(StrEnum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    CLOUD = "cloud"
    ANALYTICS = "analytics"
    DEVOPS = "devops"
    SOFT = "soft"
    OTHER = "other"


class AuthorizationType(StrEnum):
    """Work-authorization categories. Always supplied by the user, never inferred."""

    CITIZEN = "citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    WORK_VISA = "work_visa"
    STUDENT_VISA = "student_visa"
    WORK_PERMIT = "work_permit"
    OTHER = "other"


class ResumeSourceKind(StrEnum):
    UPLOAD_PDF = "upload_pdf"
    UPLOAD_DOCX = "upload_docx"
    PASTED_TEXT = "pasted_text"
    MANUAL = "manual"


class ResumeTemplate(StrEnum):
    ATS_CLASSIC = "ats_classic"
    MODERN_PROFESSIONAL = "modern_professional"
    TECHNICAL = "technical"
    MINIMAL = "minimal"


class MatchRecommendation(StrEnum):
    APPLY = "APPLY"
    REVIEW = "REVIEW"
    SKIP = "SKIP"


class JobStatus(StrEnum):
    DISCOVERED = "discovered"
    MATCHED = "matched"
    APPROVED = "approved"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class ApplicationStatus(StrEnum):
    """Automation workflow states (§22) plus the manual tracker states (§29)."""

    DISCOVERED = "DISCOVERED"
    MATCHED = "MATCHED"
    APPROVED = "APPROVED"
    RESUME_GENERATING = "RESUME_GENERATING"
    RESUME_READY = "RESUME_READY"
    APPLICATION_STARTING = "APPLICATION_STARTING"
    FORM_ANALYZING = "FORM_ANALYZING"
    FORM_FILLING = "FORM_FILLING"
    WAITING_FOR_VERIFICATION = "WAITING_FOR_VERIFICATION"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    SUBMISSION_UNCONFIRMED = "SUBMISSION_UNCONFIRMED"
    CONFIRMATION_CAPTURED = "CONFIRMATION_CAPTURED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    # post-submission tracker states, set by the user or by e-mail classification
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    WITHDRAWN = "WITHDRAWN"


TERMINAL_APPLICATION_STATUSES = frozenset(
    {
        ApplicationStatus.FAILED,
        ApplicationStatus.CANCELLED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
        ApplicationStatus.WITHDRAWN,
    }
)

SUBMITTED_APPLICATION_STATUSES = frozenset(
    {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.SUBMISSION_UNCONFIRMED,
        ApplicationStatus.CONFIRMATION_CAPTURED,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.ASSESSMENT,
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
    }
)


class AutomationRunState(StrEnum):
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    OTP_REQUIRED = "OTP_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    UNSUPPORTED_FORM = "UNSUPPORTED_FORM"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class InterventionType(StrEnum):
    CAPTCHA = "captcha"
    OTP = "otp"
    MFA = "mfa"
    LOW_CONFIDENCE = "low_confidence"
    UNSUPPORTED_FORM = "unsupported_form"
    LEGAL_ATTESTATION = "legal_attestation"
    MISSING_DATA = "missing_data"
    AUTHENTICATION_REQUIRED = "authentication_required"


class InterventionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class FailureReason(StrEnum):
    TRANSIENT_ERROR = "TRANSIENT_ERROR"
    UNSUPPORTED_FORM = "UNSUPPORTED_FORM"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CAPTCHA = "CAPTCHA"
    OTP = "OTP"
    MFA = "MFA"
    MISSING_DATA = "MISSING_DATA"
    AI_LOW_CONFIDENCE = "AI_LOW_CONFIDENCE"
    EMPLOYER_ERROR = "EMPLOYER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    DUPLICATE = "DUPLICATE"


RETRYABLE_FAILURES = frozenset(
    {FailureReason.TRANSIENT_ERROR, FailureReason.NETWORK_ERROR, FailureReason.EMPLOYER_ERROR}
)


class AtsKind(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    ICIMS = "icims"
    SMARTRECRUITERS = "smartrecruiters"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class FieldType(StrEnum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    NUMBER = "number"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTISELECT = "multiselect"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    FILE = "file"
    DATE = "date"
    UNKNOWN = "unknown"


class QuestionCategory(StrEnum):
    IDENTITY = "identity"
    CONTACT = "contact"
    LOCATION = "location"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    MOTIVATION = "motivation"
    COMPENSATION = "compensation"
    WORK_AUTHORIZATION = "work_authorization"
    SPONSORSHIP = "sponsorship"
    DEMOGRAPHIC = "demographic"
    DISABILITY = "disability"
    VETERAN = "veteran"
    CRIMINAL_HISTORY = "criminal_history"
    LEGAL_ATTESTATION = "legal_attestation"
    FILE_UPLOAD = "file_upload"
    OTHER = "other"


SENSITIVE_QUESTION_CATEGORIES = frozenset(
    {
        QuestionCategory.WORK_AUTHORIZATION,
        QuestionCategory.SPONSORSHIP,
        QuestionCategory.DEMOGRAPHIC,
        QuestionCategory.DISABILITY,
        QuestionCategory.VETERAN,
        QuestionCategory.CRIMINAL_HISTORY,
        QuestionCategory.LEGAL_ATTESTATION,
        QuestionCategory.COMPENSATION,
    }
)


class AnswerSource(StrEnum):
    PROFILE = "profile"
    RESUME = "resume"
    AI_GENERATED = "ai_generated"
    USER_PROVIDED = "user_provided"
    DEFAULT = "default"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"


class NotificationKind(StrEnum):
    APPLICATION_SUBMITTED = "application_submitted"
    APPLICATION_FAILED = "application_failed"
    CAPTCHA_REQUIRED = "captcha_required"
    OTP_REQUIRED = "otp_required"
    MFA_REQUIRED = "mfa_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    INTERVIEW_DETECTED = "interview_detected"
    STATUS_CHANGED = "status_changed"
    WELCOME = "welcome"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"  # noqa: S105  a notification kind


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubscriptionPlan(StrEnum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"


class EmailCategory(StrEnum):
    APPLICATION_CONFIRMATION = "APPLICATION_CONFIRMATION"
    INTERVIEW = "INTERVIEW"
    REJECTION = "REJECTION"
    ASSESSMENT = "ASSESSMENT"
    RECRUITER = "RECRUITER"
    OTHER = "OTHER"
