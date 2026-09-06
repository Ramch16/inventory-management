"""Background workers."""

from jobapply_workers.celery_app import celery_app

__all__ = ["celery_app"]
