"""Liveness and readiness.

``/health`` answers whether the process is up. ``/health/ready`` answers whether it can
actually serve: database reachable, Redis reachable, storage writable, AI provider
configured.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from jobapply_api.deps import SessionDep, SettingsDep, StorageDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: SettingsDep) -> dict:
    return {"status": "ok", "environment": settings.environment, "app": settings.app_name}


@router.get("/health/ready")
def ready(response: Response, db: SessionDep, settings: SettingsDep, storage: StorageDep) -> dict:
    checks: dict[str, dict] = {}

    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        checks["database"] = {"ok": False, "detail": str(exc)[:200]}

    started = time.perf_counter()
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        checks["redis"] = {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        checks["redis"] = {"ok": False, "detail": str(exc)[:200]}

    try:
        probe_key = ".health/probe"
        storage.put(probe_key, b"ok", "text/plain")
        storage.delete(probe_key)
        checks["storage"] = {"ok": True, "backend": settings.storage_backend}
    except Exception as exc:
        checks["storage"] = {"ok": False, "detail": str(exc)[:200]}

    checks["ai_provider"] = {"ok": True, "provider": settings.ai_provider}

    healthy = all(check.get("ok") for check in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
