"""Dashboard, analytics summary and notifications."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from jobapply_api.deps import (
    CurrentUser,
    DashboardServiceDep,
    NotificationServiceDep,
    SessionDep,
)
from jobapply_api.schemas.dashboard import (
    DashboardCounters,
    DashboardResponse,
    NotificationResponse,
    ProfileReadiness,
)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(user: CurrentUser, service: DashboardServiceDep) -> DashboardResponse:
    return DashboardResponse(
        counters=DashboardCounters(**service.counters(user.id)),
        readiness=ProfileReadiness(**service.readiness(user)),
        recent_applications=service.recent_applications(user.id),
        attention_required=service.attention_required(user.id),
    )


@router.get("/analytics/summary", response_model=DashboardCounters)
def analytics_summary(user: CurrentUser, service: DashboardServiceDep) -> DashboardCounters:
    return DashboardCounters(**service.counters(user.id))


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    user: CurrentUser,
    service: NotificationServiceDep,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationResponse]:
    items, _ = service.list_for_user(user.id, unread_only=unread_only, limit=limit, offset=offset)
    return [NotificationResponse.model_validate(item) for item in items]


@router.get("/notifications/unread-count")
def unread_count(user: CurrentUser, service: NotificationServiceDep) -> dict[str, int]:
    return {"count": service.unread_count(user.id)}


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: uuid.UUID,
    user: CurrentUser,
    service: NotificationServiceDep,
    db: SessionDep,
) -> None:
    service.mark_read(user.id, notification_id)
    db.commit()


@router.post("/notifications/read-all")
def mark_all_read(
    user: CurrentUser, service: NotificationServiceDep, db: SessionDep
) -> dict[str, int]:
    count = service.mark_all_read(user.id)
    db.commit()
    return {"updated": count}
