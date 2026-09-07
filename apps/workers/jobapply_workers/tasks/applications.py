"""The automation worker.

This is the only place a browser is driven. It reloads everything it needs from the
database, runs one pass of the pipeline, writes the result back, and closes the
context. Nothing about the run is carried in the queue message except identifiers and,
for one step only, a one-time code that is used and discarded.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import shared_task
from jobapply_api.services.application_service import ApplicationService
from jobapply_api.services.notification_service import NotificationService
from jobapply_api.services.policy import ApplicationPolicy, next_delay_seconds
from jobapply_api.services.profile_service import ProfileService
from jobapply_browser.engine import ApplicationRunner
from jobapply_browser.manager import BrowserManager, BrowserSettings
from jobapply_browser.models import RunContext, SignInCredential
from jobapply_browser.questions import AnswerContext, ApplicationQuestionService
from jobapply_browser.verification import redact_html
from jobapply_db.models import (
    Application,
    ApplicationAnswer,
    ApplicationQuestion,
    ApplicationTask,
    AutomationSettings,
    Job,
    ResumeVersion,
    User,
)
from jobapply_db.session import session_scope
from jobapply_shared.email import build_email_sender
from jobapply_shared.enums import ApplicationStatus, AtsKind, FailureReason, TaskStatus
from jobapply_shared.errors import TransientError
from jobapply_shared.logging import get_logger
from jobapply_shared.settings import get_settings
from jobapply_shared.storage import build_storage
from sqlalchemy import select

logger = get_logger(__name__)


def _credential_for(db, user: User, apply_url: str, settings) -> SignInCredential | None:
    """The user's stored sign-in details for this site, if they have any.

    Decryption happens here, in the worker, and the plaintext lives only inside the
    ``SignInCredential`` that is handed to the run. It is never written to the task
    payload, the run report, the audit entry or a log line. Without a match the run
    simply pauses at a sign-in wall, which is the default.
    """
    from urllib.parse import urlparse

    from jobapply_api.services.credential_service import CredentialVault

    host = (urlparse(apply_url).hostname or "").lower().removeprefix("www.")
    if not host:
        return None

    vault = CredentialVault(db, secret_key=settings.secret_key)
    for credential in vault.list_for(user.id):
        if not credential.host or not credential.secret_encrypted or not credential.username:
            continue
        # A credential for "acme.com" also covers "careers.acme.com".
        if host != credential.host and not host.endswith(f".{credential.host}"):
            continue
        secret = vault.reveal(user.id, credential.id)
        if secret is None:
            continue
        return SignInCredential(
            credential_id=str(credential.id),
            username=credential.username,
            secret=secret,
            host=credential.host,
        )
    return None


def _answer_context(db, user: User, job: Job) -> AnswerContext:
    profile_service = ProfileService(db)
    profile = profile_service.get(user.id)
    skills = profile_service.list_skills(user.id)
    education = profile_service.list_education(user.id)
    experiences = profile_service.list_experience(user.id)

    return AnswerContext(
        profile={
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "preferred_name": profile.preferred_name,
            "email": profile.email or user.email,
            "phone": profile.phone,
            "city": profile.city,
            "state": profile.state,
            "country": profile.country,
            "postal_code": profile.postal_code,
            "linkedin_url": profile.linkedin_url,
            "github_url": profile.github_url,
            "portfolio_url": profile.portfolio_url,
            "current_title": profile.current_title,
            "years_experience": float(profile.years_experience)
            if profile.years_experience is not None
            else None,
            "salary_min": profile.salary_min,
            "requires_sponsorship_now": profile.requires_sponsorship_now,
            "requires_sponsorship_future": profile.requires_sponsorship_future,
        },
        skill_years={
            skill.normalized_name: float(skill.years_experience)
            for skill in skills
            if skill.years_experience is not None
        },
        education=[{"institution": item.institution, "degree": item.degree} for item in education],
        experiences=[
            {
                "company": item.company,
                "title": item.title,
                "is_current": item.is_current,
            }
            for item in experiences
        ],
        job={"title": job.title, "company_name": job.company_name},
        saved_answers=_saved_answers(db, user.id),
    )


def _saved_answers(db, user_id: uuid.UUID) -> dict[str, str]:
    """Answers the user has previously written and approved, reusable across forms."""
    from jobapply_shared.text import normalize_text

    rows = db.execute(
        select(ApplicationQuestion.question, ApplicationAnswer.answer)
        .join(ApplicationAnswer, ApplicationAnswer.question_id == ApplicationQuestion.id)
        .join(Application, Application.id == ApplicationQuestion.application_id)
        .where(
            Application.user_id == user_id,
            ApplicationAnswer.approved_by_user_at.is_not(None),
            ApplicationAnswer.answer.is_not(None),
            ApplicationQuestion.is_sensitive.is_(False),
        )
    ).all()
    return {normalize_text(question): answer for question, answer in rows if question}


def _materialise_resume(storage, version: ResumeVersion, directory: Path) -> str | None:
    if version is None or not version.pdf_storage_key:
        return None
    path = directory / "resume.pdf"
    path.write_bytes(storage.get(version.pdf_storage_key))
    return str(path)


def _materialise_cover_letter(storage, version: ResumeVersion, directory: Path) -> str | None:
    if version is None or not version.cover_letter_storage_key:
        return None
    path = directory / "cover-letter.txt"
    path.write_bytes(storage.get(version.cover_letter_storage_key))
    return str(path)


@shared_task(
    name="apply.run",
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_application(self, task_id: str, otp_code: str | None = None) -> dict:
    """Execute one application run.

    Retries cover transient and network failures only. A CAPTCHA, an OTP prompt, a
    sign-in wall, an unsupported form or missing data are not retried: they need a
    person, and retrying would just burn attempts.
    """
    settings = get_settings()
    storage = build_storage(settings)

    with session_scope() as db:
        task = db.get(ApplicationTask, uuid.UUID(task_id))
        if task is None or task.status not in {str(TaskStatus.QUEUED), str(TaskStatus.RUNNING)}:
            return {"skipped": "task_not_runnable"}

        application = db.get(Application, task.application_id)
        if application is None or application.deleted_at is not None:
            task.status = str(TaskStatus.CANCELLED)
            return {"skipped": "application_missing"}

        user = db.get(User, task.user_id)
        job = db.get(Job, application.job_id)
        if user is None or job is None:
            task.status = str(TaskStatus.CANCELLED)
            return {"skipped": "user_or_job_missing"}

        # The global pause is honoured at the last possible moment, so pressing it
        # stops work already sitting in the queue.
        if user.automation_paused:
            task.status = str(TaskStatus.CANCELLED)
            task.failure_reason = str(FailureReason.POLICY_BLOCKED)
            task.failure_detail = "Automation is paused for this account."
            application.status = str(ApplicationStatus.APPROVED)
            return {"skipped": "automation_paused"}

        decision = ApplicationPolicy(db).evaluate(user, job)
        blocking = [
            violation
            for violation in decision.violations
            if not (
                violation.code == "already_applied"
                and violation.details.get("application_id") == str(application.id)
            )
        ]
        if blocking:
            task.status = str(TaskStatus.CANCELLED)
            task.failure_reason = str(FailureReason.POLICY_BLOCKED)
            task.failure_detail = blocking[0].message
            application.status = str(ApplicationStatus.FAILED)
            application.failure_reason = str(FailureReason.POLICY_BLOCKED)
            application.failure_detail = blocking[0].message
            return {"blocked": blocking[0].code}

        task.status = str(TaskStatus.RUNNING)
        task.started_at = datetime.now(tz=UTC)

        automation = db.execute(
            select(AutomationSettings).where(AutomationSettings.user_id == user.id)
        ).scalar_one_or_none()
        version = (
            db.get(ResumeVersion, application.resume_version_id)
            if application.resume_version_id
            else None
        )
        answer_context = _answer_context(db, user, job)
        service = ApplicationService(
            db, NotificationService(db, build_email_sender(settings)), storage
        )

        with tempfile.TemporaryDirectory(prefix="jobapply-run-") as workdir:
            directory = Path(workdir)
            context = RunContext(
                application_id=str(application.id),
                user_id=str(user.id),
                job_id=str(job.id),
                apply_url=application.apply_url or job.apply_url or "",
                ats=AtsKind(application.detected_ats or job.detected_ats or AtsKind.GENERIC),
                auto_submit=application.auto_submit and not application.requires_review,
                resume_path=_materialise_resume(storage, version, directory),
                cover_letter_path=_materialise_cover_letter(storage, version, directory),
                credential=_credential_for(
                    db, user, application.apply_url or job.apply_url or "", settings
                ),
                metadata={
                    "company": job.company_name,
                    "title": job.title,
                    "email": answer_context.profile.get("email"),
                },
            )
            # A code supplied for this one step is used here and never persisted.
            if otp_code:
                answer_context.saved_answers["one-time code"] = otp_code

            report = asyncio.run(
                _drive(context, answer_context, automation, settings, storage, application)
            )

        service.apply_run_report(application, report)

        task.status = (
            str(TaskStatus.SUCCEEDED) if report.failure_reason is None else str(TaskStatus.FAILED)
        )
        task.completed_at = datetime.now(tz=UTC)
        task.failure_reason = str(report.failure_reason) if report.failure_reason else None
        task.failure_detail = report.failure_detail

        result = {
            "status": str(report.status),
            "state": str(report.state),
            "intervention": str(report.intervention.type) if report.intervention else None,
        }

    if (
        report.failure_reason is not None
        and report.failure_reason in {FailureReason.TRANSIENT_ERROR, FailureReason.NETWORK_ERROR}
        and self.request.retries < (self.max_retries or 0)
    ):
        raise self.retry(
            exc=TransientError(report.failure_detail or "transient failure"),
            countdown=next_delay_seconds(automation),
        )
    return result


async def _drive(
    context: RunContext,
    answer_context: AnswerContext,
    automation: AutomationSettings | None,
    settings: Any,
    storage: Any,
    application: Application,
):
    """Open a context, run the pipeline, capture a screenshot on any stop."""
    manager = BrowserManager(
        BrowserSettings(
            headless=settings.browser_headless,
            executable_path=settings.browser_executable_path,
            park_ttl_seconds=settings.browser_session_ttl_seconds,
        )
    )
    question_service = ApplicationQuestionService(
        auto_threshold=(
            automation.confidence_auto_threshold
            if automation
            else settings.confidence_auto_threshold
        ),
        review_threshold=(
            automation.confidence_review_threshold
            if automation
            else settings.confidence_review_threshold
        ),
    )
    runner = ApplicationRunner(question_service=question_service)

    try:
        async with manager.session() as page:
            report = await runner.run(page, context, answer_context)

            # A screenshot is captured whenever the run stops, so the user can see
            # exactly what the automation saw.
            if report.intervention is not None or report.failure_reason is not None:
                try:
                    shot = await page.screenshot(full_page=True)
                    key = (
                        f"screenshots/{application.user_id}/{application.id}/{uuid.uuid4().hex}.png"
                    )
                    storage.put(key, shot, "image/png")
                    report.step("screenshot", "ok", data={"key": key})
                    if report.intervention is not None:
                        report.intervention.payload["screenshot_key"] = key
                    report.page_url = page.url
                except Exception:  # noqa: BLE001 - a missing screenshot is not fatal
                    logger.warning(
                        "automation.screenshot_failed",
                        extra={"context": {"event": "automation.screenshot_failed"}},
                    )

                # Page source, when kept at all for debugging, is redacted first.
                try:
                    snapshot_key = store_debug_snapshot(storage, application, await page.content())
                    report.steps.append(_debug_step(snapshot_key))
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "automation.snapshot_failed",
                        extra={"context": {"event": "automation.snapshot_failed"}},
                    )
            return report
    finally:
        await manager.stop()


def _debug_step(key: str):
    from jobapply_browser.engine import StepRecord

    return StepRecord(name="debug_snapshot", status="ok", data={"key": key})


@shared_task(name="apply.resume_after_verification", bind=True, max_retries=3)
def resume_after_verification(self, task_id: str, otp_code: str | None = None) -> dict:
    """Continue a run the user has just unblocked."""
    return run_application(task_id=task_id, otp_code=otp_code)


@shared_task(name="apply.cleanup_sessions", bind=True)
def cleanup_sessions(self) -> dict:
    """Close browser sessions whose verification window has passed."""
    from jobapply_db.models import BrowserSession

    settings = get_settings()
    closed = 0
    with session_scope() as db:
        now = datetime.now(tz=UTC)
        for session in db.execute(
            select(BrowserSession).where(
                BrowserSession.closed_at.is_(None), BrowserSession.expires_at < now
            )
        ).scalars():
            session.closed_at = now
            session.state = "expired"
            session.state_blob = None
            closed += 1
    logger.info(
        "automation.sessions_reaped",
        extra={
            "context": {
                "event": "automation.sessions_reaped",
                "closed": closed,
                "ttl": settings.browser_session_ttl_seconds,
            }
        },
    )
    return {"closed": closed}


def store_debug_snapshot(storage, application: Application, html: str) -> str:
    """Store a redacted page source for a failed run."""
    key = f"debug/{application.user_id}/{application.id}/{uuid.uuid4().hex}.html"
    storage.put(key, redact_html(html).encode("utf-8"), "text/html")
    return key
