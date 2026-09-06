"""Periodic schedule.

Phase 1 schedules only what Phase 1 actually implements. Discovery, matching and
automation entries are added as those phases land, so the schedule never advertises a
job that does not exist.
"""

from __future__ import annotations

from celery.schedules import crontab

from jobapply_workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "discover-jobs": {
        # Only users who switched automation on are polled.
        "task": "jobs.discover_for_all_active_users",
        "schedule": crontab(minute="*/30"),
    },
    "expire-stale-jobs": {
        "task": "jobs.expire_stale",
        "schedule": crontab(minute="15"),
    },
    "purge-deleted-accounts": {
        "task": "account.purge_deleted",
        "schedule": crontab(hour="3", minute="30"),
    },
}
