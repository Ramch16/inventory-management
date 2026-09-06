"""Applications, interventions and automation settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from jobapply_ai.factory import get_ai_provider
from jobapply_db.models import AutomationSettings, Intervention, Job
from jobapply_shared.enums import InterventionStatus, InterventionType
from jobapply_shared.errors import ValidationError_
from sqlalchemy import func, select

from jobapply_api.deps import (
    CurrentUser,
    NotificationServiceDep,
    SessionDep,
    StorageDep,
)
from jobapply_api.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    AutomationLogOut,
    AutomationSettingsOut,
    AutomationSettingsUpdate,
    InterventionContinue,
    InterventionOut,
    PauseRequest,
    QuestionOut,
    StatusUpdate,
    StepOut,
)
from jobapply_api.schemas.common import Page
from jobapply_api.services import audit
from jobapply_api.services.application_service import (
    BROWSER_INTERVENTIONS,
    ApplicationService,
)
from jobapply_api.services.tailoring_service import TailoringService

router = APIRouter(tags=["applications"])


def application_service(
    db: SessionDep, notifications: NotificationServiceDep, storage: StorageDep
) -> ApplicationService:
    return ApplicationService(db, notifications, storage)


ApplicationServiceDep = Annotated[ApplicationService, Depends(application_service)]


def _summary(application, job: Job, open_interventions: int = 0) -> ApplicationSummary:
    summary = ApplicationSummary.model_validate(application)
    summary.company_name = job.company_name
    summary.title = job.title
    summary.open_interventions = open_interventions
    return summary


# ------------------------------------------------------------------ applications
@router.post(
    "/applications", response_model=ApplicationSummary, status_code=status.HTTP_201_CREATED
)
def create_application(
    payload: ApplicationCreate,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
    storage: StorageDep,
) -> ApplicationSummary:
    """Create an application for an approved job.

    Every policy gate runs here — duplicates, expiry, match score, exclusions,
    salary, location, employment type, sponsorship, rate limits — so an application
    that should not exist is never created in the first place.
    """
    application = service.create(user, payload.job_id, auto_submit=payload.auto_submit)

    if payload.generate_resume:
        tailoring = TailoringService(db, storage, get_ai_provider())
        if tailoring.latest_for_job(user.id, payload.job_id) is None:
            version = tailoring.generate(user.id, payload.job_id)
            application.resume_version_id = version.id

    db.commit()
    db.refresh(application)
    job = db.get(Job, application.job_id)
    return _summary(application, job)


@router.get("/applications", response_model=Page[ApplicationSummary])
def list_applications(
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Page[ApplicationSummary]:
    rows, total = service.list(
        user.id, status=status_filter, limit=page_size, offset=(page - 1) * page_size
    )
    open_counts = dict(
        db.execute(
            select(Intervention.application_id, func.count())
            .where(
                Intervention.user_id == user.id,
                Intervention.status == str(InterventionStatus.OPEN),
            )
            .group_by(Intervention.application_id)
        ).all()
    )
    return Page[ApplicationSummary](
        items=[
            _summary(application, job, open_counts.get(application.id, 0))
            for application, job in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/applications/export")
def export_applications(user: CurrentUser, service: ApplicationServiceDep) -> Response:
    """The user's own application history as CSV."""
    import csv
    import io

    rows, _ = service.list(user.id, limit=10_000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "company",
            "title",
            "status",
            "match_score",
            "ats",
            "submitted_at",
            "confirmation_id",
            "failure_reason",
            "apply_url",
            "created_at",
        ]
    )
    for application, job in rows:
        writer.writerow(
            [
                job.company_name,
                job.title,
                application.status,
                application.match_score or "",
                application.detected_ats or "",
                application.submitted_at.isoformat() if application.submitted_at else "",
                application.confirmation_id or "",
                application.failure_reason or "",
                application.apply_url or "",
                application.created_at.isoformat(),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="applications.csv"'},
    )


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: uuid.UUID,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> ApplicationDetail:
    application = service.get(user.id, application_id)
    job = db.get(Job, application.job_id)
    open_interventions = int(
        db.execute(
            select(func.count())
            .select_from(Intervention)
            .where(
                Intervention.application_id == application.id,
                Intervention.status == str(InterventionStatus.OPEN),
            )
        ).scalar_one()
    )

    # Built from the ORM row field by field: validating the row directly would pull in
    # its ``questions`` and ``steps`` relationships, which are shaped for the database
    # rather than for this response.
    detail = ApplicationDetail(
        **_summary(application, job, open_interventions).model_dump(),
        apply_url=application.apply_url,
        confirmation_id=application.confirmation_id,
        confirmation_url=application.confirmation_url,
        confirmation_text=application.confirmation_text,
        failure_detail=application.failure_detail,
        notes=application.notes,
        completed_at=application.completed_at,
        resume_version_id=application.resume_version_id,
    )
    detail.can_retry = service.can_retry(application)
    detail.steps = [StepOut.model_validate(step) for step in service.steps(application.id)]
    detail.logs = [AutomationLogOut.model_validate(log) for log in service.logs(application.id)]
    detail.questions = [
        QuestionOut(
            id=question.id,
            field_id=question.field_id,
            label=question.label,
            question=question.question,
            field_type=question.field_type,
            category=question.category,
            required=question.required,
            is_sensitive=question.is_sensitive,
            options=list(question.options or []),
            answer=answer.answer if answer else None,
            confidence=answer.confidence if answer else 0.0,
            source=answer.source if answer else None,
            requires_review=answer.requires_review if answer else True,
            approved_by_user_at=answer.approved_by_user_at if answer else None,
            reason=answer.rejected_reason if answer else None,
        )
        for question, answer in service.questions(application.id)
    ]

    version = service.resume_version(application)
    if version is not None:
        detail.resume_template = version.template
        detail.resume_quality = version.quality
        detail.cover_letter_text = version.cover_letter_text
    return detail


@router.post("/applications/{application_id}/start", status_code=status.HTTP_202_ACCEPTED)
def start_application(
    application_id: uuid.UUID,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> dict:
    task = service.start(user, application_id)
    db.commit()
    _enqueue("apply.run", str(task.id))
    return {"task_id": str(task.id), "status": task.status}


@router.post("/applications/{application_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_application(
    application_id: uuid.UUID,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> None:
    service.cancel(user, application_id)
    db.commit()


@router.put("/applications/{application_id}/status", response_model=ApplicationSummary)
def update_status(
    application_id: uuid.UUID,
    payload: StatusUpdate,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> ApplicationSummary:
    application = service.set_manual_status(user, application_id, str(payload.status), payload.note)
    db.commit()
    db.refresh(application)
    return _summary(application, db.get(Job, application.job_id))


# ----------------------------------------------------------------- interventions
@router.get("/interventions", response_model=Page[InterventionOut])
def list_interventions(
    user: CurrentUser,
    service: ApplicationServiceDep,
    storage: StorageDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: str | None = Query(default="open", alias="status"),
) -> Page[InterventionOut]:
    rows, total = service.list_interventions(
        user.id, status=status_filter, limit=page_size, offset=(page - 1) * page_size
    )
    return Page[InterventionOut](
        items=[_intervention_out(row[0], row[2], storage) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/interventions/{intervention_id}", response_model=InterventionOut)
def get_intervention(
    intervention_id: uuid.UUID,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
    storage: StorageDep,
) -> InterventionOut:
    intervention = service.get_intervention(user.id, intervention_id)
    application = service.get(user.id, intervention.application_id)
    return _intervention_out(intervention, db.get(Job, application.job_id), storage)


@router.post("/interventions/{intervention_id}/continue", status_code=status.HTTP_202_ACCEPTED)
def continue_intervention(
    intervention_id: uuid.UUID,
    payload: InterventionContinue,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> dict:
    """Record what the user supplied and re-queue the run.

    A one-time code travels to the worker in the task message and is never written to
    the database or to a log line.
    """
    task = service.resolve_intervention(
        user, intervention_id, answers=payload.answers, otp_code=payload.otp_code
    )
    db.commit()
    _enqueue("apply.resume_after_verification", str(task.id), otp_code=payload.otp_code)
    return {"task_id": str(task.id), "status": task.status}


@router.post("/interventions/{intervention_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_intervention(
    intervention_id: uuid.UUID,
    user: CurrentUser,
    service: ApplicationServiceDep,
    db: SessionDep,
) -> None:
    service.cancel_intervention(user, intervention_id)
    db.commit()


def _intervention_out(intervention: Intervention, job: Job, storage) -> InterventionOut:
    out = InterventionOut.model_validate(intervention)
    out.company_name = job.company_name if job else None
    out.title = job.title if job else None
    out.requires_browser = InterventionType(intervention.type) in BROWSER_INTERVENTIONS
    if intervention.screenshot_key:
        out.screenshot_url = storage.presign(intervention.screenshot_key)
    return out


# ------------------------------------------------------------ automation settings
@router.get("/automation-settings", response_model=AutomationSettingsOut)
def get_automation_settings(user: CurrentUser, db: SessionDep) -> AutomationSettingsOut:
    settings = _settings_for(db, user)
    db.commit()
    out = AutomationSettingsOut.model_validate(settings)
    out.automation_paused = user.automation_paused
    return out


@router.put("/automation-settings", response_model=AutomationSettingsOut)
def update_automation_settings(
    payload: AutomationSettingsUpdate,
    user: CurrentUser,
    db: SessionDep,
) -> AutomationSettingsOut:
    settings = _settings_for(db, user)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("enabled") and not user.onboarding_completed_at:
        raise ValidationError_(
            "Complete onboarding and confirm your profile before enabling automation.",
            code="onboarding_incomplete",
        )

    for key, value in changes.items():
        setattr(settings, key, str(value) if key == "default_resume_template" else value)

    if changes.get("enabled"):
        settings.enabled_at = datetime.now(tz=UTC)
    audit.record(
        db,
        action="automation.settings_updated",
        actor_user_id=user.id,
        entity_type="automation_settings",
        entity_id=settings.id,
        data={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(settings)
    out = AutomationSettingsOut.model_validate(settings)
    out.automation_paused = user.automation_paused
    return out


@router.post("/automation/pause", response_model=AutomationSettingsOut)
def set_pause(payload: PauseRequest, user: CurrentUser, db: SessionDep) -> AutomationSettingsOut:
    """The global stop. Pausing takes effect immediately for every queued run."""
    settings = _settings_for(db, user)
    user.automation_paused = payload.paused
    settings.paused_at = datetime.now(tz=UTC) if payload.paused else None
    audit.record(
        db,
        action="automation.paused" if payload.paused else "automation.resumed",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    db.refresh(settings)
    out = AutomationSettingsOut.model_validate(settings)
    out.automation_paused = user.automation_paused
    return out


def _settings_for(db, user) -> AutomationSettings:
    settings = db.execute(
        select(AutomationSettings).where(AutomationSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings is None:
        settings = AutomationSettings(user_id=user.id)
        db.add(settings)
        db.flush()
    return settings


def _enqueue(task_name: str, task_id: str, **kwargs) -> None:
    """Hand the task to the broker.

    A broker that is unavailable must not fail the request: the row is already
    written, and the sweeper picks up queued tasks.
    """
    try:
        from jobapply_workers.celery_app import celery_app

        celery_app.send_task(task_name, kwargs={"task_id": task_id, **kwargs})
    except Exception:  # noqa: BLE001 - the queued row is the source of truth
        from jobapply_shared.logging import get_logger

        get_logger(__name__).warning(
            "queue.enqueue_failed",
            extra={"context": {"event": "queue.enqueue_failed", "task": task_name}},
        )
