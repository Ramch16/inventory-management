"""The ``ApplicationAdapter`` interface and the shared behaviour every adapter gets.

An adapter knows one platform's quirks: where the form lives, how its controls are
named, which button submits, what a confirmation looks like. Everything else — form
analysis, mapping, answering, verification scanning — is shared, so adding a platform
means describing it, not reimplementing the pipeline.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any, Protocol, runtime_checkable

from jobapply_shared.enums import AtsKind, FieldType, InterventionType
from jobapply_shared.logging import get_logger

from jobapply_browser.detection import SIGNATURES_BY_ATS, detect_ats
from jobapply_browser.forms import analyze_page
from jobapply_browser.models import (
    ConfirmationResult,
    DetectionResult,
    FieldMapping,
    FillOutcome,
    FormSpec,
    NormalizedField,
    RunContext,
    SignInCredential,
    SignInResult,
    SubmissionResult,
    ValidationReport,
    VerificationSignal,
)
from jobapply_browser.verification import scan_page

logger = get_logger(__name__)


async def _query(page: Any, selector: str) -> Any:
    """``query_selector`` that treats an unusable selector as "not present"."""
    with suppress(Exception):
        return await page.query_selector(selector)
    return None


async def wait_for_first(
    page: Any, selectors: tuple[str, ...], *, timeout_ms: int = 5_000
) -> str | None:
    """Wait for whichever of ``selectors`` appears first.

    Trying each in turn is ordinary control flow, not error handling: a platform
    renders one of several containers depending on how the board is embedded.
    """
    for selector in selectors:
        # A selector that is simply absent is ordinary control flow here, so the
        # miss is not worth a log line of its own; the summary below covers it.
        with suppress(Exception):
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return selector
    logger.debug(
        "browser.no_container_matched",
        extra={"context": {"event": "browser.no_container_matched", "selectors": list(selectors)}},
    )
    return None


#: Ordinary sign-in controls. Nothing here targets a challenge widget.
PASSWORD_SELECTORS = ("input[type='password']",)

USERNAME_SELECTORS = (
    "input[type='email']",
    "input[name='email']",
    "input[name='username']",
    "input[id='email']",
    "input[id='username']",
    "input[autocomplete='username']",
)

SIGN_IN_SUBMIT_SELECTORS = (
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Sign in')",
    "button:has-text('Log in')",
)

CONFIRMATION_PATTERNS = (
    r"(?i)thank you for (?:your )?appl",
    r"(?i)application (?:has been )?(?:received|submitted|complete)",
    r"(?i)we(?:'ve| have) received your application",
    r"(?i)your application (?:was|has been) sent",
    r"(?i)successfully applied",
)

CONFIRMATION_ID_PATTERNS = (
    r"(?i)(?:confirmation|reference|application)\s*(?:id|number|#)\s*[:#]?\s*([A-Za-z0-9-]{4,32})",
    r"(?i)\bR-?\d{5,}\b",
)


@runtime_checkable
class ApplicationAdapter(Protocol):
    ats: AtsKind

    async def detect(self, page: Any, url: str) -> DetectionResult: ...
    async def navigate(self, page: Any, context: RunContext) -> None: ...
    async def inspect_form(self, page: Any, context: RunContext) -> FormSpec: ...
    async def map_fields(self, form: FormSpec) -> list[FieldMapping]: ...
    async def fill_field(self, page: Any, field: NormalizedField, value: str) -> FillOutcome: ...
    async def upload_resume(self, page: Any, form: FormSpec, path: str) -> FillOutcome: ...
    async def upload_cover_letter(self, page: Any, form: FormSpec, path: str) -> FillOutcome: ...
    async def sign_in(self, page: Any, credential: SignInCredential) -> SignInResult: ...
    async def validate(
        self, page: Any, context: RunContext, form: FormSpec
    ) -> ValidationReport: ...
    async def submit(self, page: Any, form: FormSpec) -> SubmissionResult: ...
    async def capture_confirmation(self, page: Any) -> ConfirmationResult: ...
    async def cleanup(self, page: Any) -> None: ...


class BaseAdapter:
    """Shared implementation. Subclasses override only what their platform changes."""

    ats: AtsKind = AtsKind.GENERIC

    # ------------------------------------------------------------------ detect
    async def detect(self, page: Any, url: str) -> DetectionResult:
        html = await page.content()
        title = await page.title()
        generator = await page.evaluate(
            "() => document.querySelector('meta[name=generator]')?.content || ''"
        )
        return detect_ats(url=url, html=html, meta_generator=generator, page_title=title)

    async def navigate(self, page: Any, context: RunContext) -> None:
        await page.goto(context.apply_url, wait_until="domcontentloaded")
        await self._after_navigate(page)

    async def _after_navigate(self, page: Any) -> None:
        """Hook for platform-specific waiting (an embedded iframe, a client-side app)."""
        return

    # -------------------------------------------------------------------- form
    def form_selectors(self) -> tuple[str, ...]:
        signature = SIGNATURES_BY_ATS.get(self.ats)
        return signature.form_selectors if signature else ("form",)

    async def inspect_form(self, page: Any, context: RunContext) -> FormSpec:
        return await analyze_page(page, ats=self.ats)

    async def map_fields(self, form: FormSpec) -> list[FieldMapping]:
        from jobapply_browser.mapping import map_fields

        return map_fields(form.fields)

    # -------------------------------------------------------------------- fill
    async def fill_field(self, page: Any, field: NormalizedField, value: str) -> FillOutcome:
        """Write one value and read it back.

        Reading back is not paranoia: client-side forms routinely reformat, reject or
        silently ignore a written value, and submitting a form we did not verify is
        how a wrong answer reaches an employer.
        """
        selector = field.selector or (f"#{field.dom_id}" if field.dom_id else None)
        if not selector:
            return FillOutcome(field_id=field.field_id, filled=False, error="no selector")

        try:
            if field.type in {FieldType.SELECT, FieldType.MULTISELECT}:
                await page.select_option(selector, value)
            elif field.type == FieldType.RADIO:
                await page.check(f"{selector}[value='{value}']")
            elif field.type == FieldType.CHECKBOX:
                if str(value).lower() in {"true", "yes", "1", "on"}:
                    await page.check(selector)
                else:
                    await page.uncheck(selector)
            else:
                await page.fill(selector, value)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            return FillOutcome(field_id=field.field_id, filled=False, error=str(exc)[:300])

        observed = await self._read_back(page, field, selector)
        matched = observed is not None and (
            observed == value or observed.strip().lower() == str(value).strip().lower()
        )
        return FillOutcome(
            field_id=field.field_id,
            filled=bool(matched),
            observed_value=observed,
            error=None if matched else "the page did not keep the value we wrote",
        )

    async def _read_back(self, page: Any, field: NormalizedField, selector: str) -> str | None:
        try:
            if field.type == FieldType.CHECKBOX:
                return "true" if await page.is_checked(selector) else "false"
            if field.type == FieldType.RADIO:
                return await page.eval_on_selector(
                    f"{selector}:checked", "element => element.value"
                )
            return await page.input_value(selector)
        except Exception:  # noqa: BLE001 - a value we cannot read is a failed fill
            return None

    async def upload_resume(self, page: Any, form: FormSpec, path: str) -> FillOutcome:
        return await self._upload(page, form, path, ("generated_resume",), "resume")

    async def upload_cover_letter(self, page: Any, form: FormSpec, path: str) -> FillOutcome:
        return await self._upload(page, form, path, ("generated_cover_letter",), "cover letter")

    async def _upload(
        self, page: Any, form: FormSpec, path: str, targets: tuple[str, ...], label: str
    ) -> FillOutcome:
        from jobapply_browser.mapping import map_field

        for field in form.fields:
            if field.type != FieldType.FILE:
                continue
            if map_field(field).target in targets:
                try:
                    await page.set_input_files(field.selector, path)
                except Exception as exc:  # noqa: BLE001
                    return FillOutcome(field_id=field.field_id, filled=False, error=str(exc)[:300])
                return FillOutcome(field_id=field.field_id, filled=True, observed_value=path)
        return FillOutcome(field_id=f"<{label}>", filled=False, error=f"no {label} upload field")

    # ----------------------------------------------------------------- sign in
    async def sign_in(self, page: Any, credential: SignInCredential) -> SignInResult:
        """Sign in to the user's own account with the credential they stored.

        This is the ordinary sign-in form and nothing else. It is attempted once, and
        it stops at the first sign of a challenge: a CAPTCHA, a one-time code or a
        multi-factor prompt ends the attempt and hands the run back to the user. No
        challenge is answered, worked around, or retried here.
        """
        password_selector = await self._first_present(page, PASSWORD_SELECTORS)
        if password_selector is None:
            return SignInResult(signed_in=False, error="no sign-in form was found on this page")

        username_selector = await self._first_present(page, USERNAME_SELECTORS)
        if username_selector is None:
            return SignInResult(
                signed_in=False, error="the sign-in form has no field for a username"
            )

        try:
            await page.fill(username_selector, credential.username)
            await page.fill(password_selector, credential.secret.get_secret_value())
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            return SignInResult(signed_in=False, error=str(exc)[:300])

        submit_selector = await self._first_present(page, SIGN_IN_SUBMIT_SELECTORS)
        if submit_selector is None:
            return SignInResult(
                signed_in=False, error="the sign-in form has no button we can identify"
            )

        try:
            await page.click(submit_selector)
            await page.wait_for_load_state("networkidle")
        except Exception as exc:  # noqa: BLE001
            return SignInResult(signed_in=False, error=str(exc)[:300])

        scan = scan_page(await page.content(), url=page.url)
        blocking = scan.blocking
        if blocking is not None:
            # Includes the case where the same sign-in form came back: wrong details
            # are the user's to correct, and a second attempt risks a lockout.
            return SignInResult(signed_in=False, blocked_by=blocking)
        return SignInResult(signed_in=True)

    async def _first_present(self, page: Any, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            if await _query(page, selector) is not None:
                return selector
        return None

    # ---------------------------------------------------------------- validate
    async def validate(self, page: Any, context: RunContext, form: FormSpec) -> ValidationReport:
        """Pre-flight check, run before anything is submitted.

        Confirms the page still belongs to the job we think we are applying to, that
        the identity on the form is the applicant's, that every required field is
        filled, and that nothing low-confidence is still waiting on a person.
        """
        missing: list[str] = []
        unresolved: list[str] = []
        mismatches: list[str] = []
        notes: list[str] = []

        required_ids = {field.field_id for field in form.required_fields()}
        for field in form.required_fields():
            answer = context.answers.get(field.field_id)
            if field.type == FieldType.FILE:
                if not context.resume_path:
                    missing.append(field.field_id)
                continue
            if answer is None or answer.answer in (None, ""):
                missing.append(field.field_id)

        for field_id, answer in context.answers.items():
            if not answer.needs_person:
                continue
            if answer.answer is not None or field_id in required_ids:
                # A draft we would actually submit, or a required question: a person
                # has to look before this form is sent.
                unresolved.append(field_id)
            else:
                # An optional question with no grounded answer is left blank rather
                # than filled with a guess.
                notes.append(f"optional question '{field_id}' was left blank")

        html = await page.content()
        expected_company = (context.metadata.get("company") or "").strip()
        expected_title = (context.metadata.get("title") or "").strip()
        if expected_company and expected_company.lower() not in html.lower():
            mismatches.append(f"the page does not mention {expected_company}")
        if expected_title and expected_title.lower() not in html.lower():
            notes.append(f"the page does not mention the job title '{expected_title}'")

        applicant_email = context.metadata.get("email")
        if applicant_email:
            filled_values = {answer.answer for answer in context.answers.values() if answer.answer}
            if applicant_email not in filled_values:
                notes.append("the applicant's e-mail was not written to this form")

        return ValidationReport(
            ok=not missing and not unresolved and not mismatches,
            missing_required=sorted(set(missing)),
            unresolved=sorted(set(unresolved)),
            mismatches=mismatches,
            notes=notes,
        )

    # ------------------------------------------------------------------ submit
    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
        )

    async def submit(self, page: Any, form: FormSpec) -> SubmissionResult:
        """Click exactly one submit control, and only after a final challenge scan."""
        scan = scan_page(await page.content(), url=page.url)
        blocking = scan.blocking
        if blocking is not None:
            return SubmissionResult(submitted=False, blocked_by=blocking)

        selectors = (
            (form.submit_selector,) if form.submit_selector else ()
        ) + self.submit_selectors()
        for selector in selectors:
            element = await _query(page, selector)
            if element is None:
                continue
            try:
                await element.click()
                await page.wait_for_load_state("networkidle")
            except Exception as exc:  # noqa: BLE001
                return SubmissionResult(submitted=False, error=str(exc)[:300])
            return SubmissionResult(submitted=True)

        return SubmissionResult(
            submitted=False,
            blocked_by=VerificationSignal(
                type=InterventionType.UNSUPPORTED_FORM,
                reason="No submit control could be identified on this form.",
            ),
        )

    # ------------------------------------------------------------ confirmation
    async def capture_confirmation(self, page: Any) -> ConfirmationResult:
        """Look for real evidence of submission.

        Without it the caller records SUBMISSION_UNCONFIRMED. The platform never
        reports an application as sent on the strength of having clicked a button.
        """
        import re

        html = await page.content()
        text = re.sub(r"<[^>]+>", " ", html)
        signals = [pattern for pattern in CONFIRMATION_PATTERNS if re.search(pattern, text)]
        confirmation_id: str | None = None
        for pattern in CONFIRMATION_ID_PATTERNS:
            match = re.search(pattern, text)
            if match:
                confirmation_id = match.group(match.lastindex or 0).strip()
                signals.append(f"id:{pattern}")
                break

        return ConfirmationResult(
            confirmed=bool(signals),
            confirmation_id=confirmation_id,
            url=page.url,
            text=re.sub(r"\s+", " ", text).strip()[:600] if signals else None,
            signals=signals,
        )

    async def cleanup(self, page: Any) -> None:
        return None
