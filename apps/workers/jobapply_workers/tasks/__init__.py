"""Celery tasks, grouped by the pipeline stage they belong to."""

from jobapply_workers.tasks import account, applications, discovery, email, resumes

__all__ = ["account", "applications", "discovery", "email", "resumes"]
