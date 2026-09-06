"""Applications: creation, queueing, status and the intervention lifecycle.

The service owns the workflow states. It never drives a browser itself — that happens
in a worker — so the API stays responsive and a run can be retried without replaying
an HTTP request.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from jobapply_db.models import (
    Application,
    ApplicationAnswer,
    ApplicationQuestion,
    ApplicationStep,
    ApplicationTask,
    AutomationLog,
    AutomationSettings,
    BrowserSession,
    Intervention,
    Job,
    JobMatch,
    ResumeVersion,
    User,
)
from jobapply_shared.enums import (
    RETRYABLE_FAILURES,
    TERMINAL_APPLICATION_STATUSES,
    ApplicationStatus,
    FailureReason,
    InterventionStatus,
    InterventionType,
    NotificationKind,
    TaskStatus,
)
from jobapply_shared.errors import ConflictError, NotFoundError, ValidationError_
from jobapply_shared.logging import get_logger
from jobapply_shared.metrics import record_application_run, record_intervention
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobapply_api.services import audit
from jobapply_api.services.job_service import JobService
from jobapply_api.services.notification_service import NotificationService
from jobapply_api.services.policy import (
    ApplicationPolicy,
    manual_status_allowed,
    resume_ready,
)
from jobapply_api.services.tailoring_service import TailoringService

logger = get_logger(__name__)

MAX_ATTEMPTS = 3

#: Intervention types that mean the user has to act in a browser themselves.
BROWSER_INTERVENTIONS = frozenset(
    {
        InterventionType.CAPTCHA,
        InterventionType.MFA,
        InterventionType.AUTHENTICATION_REQUIRED,
    }
)

NOTIFICATION_BY_INTERVENTION = {
    InterventionType.CAPTCHA: NotificationKind.CAPTCHA_REQUIRED,
    InterventionType.OTP: NotificationKind.OTP_REQUIRED,
    InterventionType.MFA: NotificationKind.MFA_REQUIRED,
}


class ApplicationService:
    def __init__(
        self,
        db: Session,
        notifications: NotificationService | None = None,
        storage: Any | None = None,
    ) -> None:
        self.db = db
        self.notifications = notifications
        self.storage = storage

    # ------------------------------------------------------------------ create
    def create(
        self, user: User, job_id: uuid.UUID, *, auto_submit: bool | None = None
    ) -> Application:
        job = JobService(self.db).get_job(job_id)
        decision = ApplicationPolicy(self.db).evaluate(user, job)

        if not decision.allowed:
            violation = decision.first
            assert violation is not None
            raise ValidationError_(
                violation.message,
                code=violation.code,
                details={
                    "violations": [
                        {"code": item.code, "message": item.message, "details": item.details}
                        for item in decision.violations
                    ],
                    "retry_after_seconds": decision.retry_after_seconds,
                },
            )

        automation = self.db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user.id)
        ).scalar_one_or_none()
        submit = (
            auto_submit
            if auto_submit is not None
            else bool(automation and automation.auto_submit_enabled)
        )
        # Review-before-submit always wins over auto-submit: the stricter of the two
        # settings is the one the user meant.
        requires_review = bool(automation and automation.require_review_before_submit)

        match = self.db.execute(
            select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
        ).scalar_one_or_none()

        application = Application(
            user_id=user.id,
            job_id=job.id,
            status=str(ApplicationStatus.APPROVED),
            auto_submit=submit and not requires_review,
            requires_review=requires_review,
            detected_ats=job.detected_ats,
            apply_url=job.apply_url,
            dedupe_hash=decision.dedupe_hash,
            match_score=match.overall_score if match else None,
        )
        self.db.add(application)
        self.db.flush()
        self._step(application, "created", "ok", "Application created from an approved match.")

        audit.record(
            self.db,
            action="application.created",
            actor_user_id=user.id,
            entity_type="application",
            entity_id=application.id,
            data={"job_id": str(job.id), "auto_submit": application.auto_submit},
        )
        return application

    # ------------------------------------------------------------------- start
    def start(self, user: User, application_id: uuid.UUID) -> ApplicationTask:
        """Queue the run. The tailored resume must already exist."""
        application = self.get(user.id, application_id)

        if application.status in {str(status) for status in TERMINAL_APPLICATION_STATUSES}:
            raise ConflictError(
                f"This application is already {application.status.lower()}.",
                code="application_terminal",
            )
        if application.attempts >= MAX_ATTEMPTS:
            raise ConflictError(
                "This application has already been retried the maximum number of times.",
                code="max_attempts_reached",
            )

        job = JobService(self.db).get_job(application.job_id)
        decision = ApplicationPolicy(self.db).evaluate(user, job)
        # "already_applied" refers to this very application when we are restarting it.
        blocking = [
            violation
            for violation in decision.violations
            if violation.code != "already_applied"
            or violation.details.get("application_id") != str(application.id)
        ]
        if blocking:
            raise ValidationError_(
                blocking[0].message,
                code=blocking[0].code,
                details={"violations": [item.__dict__ for item in blocking]},
            )

        if not resume_ready(self.db, user.id, application.job_id):
            raise ValidationError_(
                "Generate a tailored resume for this job before starting the application.",
                code="resume_not_ready",
            )

        version = TailoringService(self.db, self.storage).latest_for_job(
            user.id, application.job_id
        )
        application.resume_version_id = version.id if version else None
        application.status = str(ApplicationStatus.APPLICATION_STARTING)
        application.started_at = datetime.now(tz=UTC)
        application.attempts += 1

        task = ApplicationTask(
            user_id=user.id,
            job_id=application.job_id,
            application_id=application.id,
            kind="apply",
            status=str(TaskStatus.QUEUED),
            max_attempts=MAX_ATTEMPTS,
        )
        self.db.add(task)
        self.db.flush()
        self._step(application, "queued", "ok", "Queued for the automation worker.")
        audit.record(
            self.db,
            action="application.started",
            actor_user_id=user.id,
            entity_type="application",
            entity_id=application.id,
            data={"attempt": application.attempts},
        )
        return task

    # -------------------------------------------------------------- run result
    def apply_run_report(self, application: Application, report: Any) -> Application:
        """Persist a worker's ``RunReport``: steps, questions, answers, logs, status."""
        for step in report.steps:
            self._step(
                application,
                step.name,
                step.status,
                step.message,
                duration_ms=step.duration_ms,
                data=step.data,
            )

        if report.form is not None:
            self._persist_questions(application, report)

        application.status = str(report.status)
        application.run_state = str(report.state)
        application.detected_ats = (
            str(report.detection.ats) if report.detection else application.detected_ats
        )

        if report.failure_reason is not None:
            application.failure_reason = str(report.failure_reason)
            application.failure_detail = report.failure_detail

        if report.confirmation is not None and report.confirmation.confirmed:
            application.submitted_at = application.submitted_at or datetime.now(tz=UTC)
            application.completed_at = datetime.now(tz=UTC)
            application.confirmation_id = report.confirmation.confirmation_id
            application.confirmation_url = report.confirmation.url
            application.confirmation_text = report.confirmation.text
            application.confirmation_source = "page"
        elif application.status == str(ApplicationStatus.SUBMISSION_UNCONFIRMED):
            # The click went through but nothing proved delivery. Record the time so
            # rate limits still count it, without claiming it was received.
            application.submitted_at = application.submitted_at or datetime.now(tz=UTC)

        self.db.add(
            AutomationLog(
                user_id=application.user_id,
                application_id=application.id,
                job_id=application.job_id,
                event="automation.run_finished",
                status=str(report.status),
                ats=str(report.detection.ats) if report.detection else None,
                message=report.failure_detail,
                data={
                    "state": str(report.state),
                    "fields": len(report.form.fields) if report.form else 0,
                    "filled": sum(1 for outcome in report.fills if outcome.filled),
                },
            )
        )

        record_application_run(
            str(report.detection.ats) if report.detection else "unknown",
            str(report.status),
            sum(step.duration_ms or 0 for step in report.steps),
        )

        if report.intervention is not None:
            record_intervention(str(report.intervention.type))
            self.open_intervention(application, report)
        elif report.failure_reason is not None:
            self._notify(
                application,
                NotificationKind.APPLICATION_FAILED,
                "Application failed",
                report.failure_detail or "The application could not be completed.",
            )
        elif application.status in {
            str(ApplicationStatus.SUBMITTED),
            str(ApplicationStatus.CONFIRMATION_CAPTURED),
        }:
            self._notify(
                application,
                NotificationKind.APPLICATION_SUBMITTED,
                "Application submitted",
                "Your application was submitted and confirmed.",
            )
        elif application.status == str(ApplicationStatus.SUBMISSION_UNCONFIRMED):
            self._notify(
                application,
                NotificationKind.APPLICATION_SUBMITTED,
                "Application sent, but not confirmed",
                (
                    "The form was submitted but no confirmation appeared. Check your "
                    "e-mail before applying again."
                ),
            )
        return application

    def _persist_questions(self, application: Application, report: Any) -> None:
        answers = {answer.field_id: answer for answer in report.answers}
        existing = {
            question.field_id: question
            for question in self.db.execute(
                select(ApplicationQuestion).where(
                    ApplicationQuestion.application_id == application.id
                )
            ).scalars()
        }
        for field in report.form.fields:
            question = existing.get(field.field_id)
            if question is None:
                question = ApplicationQuestion(
                    application_id=application.id,
                    field_id=field.field_id,
                    field_name=field.name,
                    label=field.label,
                    question=field.question,
                    field_type=str(field.type),
                    required=field.required,
                    options=[option.model_dump() for option in field.options],
                    context_text=field.context_text,
                )
                self.db.add(question)
                self.db.flush()

            answer = answers.get(field.field_id)
            if answer is None:
                continue
            question.category = str(answer.category)
            question.is_sensitive = answer.is_sensitive

            record = self.db.execute(
                select(ApplicationAnswer).where(ApplicationAnswer.question_id == question.id)
            ).scalar_one_or_none()
            if record is None:
                record = ApplicationAnswer(question_id=question.id, application_id=application.id)
                self.db.add(record)
            record.answer = answer.answer
            record.confidence = answer.confidence
            record.source = str(answer.source)
            record.source_ids = answer.source_ids
            record.requires_review = answer.requires_review
            record.rejected_reason = answer.reason

    # ----------------------------------------------------------- interventions
    def open_intervention(self, application: Application, report: Any) -> Intervention:
        request = report.intervention
        intervention = Intervention(
            user_id=application.user_id,
            application_id=application.id,
            type=str(request.type),
            status=str(InterventionStatus.OPEN),
            current_step=request.current_step,
            reason=request.reason,
            page_url=report.page_url,
            page_title=report.page_title,
            screenshot_key=request.payload.get("screenshot_key"),
            payload=request.payload,
        )
        self.db.add(intervention)
        self.db.flush()

        kind = NOTIFICATION_BY_INTERVENTION.get(
            request.type, NotificationKind.HUMAN_REVIEW_REQUIRED
        )
        self._notify(
            application,
            kind,
            "Action required",
            request.reason,
            link=f"/interventions/{intervention.id}",
        )
        logger.info(
            "automation.intervention_opened",
            extra={
                "context": {
                    "event": "automation.intervention_opened",
                    "application_id": str(application.id),
                    "type": str(request.type),
                    "step": request.current_step,
                }
            },
        )
        return intervention

    def list_interventions(
        self, user_id: uuid.UUID, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[tuple[Intervention, Application, Job]], int]:
        conditions = [Intervention.user_id == user_id]
        if status:
            conditions.append(Intervention.status == status)
        statement = (
            select(Intervention, Application, Job)
            .join(Application, Application.id == Intervention.application_id)
            .join(Job, Job.id == Application.job_id)
            .where(*conditions)
        )
        total = self.db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
        rows = self.db.execute(
            statement.order_by(Intervention.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows], int(total)

    def get_intervention(self, user_id: uuid.UUID, intervention_id: uuid.UUID) -> Intervention:
        intervention = self.db.execute(
            select(Intervention).where(
                Intervention.id == intervention_id, Intervention.user_id == user_id
            )
        ).scalar_one_or_none()
        if intervention is None:
            raise NotFoundError("Intervention not found.", code="intervention_not_found")
        return intervention

    def resolve_intervention(
        self,
        user: User,
        intervention_id: uuid.UUID,
        *,
        answers: dict[str, str] | None = None,
        otp_code: str | None = None,
    ) -> ApplicationTask:
        """Record the user's input and re-queue the run.

        A one-time code is passed to the worker in the task payload and never written
        to the database.
        """
        intervention = self.get_intervention(user.id, intervention_id)
        if intervention.status != str(InterventionStatus.OPEN):
            raise ConflictError(
                "This item has already been dealt with.", code="intervention_closed"
            )

        application = self.get(user.id, intervention.application_id)

        if answers:
            self._apply_user_answers(application, answers)

        intervention.status = str(InterventionStatus.RESOLVED)
        intervention.resolved_at = datetime.now(tz=UTC)
        intervention.resolution = "continued"

        application.status = str(ApplicationStatus.APPLICATION_STARTING)
        self._step(
            application,
            "intervention_resolved",
            "ok",
            f"You resolved a {intervention.type} step.",
        )

        task = ApplicationTask(
            user_id=user.id,
            job_id=application.job_id,
            application_id=application.id,
            kind="apply_resume",
            status=str(TaskStatus.QUEUED),
            max_attempts=MAX_ATTEMPTS,
        )
        self.db.add(task)
        self.db.flush()

        audit.record(
            self.db,
            action="application.intervention_resolved",
            actor_user_id=user.id,
            entity_type="intervention",
            entity_id=intervention.id,
            # The OTP itself is deliberately absent from the audit payload.
            data={"type": intervention.type, "answered": sorted(answers or {})},
        )
        # ``otp_code`` is handed to the worker by the caller and is never written
        # anywhere: not to this row, not to the audit log, not to a log line.
        _ = otp_code
        return task

    def cancel_intervention(self, user: User, intervention_id: uuid.UUID) -> Intervention:
        intervention = self.get_intervention(user.id, intervention_id)
        intervention.status = str(InterventionStatus.CANCELLED)
        intervention.resolved_at = datetime.now(tz=UTC)
        intervention.resolution = "cancelled"

        application = self.get(user.id, intervention.application_id)
        application.status = str(ApplicationStatus.CANCELLED)
        application.completed_at = datetime.now(tz=UTC)
        self._step(application, "cancelled", "ok", "You cancelled this application.")
        self._close_browser_sessions(application)
        return intervention

    def _apply_user_answers(self, application: Application, answers: dict[str, str]) -> None:
        questions = {
            question.field_id: question
            for question in self.db.execute(
                select(ApplicationQuestion).where(
                    ApplicationQuestion.application_id == application.id
                )
            ).scalars()
        }
        now = datetime.now(tz=UTC)
        for field_id, value in answers.items():
            question = questions.get(field_id)
            if question is None:
                continue
            record = self.db.execute(
                select(ApplicationAnswer).where(ApplicationAnswer.question_id == question.id)
            ).scalar_one_or_none()
            if record is None:
                record = ApplicationAnswer(question_id=question.id, application_id=application.id)
                self.db.add(record)
            record.answer = value
            record.confidence = 1.0
            record.source = "user_provided"
            record.requires_review = False
            record.approved_by_user_at = now

    # ------------------------------------------------------------------ status
    def get(self, user_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        application = self.db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.user_id == user_id,
                Application.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found.", code="application_not_found")
        return application

    def list(
        self,
        user_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[tuple[Application, Job]], int]:
        conditions = [Application.user_id == user_id, Application.deleted_at.is_(None)]
        if status:
            conditions.append(Application.status == status)
        statement = (
            select(Application, Job).join(Job, Job.id == Application.job_id).where(*conditions)
        )
        total = self.db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
        rows = self.db.execute(
            statement.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return [(row[0], row[1]) for row in rows], int(total)

    def set_manual_status(
        self, user: User, application_id: uuid.UUID, status: str, note: str | None = None
    ) -> Application:
        application = self.get(user.id, application_id)
        if not manual_status_allowed(application.status, status):
            raise ValidationError_(
                "An application cannot be marked submitted by hand — that is recorded "
                "only when the automation observes it.",
                code="status_not_allowed",
            )
        previous = application.status
        application.status = status
        if note:
            application.notes = note
        if status in {str(state) for state in TERMINAL_APPLICATION_STATUSES}:
            application.completed_at = datetime.now(tz=UTC)
        self._step(application, "status_changed", "ok", f"{previous} → {status}")
        self._notify(
            application,
            NotificationKind.STATUS_CHANGED,
            "Application status updated",
            f"{previous} → {status}",
        )
        audit.record(
            self.db,
            action="application.status_changed",
            actor_user_id=user.id,
            entity_type="application",
            entity_id=application.id,
            data={"from": previous, "to": status},
        )
        return application

    def cancel(self, user: User, application_id: uuid.UUID) -> Application:
        application = self.get(user.id, application_id)
        if application.status in {
            str(ApplicationStatus.SUBMITTED),
            str(ApplicationStatus.CONFIRMATION_CAPTURED),
        }:
            raise ConflictError(
                "This application has already been submitted and cannot be cancelled.",
                code="already_submitted",
            )
        application.status = str(ApplicationStatus.CANCELLED)
        application.completed_at = datetime.now(tz=UTC)
        self._step(application, "cancelled", "ok", "You cancelled this application.")
        self._close_browser_sessions(application)
        for intervention in self.db.execute(
            select(Intervention).where(
                Intervention.application_id == application.id,
                Intervention.status == str(InterventionStatus.OPEN),
            )
        ).scalars():
            intervention.status = str(InterventionStatus.CANCELLED)
            intervention.resolved_at = datetime.now(tz=UTC)
        audit.record(
            self.db,
            action="application.cancelled",
            actor_user_id=user.id,
            entity_type="application",
            entity_id=application.id,
        )
        return application

    def can_retry(self, application: Application) -> bool:
        if application.attempts >= MAX_ATTEMPTS:
            return False
        if application.failure_reason is None:
            return False
        return FailureReason(application.failure_reason) in RETRYABLE_FAILURES

    # ------------------------------------------------------------------ detail
    def steps(self, application_id: uuid.UUID) -> list[ApplicationStep]:
        return list(
            self.db.execute(
                select(ApplicationStep)
                .where(ApplicationStep.application_id == application_id)
                .order_by(ApplicationStep.created_at)
            )
            .scalars()
            .all()
        )

    def questions(
        self, application_id: uuid.UUID
    ) -> list[tuple[ApplicationQuestion, ApplicationAnswer | None]]:
        rows = self.db.execute(
            select(ApplicationQuestion, ApplicationAnswer)
            .outerjoin(ApplicationAnswer, ApplicationAnswer.question_id == ApplicationQuestion.id)
            .where(ApplicationQuestion.application_id == application_id)
            .order_by(ApplicationQuestion.created_at)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def logs(self, application_id: uuid.UUID, limit: int = 100) -> list[AutomationLog]:
        return list(
            self.db.execute(
                select(AutomationLog)
                .where(AutomationLog.application_id == application_id)
                .order_by(AutomationLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def resume_version(self, application: Application) -> ResumeVersion | None:
        if application.resume_version_id is None:
            return None
        return self.db.get(ResumeVersion, application.resume_version_id)

    # ----------------------------------------------------------------- helpers
    def _step(
        self,
        application: Application,
        name: str,
        status: str,
        message: str | None = None,
        *,
        duration_ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> ApplicationStep:
        step = ApplicationStep(
            application_id=application.id,
            name=name,
            status=status,
            message=message,
            duration_ms=duration_ms,
            data=data or {},
            finished_at=datetime.now(tz=UTC),
        )
        self.db.add(step)
        return step

    def _close_browser_sessions(self, application: Application) -> None:
        now = datetime.now(tz=UTC)
        for session in self.db.execute(
            select(BrowserSession).where(
                BrowserSession.application_id == application.id,
                BrowserSession.closed_at.is_(None),
            )
        ).scalars():
            session.closed_at = now
            session.state = "closed"
            # Encrypted state is dropped with the session; nothing is kept.
            session.state_blob = None

    def _notify(
        self,
        application: Application,
        kind: NotificationKind,
        title: str,
        body: str,
        link: str | None = None,
    ) -> None:
        if self.notifications is None:
            return
        self.notifications.create(
            user_id=application.user_id,
            kind=kind,
            title=title,
            body=body,
            link=link or f"/applications/{application.id}",
            payload={"application_id": str(application.id)},
        )
