"""HTTP routers. Routers translate HTTP to service calls and hold no business logic."""

from jobapply_api.routers import (
    admin,
    applications,
    auth,
    billing,
    dashboard,
    health,
    jobs,
    profile,
    resumes,
)

__all__ = [
    "admin",
    "applications",
    "auth",
    "billing",
    "dashboard",
    "health",
    "jobs",
    "profile",
    "resumes",
]
