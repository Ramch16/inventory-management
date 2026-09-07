"""The application run.

One pass through the pipeline, expressed as a state machine whose every stop is
explicit:

    navigate → detect → inspect → map → answer → fill → upload → validate
             → (submit | pause) → confirm

The run stops — it does not improvise — on a CAPTCHA, an MFA or OTP prompt, a sign-in
wall, a legal attestation, an unmapped field on an unknown site, a low-confidence
answer, or a validation failure. Each stop produces an ``InterventionRequest`` naming
what a person has to do.

This module owns no database and no HTTP: it takes inputs and returns a report, which
makes the whole run testable against local mock sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jobapply_shared.enums import (
    ApplicationStatus,
    AtsKind,
    AutomationRunState,
    FailureReason,
    FieldType,
    InterventionType,
)
from jobapply_shared.logging import get_logger, log_event

from jobapply_browser.adapters import BaseAdapter, get_adapter
from jobapply_browser.models import (
    ConfirmationResult,
    DetectionResult,
    FieldMapping,
    FillOutcome,
    FormSpec,
    ResolvedAnswer,
    RunContext,
    ValidationReport,
    VerificationSignal,
)
from jobapply_browser.questions import AnswerContext, ApplicationQuestionService
from jobapply_browser.verification import scan_page

logger = get_logger(__name__)


@dataclass
class InterventionRequest:
    type: InterventionType
    reason: str
    current_step: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    name: str
    status: str
    message: str | None = None
    duration_ms: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    """Everything one run produced, for persistence and for the user's timeline."""

    state: AutomationRunState = AutomationRunState.RUNNING
    status: ApplicationStatus = ApplicationStatus.APPLICATION_STARTING
    detection: DetectionResult | None = None
    form: FormSpec | None = None
    mappings: list[FieldMapping] = field(default_factory=list)
    answers: list[ResolvedAnswer] = field(default_factory=list)
    fills: list[FillOutcome] = field(default_factory=list)
    validation: ValidationReport | None = None
    confirmation: ConfirmationResult | None = None
    intervention: InterventionRequest | None = None
    failure_reason: FailureReason | None = None
    failure_detail: str | None = None
    steps: list[StepRecord] = field(default_factory=list)
    screenshot: bytes | None = None
    page_url: str | None = None
    page_title: str | None = None

    def step(self, name: str, status: str, message: str | None = None, **data: Any) -> None:
        self.steps.append(StepRecord(name=name, status=status, message=message, data=data))


class ApplicationRunner:
    """Drives one application from an open page to a submitted (or paused) state."""

    def __init__(
        self,
        *,
        question_service: ApplicationQuestionService,
        enabled_adapters: frozenset[AtsKind] | None = None,
    ) -> None:
        self.question_service = question_service
        self.enabled_adapters = enabled_adapters

    async def _try_sign_in(
        self,
        page: Any,
        context: RunContext,
        report: RunReport,
        blocking: VerificationSignal,
        adapter: BaseAdapter,
    ) -> VerificationSignal | None:
        """Sign in, but only for a plain sign-in wall and only with a stored credential.

        Every other blocking signal — a CAPTCHA, a one-time code, a multi-factor
        prompt — is returned untouched so the run pauses. Signing in here is the user
        acting through the platform on their own account; it is never a way past a
        control the employer put in front of that account.
        """
        if blocking.type is not InterventionType.AUTHENTICATION_REQUIRED:
            return blocking
        if context.credential is None:
            return blocking

        result = await adapter.sign_in(page, context.credential)
        report.step(
            "sign_in",
            "ok" if result.signed_in else "paused",
            message=result.error,
            data={"credential_id": context.credential.credential_id},
        )
        if result.signed_in:
            report.page_url = page.url
            # The page changed; whatever is in front of us now decides the run.
            return scan_page(await page.content(), url=page.url).blocking
        return result.blocked_by or VerificationSignal(
            type=InterventionType.AUTHENTICATION_REQUIRED,
            reason=(
                "Signing in with your stored credential did not work: "
                f"{result.error or 'the site did not accept it'}. Sign in yourself, or "
                "update the credential in Settings."
            ),
        )

    async def run(
        self,
        page: Any,
        context: RunContext,
        answer_context: AnswerContext,
        *,
        adapter: BaseAdapter | None = None,
    ) -> RunReport:
        report = RunReport()
        started = datetime.now(tz=UTC)

        try:
            chosen = adapter or get_adapter(context.ats, enabled=self.enabled_adapters)

            # -- navigate ---------------------------------------------------
            await chosen.navigate(page, context)
            report.page_url = page.url
            report.step("navigate", "ok", data={"url": page.url})

            # A challenge on arrival stops everything before a single keystroke.
            blocking = scan_page(await page.content(), url=page.url).blocking
            if blocking is not None:
                blocking = await self._try_sign_in(page, context, report, blocking, chosen)
            if blocking is not None:
                return self._pause(report, blocking, "navigate")

            # -- detect -----------------------------------------------------
            detection = await chosen.detect(page, page.url)
            report.detection = detection
            if detection.ats is not chosen.ats and detection.ats is not AtsKind.GENERIC:
                # The URL suggested one platform and the page proved another.
                chosen = get_adapter(detection.ats, enabled=self.enabled_adapters)
                context.ats = detection.ats
            report.step(
                "detect", "ok", data={"ats": str(detection.ats), "confidence": detection.confidence}
            )

            # -- inspect ----------------------------------------------------
            form = await chosen.inspect_form(page, context)
            report.form = form
            report.page_title = form.page_title
            if not form.fields:
                return self._pause(
                    report,
                    VerificationSignal(
                        type=InterventionType.UNSUPPORTED_FORM,
                        reason="No application form could be found on this page.",
                    ),
                    "inspect_form",
                )
            report.step("inspect_form", "ok", data={"fields": len(form.fields)})

            # -- map and answer ---------------------------------------------
            mappings = await chosen.map_fields(form)
            report.mappings = mappings
            # File inputs are filled by the upload step, not by the question engine.
            answerable = [field_ for field_ in form.fields if field_.type is not FieldType.FILE]
            answers = await self.question_service.answer_all(answerable, mappings, answer_context)
            report.answers = answers
            context.answers = {answer.field_id: answer for answer in answers}
            report.step(
                "map_fields",
                "ok",
                data={
                    "mapped": sum(1 for mapping in mappings if mapping.target),
                    "unmapped": sum(1 for mapping in mappings if not mapping.target),
                },
            )

            needs_person = [answer for answer in answers if answer.needs_person]
            required_ids = {field_.field_id for field_ in form.required_fields()}
            blocking_answers = [
                answer
                for answer in needs_person
                if answer.field_id in required_ids or answer.is_sensitive
            ]
            if blocking_answers:
                return self._pause_for_answers(report, blocking_answers, form)

            # -- fill -------------------------------------------------------
            for field_ in form.fields:
                answer = context.answers.get(field_.field_id)
                if answer is None or not answer.can_autofill:
                    continue
                outcome = await chosen.fill_field(page, field_, answer.answer or "")
                report.fills.append(outcome)
            filled = sum(1 for outcome in report.fills if outcome.filled)
            report.step("fill_form", "ok", data={"filled": filled, "attempted": len(report.fills)})

            failed_fills = [outcome for outcome in report.fills if not outcome.filled]
            if failed_fills:
                return self._fail(
                    report,
                    FailureReason.EMPLOYER_ERROR,
                    "The page did not accept "
                    f"{len(failed_fills)} value(s): "
                    + ", ".join(outcome.field_id for outcome in failed_fills[:5]),
                )

            # -- upload -----------------------------------------------------
            if context.resume_path:
                outcome = await chosen.upload_resume(page, form, context.resume_path)
                report.fills.append(outcome)
                report.step(
                    "upload_resume", "ok" if outcome.filled else "failed", message=outcome.error
                )
                if not outcome.filled and any(
                    field_.type.value == "file" and field_.required for field_ in form.fields
                ):
                    return self._fail(
                        report,
                        FailureReason.UNSUPPORTED_FORM,
                        outcome.error or "resume upload failed",
                    )
            if context.cover_letter_path:
                outcome = await chosen.upload_cover_letter(page, form, context.cover_letter_path)
                report.step(
                    "upload_cover_letter",
                    "ok" if outcome.filled else "skipped",
                    message=outcome.error,
                )

            # -- validate ---------------------------------------------------
            validation = await chosen.validate(page, context, form)
            report.validation = validation
            report.step(
                "validate",
                "ok" if validation.ok else "blocked",
                data={
                    "missing": validation.missing_required,
                    "unresolved": validation.unresolved,
                    "mismatches": validation.mismatches,
                },
            )
            if not validation.ok:
                return self._pause(
                    report,
                    VerificationSignal(
                        type=InterventionType.LOW_CONFIDENCE
                        if validation.unresolved
                        else InterventionType.UNSUPPORTED_FORM,
                        reason=self._validation_reason(validation),
                    ),
                    "validate",
                    payload={
                        "missing_required": validation.missing_required,
                        "unresolved": validation.unresolved,
                        "mismatches": validation.mismatches,
                    },
                )

            # -- submit -----------------------------------------------------
            if not context.auto_submit:
                report.state = AutomationRunState.WAITING_FOR_USER
                report.status = ApplicationStatus.READY_TO_SUBMIT
                report.step("ready_to_submit", "ok", message="waiting for your approval")
                report.intervention = InterventionRequest(
                    type=InterventionType.LOW_CONFIDENCE,
                    reason=(
                        "The form is filled and checked. Review it and submit when you are ready."
                    ),
                    current_step="ready_to_submit",
                    payload={"answers": [answer.model_dump(mode="json") for answer in answers]},
                )
                return report

            report.status = ApplicationStatus.SUBMITTING
            submission = await chosen.submit(page, form)
            if submission.blocked_by is not None:
                return self._pause(report, submission.blocked_by, "submit")
            if not submission.submitted:
                return self._fail(
                    report, FailureReason.EMPLOYER_ERROR, submission.error or "submission failed"
                )
            report.step("submit", "ok")

            # -- confirm ----------------------------------------------------
            confirmation = await chosen.capture_confirmation(page)
            report.confirmation = confirmation
            report.page_url = page.url
            if confirmation.confirmed:
                report.status = ApplicationStatus.CONFIRMATION_CAPTURED
                report.state = AutomationRunState.COMPLETED
                report.step("capture_confirmation", "ok", data={"signals": confirmation.signals})
            else:
                # The click succeeded but nothing proves the employer received it.
                report.status = ApplicationStatus.SUBMISSION_UNCONFIRMED
                report.state = AutomationRunState.COMPLETED
                report.step(
                    "capture_confirmation",
                    "unconfirmed",
                    message=(
                        "No confirmation was visible, so this is recorded as unconfirmed "
                        "rather than applied."
                    ),
                )
            return report

        except Exception as exc:  # noqa: BLE001 - every failure is reported, never raised out
            logger.exception("automation.run_failed")
            return self._fail(report, self._classify(exc), str(exc)[:500])
        finally:
            log_event(
                logger,
                "automation.run_finished",
                user_id=context.user_id,
                application_id=context.application_id,
                job_id=context.job_id,
                ats=str(context.ats),
                status=str(report.status),
                duration_ms=int((datetime.now(tz=UTC) - started).total_seconds() * 1000),
            )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _validation_reason(validation: ValidationReport) -> str:
        parts: list[str] = []
        if validation.missing_required:
            parts.append(f"{len(validation.missing_required)} required field(s) are still empty")
        if validation.unresolved:
            parts.append(f"{len(validation.unresolved)} answer(s) need your review")
        if validation.mismatches:
            parts.append(validation.mismatches[0])
        return "; ".join(parts) or "the form did not pass its pre-submission check"

    def _pause(
        self,
        report: RunReport,
        signal: VerificationSignal,
        step: str,
        payload: dict[str, Any] | None = None,
    ) -> RunReport:
        report.state = {
            InterventionType.CAPTCHA: AutomationRunState.CAPTCHA_REQUIRED,
            InterventionType.OTP: AutomationRunState.OTP_REQUIRED,
            InterventionType.MFA: AutomationRunState.MFA_REQUIRED,
            InterventionType.UNSUPPORTED_FORM: AutomationRunState.UNSUPPORTED_FORM,
            InterventionType.LOW_CONFIDENCE: AutomationRunState.LOW_CONFIDENCE,
        }.get(signal.type, AutomationRunState.WAITING_FOR_USER)
        report.status = ApplicationStatus.WAITING_FOR_VERIFICATION
        report.intervention = InterventionRequest(
            type=signal.type,
            reason=signal.reason,
            current_step=step,
            payload={"evidence": signal.evidence, **(payload or {})},
        )
        report.step(step, "paused", message=signal.reason)
        return report

    def _pause_for_answers(
        self, report: RunReport, answers: list[ResolvedAnswer], form: FormSpec
    ) -> RunReport:
        labels = {field_.field_id: (field_.question or field_.label) for field_ in form.fields}
        sensitive = [answer for answer in answers if answer.is_sensitive]
        reason = (
            "Some questions need you: "
            + ", ".join(
                f"“{labels.get(answer.field_id) or answer.field_id}”" for answer in answers[:3]
            )
            + ("." if len(answers) <= 3 else f" and {len(answers) - 3} more.")
        )
        report.state = (
            AutomationRunState.WAITING_FOR_USER if sensitive else AutomationRunState.LOW_CONFIDENCE
        )
        report.status = ApplicationStatus.WAITING_FOR_VERIFICATION
        report.intervention = InterventionRequest(
            type=InterventionType.LEGAL_ATTESTATION
            if any(
                answer.category.value in {"legal_attestation", "criminal_history"}
                for answer in sensitive
            )
            else (
                InterventionType.MISSING_DATA
                if any(answer.answer is None for answer in answers)
                else InterventionType.LOW_CONFIDENCE
            ),
            reason=reason,
            current_step="answer_questions",
            payload={
                "questions": [
                    {
                        "field_id": answer.field_id,
                        "question": labels.get(answer.field_id),
                        "draft": answer.answer,
                        "confidence": answer.confidence,
                        "category": str(answer.category),
                        "is_sensitive": answer.is_sensitive,
                        "reason": answer.reason,
                        "options": [
                            option.model_dump()
                            for field_ in form.fields
                            if field_.field_id == answer.field_id
                            for option in field_.options
                        ],
                    }
                    for answer in answers
                ]
            },
        )
        report.step("answer_questions", "paused", message=reason)
        return report

    def _fail(self, report: RunReport, reason: FailureReason, detail: str) -> RunReport:
        report.state = AutomationRunState.FAILED
        report.status = ApplicationStatus.FAILED
        report.failure_reason = reason
        report.failure_detail = detail
        report.step("failed", "failed", message=detail)
        return report

    @staticmethod
    def _classify(exc: Exception) -> FailureReason:
        text = f"{type(exc).__name__}: {exc}".lower()
        if "timeout" in text:
            return FailureReason.TRANSIENT_ERROR
        if any(word in text for word in ("net::", "connection", "dns", "socket")):
            return FailureReason.NETWORK_ERROR
        return FailureReason.EMPLOYER_ERROR
