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


@celery_app.on_after_configure.connect
def _register_heartbeat(sender, **_kwargs) -> None:
    """Publish a heartbeat so ``/health/ready`` can tell whether workers are alive.

    A deployment with no running worker looks healthy from the API alone while
    applications quietly queue up; this makes that visible.
    """
    sender.add_periodic_task(30.0, worker_heartbeat.s(), name="worker heartbeat")


@celery_app.task(name="worker.heartbeat")
def worker_heartbeat() -> dict:
    import socket
    import time

    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.hset("jobapply:worker:heartbeats", socket.gethostname(), time.time())
        client.expire("jobapply:worker:heartbeats", 600)
    except Exception:  # noqa: BLE001 - a missing heartbeat must not kill the worker
        return {"published": False}
    return {"published": True}
