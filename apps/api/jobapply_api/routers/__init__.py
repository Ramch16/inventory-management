"""HTTP routers. Routers translate HTTP to service calls and hold no business logic."""

from jobapply_api.routers import applications, auth, dashboard, health, jobs, profile, resumes

__all__ = ["applications", "auth", "dashboard", "health", "jobs", "profile", "resumes"]
