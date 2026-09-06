"""Celery tasks, grouped by the pipeline stage they belong to."""

from jobapply_workers.tasks import account, email, resumes

__all__ = ["account", "email", "resumes"]
