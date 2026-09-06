"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata``, which Alembic's
autogenerate relies on.
"""

from jobapply_db.models.application import (
    Application,
    ApplicationAnswer,
    ApplicationQuestion,
    ApplicationStep,
    ApplicationTask,
    AutomationLog,
    BrowserSession,
    Intervention,
)
from jobapply_db.models.job import Company, Job, JobMatch, JobPreference, JobSource
from jobapply_db.models.platform import (
    AutomationSettings,
    Credential,
    Notification,
    Subscription,
    UsageRecord,
)
from jobapply_db.models.profile import (
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    Skill,
)
from jobapply_db.models.resume import Resume, ResumeVersion
from jobapply_db.models.user import AuditLog, AuthToken, OAuthAccount, User

__all__ = [
    "Application",
    "ApplicationAnswer",
    "ApplicationQuestion",
    "ApplicationStep",
    "ApplicationTask",
    "AuditLog",
    "AuthToken",
    "AutomationLog",
    "AutomationSettings",
    "BrowserSession",
    "Certification",
    "Company",
    "Credential",
    "Education",
    "Experience",
    "Intervention",
    "Job",
    "JobMatch",
    "JobPreference",
    "JobSource",
    "Notification",
    "OAuthAccount",
    "Profile",
    "Project",
    "Resume",
    "ResumeVersion",
    "Skill",
    "Subscription",
    "UsageRecord",
    "User",
]
