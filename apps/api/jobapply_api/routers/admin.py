"""Administrator endpoints.

Admins see aggregates and failure diagnostics so a broken adapter or a failing
provider can be found and disabled. They do not see passwords, tokens, credential
secrets, browser state, or the content of anyone's application answers — an operator
does not need those to fix the platform.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from jobapply_db.models import (
    Application,
    AutomationLog,
    AutomationSettings,
    Intervention,
    Job,
    JobSource,
    Subscription,
    UsageRecord,
    User,
)
from jobapply_shared.enums import (
    SUBMITTED_APPLICATION_STATUSES,
    ApplicationStatus,
    AtsKind,
    InterventionStatus,
)
from jobapply_shared.errors import NotFoundError
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from jobapply_api.deps import CurrentAdmin, SessionDep
from jobapply_api.services import audit

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    """Never includes a password hash, a token or any credential material."""

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    email_verified: bool
    automation_enabled: bool
    automation_paused: bool
    plan: str | None = None
    applications: int = 0
    created_at: datetime


class AdapterHealth(BaseModel):
    ats: str
    runs: int = 0
    succeeded: int = 0
    failed: int = 0
    interventions: int = 0
    success_rate: float = 0.0
    enabled: bool = True


class AdminOverview(BaseModel):
    users: int
    active_users: int
    jobs: int
    applications: int
    submitted: int
    failed: int
    open_interventions: int
    adapters: list[AdapterHealth]


class AdminErrorOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID | None = None
    event: str
    level: str
    status: str | None = None
    ats: str | None = None
    message: str | None = None
    created_at: datetime


class AdapterToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SourceToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    config: dict | None = None


def _count(db, model, *conditions) -> int:
    return int(db.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one())


@router.get("/overview", response_model=AdminOverview)
def overview(admin: CurrentAdmin, db: SessionDep) -> AdminOverview:
    submitted = [str(status) for status in SUBMITTED_APPLICATION_STATUSES]
    rows = db.execute(
        select(
            Application.detected_ats,
            Application.status,
            func.count().label("count"),
        )
        .where(Application.deleted_at.is_(None))
        .group_by(Application.detected_ats, Application.status)
    ).all()

    per_ats: dict[str, dict[str, int]] = {}
    for ats, status, count in rows:
        bucket = per_ats.setdefault(ats or "unknown", {"runs": 0, "succeeded": 0, "failed": 0})
        bucket["runs"] += int(count)
        if status in submitted:
            bucket["succeeded"] += int(count)
        elif status == str(ApplicationStatus.FAILED):
            bucket["failed"] += int(count)

    intervention_counts = dict(
        db.execute(
            select(Application.detected_ats, func.count())
            .join(Intervention, Intervention.application_id == Application.id)
            .group_by(Application.detected_ats)
        ).all()
    )

    adapters = []
    for kind in [*AtsKind]:
        if kind in {AtsKind.UNKNOWN}:
            continue
        stats = per_ats.get(str(kind), {"runs": 0, "succeeded": 0, "failed": 0})
        finished = stats["succeeded"] + stats["failed"]
        adapters.append(
            AdapterHealth(
                ats=str(kind),
                runs=stats["runs"],
                succeeded=stats["succeeded"],
                failed=stats["failed"],
                interventions=int(intervention_counts.get(str(kind), 0)),
                success_rate=round(100 * stats["succeeded"] / finished, 1) if finished else 0.0,
                enabled=True,
            )
        )

    return AdminOverview(
        users=_count(db, User, User.deleted_at.is_(None)),
        active_users=_count(db, User, User.deleted_at.is_(None), User.is_active.is_(True)),
        jobs=_count(db, Job, Job.deleted_at.is_(None)),
        applications=_count(db, Application, Application.deleted_at.is_(None)),
        submitted=_count(
            db, Application, Application.deleted_at.is_(None), Application.status.in_(submitted)
        ),
        failed=_count(
            db,
            Application,
            Application.deleted_at.is_(None),
            Application.status == str(ApplicationStatus.FAILED),
        ),
        open_interventions=_count(
            db, Intervention, Intervention.status == str(InterventionStatus.OPEN)
        ),
        adapters=adapters,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    admin: CurrentAdmin,
    db: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminUserOut]:
    rows = db.execute(
        select(
            User,
            AutomationSettings.enabled,
            Subscription.plan,
            func.count(Application.id),
        )
        .outerjoin(AutomationSettings, AutomationSettings.user_id == User.id)
        .outerjoin(Subscription, Subscription.user_id == User.id)
        .outerjoin(
            Application,
            (Application.user_id == User.id) & (Application.deleted_at.is_(None)),
        )
        .where(User.deleted_at.is_(None))
        .group_by(User.id, AutomationSettings.enabled, Subscription.plan)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            email_verified=user.email_verified_at is not None,
            automation_enabled=bool(enabled),
            automation_paused=user.automation_paused,
            plan=plan,
            applications=int(applications),
            created_at=user.created_at,
        )
        for user, enabled, plan, applications in rows
    ]


@router.post("/users/{user_id}/disable", response_model=AdminUserOut)
def disable_user(user_id: uuid.UUID, admin: CurrentAdmin, db: SessionDep) -> AdminUserOut:
    """Disable an account. Automation is paused at the same time so nothing keeps
    running on behalf of a user who has just been locked out."""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found.", code="user_not_found")
    user.is_active = False
    user.automation_paused = True
    audit.record(
        db,
        action="admin.user_disabled",
        actor_user_id=admin.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return AdminUserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified_at is not None,
        automation_enabled=False,
        automation_paused=user.automation_paused,
        applications=0,
        created_at=user.created_at,
    )


@router.get("/errors", response_model=list[AdminErrorOut])
def list_errors(
    admin: CurrentAdmin,
    db: SessionDep,
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AdminErrorOut]:
    since = datetime.now(tz=UTC) - timedelta(hours=hours)
    rows = (
        db.execute(
            select(AutomationLog)
            .where(
                AutomationLog.created_at >= since,
                AutomationLog.level.in_(["ERROR", "WARNING"]),
            )
            .order_by(AutomationLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [AdminErrorOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/usage")
def usage(admin: CurrentAdmin, db: SessionDep, months: int = Query(default=3, ge=1, le=24)) -> dict:
    rows = db.execute(
        select(UsageRecord.period, UsageRecord.metric, func.sum(UsageRecord.quantity))
        .group_by(UsageRecord.period, UsageRecord.metric)
        .order_by(UsageRecord.period.desc())
        .limit(months * 5)
    ).all()
    plans = dict(
        db.execute(select(Subscription.plan, func.count()).group_by(Subscription.plan)).all()
    )
    return {
        "usage": [
            {"period": period, "metric": metric, "quantity": int(quantity or 0)}
            for period, metric, quantity in rows
        ],
        "plans": {plan: int(count) for plan, count in plans.items()},
    }


@router.get("/sources")
def list_sources(admin: CurrentAdmin, db: SessionDep) -> list[dict]:
    return [
        {
            "id": str(source.id),
            "slug": source.slug,
            "name": source.name,
            "kind": source.kind,
            "enabled": source.enabled,
            "last_run_at": source.last_run_at.isoformat() if source.last_run_at else None,
            "last_error": source.last_error,
        }
        for source in db.execute(select(JobSource).order_by(JobSource.slug)).scalars()
    ]


@router.post("/sources/{slug}")
def toggle_source(slug: str, payload: SourceToggle, admin: CurrentAdmin, db: SessionDep) -> dict:
    """Enable, disable or reconfigure a job source — the lever for a source that has
    started returning junk or has begun rate-limiting us."""
    source = db.execute(select(JobSource).where(JobSource.slug == slug)).scalar_one_or_none()
    if source is None:
        raise NotFoundError("Job source not found.", code="source_not_found")
    source.enabled = payload.enabled
    if payload.config is not None:
        source.config = payload.config
    audit.record(
        db,
        action="admin.source_toggled",
        actor_user_id=admin.id,
        entity_type="job_source",
        entity_id=source.id,
        data={"enabled": payload.enabled},
    )
    db.commit()
    return {"slug": source.slug, "enabled": source.enabled}
