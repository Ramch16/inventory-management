"""HTTP routers. Routers translate HTTP to service calls and hold no business logic."""

from jobapply_api.routers import auth, dashboard, health, profile, resumes

__all__ = ["auth", "dashboard", "health", "profile", "resumes"]
