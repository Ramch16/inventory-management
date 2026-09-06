"""Celery application.

Queues are separated so a slow browser run cannot starve matching or e-mail. Task
payloads carry identifiers only: workers reload state from PostgreSQL inside a
transaction, which keeps retries safe and keeps secrets out of the broker.
"""

from __future__ import annotations

from celery import Celery
from jobapply_shared.logging import configure_logging
from jobapply_shared.settings import get_settings
from kombu import Queue

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)

celery_app = Celery("jobapply", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("discovery"),
        Queue("matching"),
        Queue("resumes"),
        Queue("automation"),
        Queue("notifications"),
    ),
    task_routes={
        "jobs.*": {"queue": "discovery"},
        "match.*": {"queue": "matching"},
        "resume.*": {"queue": "resumes"},
        "apply.*": {"queue": "automation"},
        "email.*": {"queue": "notifications"},
        "notify.*": {"queue": "notifications"},
        "account.*": {"queue": "default"},
    },
)

celery_app.autodiscover_tasks(["jobapply_workers.tasks"], force=True)
