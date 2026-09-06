"""Generic fallback for application forms on employer sites.

Deliberately conservative. It fills only what deterministic mapping resolved with high
confidence, refuses to click anything it cannot identify as a submit control, and
escalates rather than guessing. It never clicks a button just because it is the only
one on the page.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from jobapply_shared.enums import AtsKind, InterventionType

from jobapply_browser.adapters.base import BaseAdapter
from jobapply_browser.detection import classify_page
from jobapply_browser.models import (
    FormSpec,
    RunContext,
    SubmissionResult,
    ValidationReport,
    VerificationSignal,
)

#: Only these words identify a submit control on an unknown site.
SUBMIT_TEXTS = (
    "submit application",
    "submit my application",
    "send application",
    "submit",
    "apply now",
)

#: Buttons that look like submits but are not.
FORBIDDEN_TEXTS = ("save", "cancel", "back", "previous", "reset", "clear", "delete")


async def _control_label(element: Any) -> str:
    """Visible text of a control, or "" if it cannot be read."""
    with suppress(Exception):
        text = await element.inner_text() or await element.get_attribute("value") or ""
        return text.strip().lower()
    return ""


class GenericAdapter(BaseAdapter):
    ats = AtsKind.GENERIC

    async def inspect_form(self, page: Any, context: RunContext) -> FormSpec:
        spec = await super().inspect_form(page, context)
        html = await page.content()
        classification = classify_page(html, field_count=len(spec.fields))
        if classification.requires_login:
            spec.submit_selector = None
        return spec

    async def validate(self, page: Any, context: RunContext, form: FormSpec) -> ValidationReport:
        report = await super().validate(page, context, form)
        html = await page.content()
        classification = classify_page(html, field_count=len(form.fields))

        if classification.requires_login:
            report.ok = False
            report.mismatches.append("this page requires an account before applying")
        elif not classification.is_application_form:
            report.ok = False
            report.mismatches.append(
                "this does not look like an application form: " + classification.reasons[0]
            )

        # On an unknown site an unmapped field is a reason to ask, not to improvise.
        from jobapply_browser.mapping import map_fields, unmapped

        leftovers = unmapped(map_fields(form.fields))
        if leftovers:
            report.ok = False
            report.unresolved.extend(mapping.field_id for mapping in leftovers)
            report.notes.append(
                f"{len(leftovers)} field(s) on this form could not be mapped confidently."
            )
        return report

    def submit_selectors(self) -> tuple[str, ...]:
        return ()

    async def submit(self, page: Any, form: FormSpec) -> SubmissionResult:
        """Click one control whose visible text names it as a submit, or stop."""
        from jobapply_browser.verification import scan_page

        scan = scan_page(await page.content(), url=page.url)
        blocking = scan.blocking
        if blocking is not None:
            return SubmissionResult(submitted=False, blocked_by=blocking)

        candidates = await page.query_selector_all("button, input[type='submit'], a[role='button']")
        matches = []
        for element in candidates:
            label = await _control_label(element)
            if not label or any(word in label for word in FORBIDDEN_TEXTS):
                continue
            if any(text == label or text in label for text in SUBMIT_TEXTS):
                matches.append((label, element))

        if not matches:
            return SubmissionResult(
                submitted=False,
                blocked_by=VerificationSignal(
                    type=InterventionType.UNSUPPORTED_FORM,
                    reason=(
                        "No control on this page clearly submits the application, so "
                        "nothing was clicked."
                    ),
                ),
            )
        if len({label for label, _ in matches}) > 1:
            return SubmissionResult(
                submitted=False,
                blocked_by=VerificationSignal(
                    type=InterventionType.UNSUPPORTED_FORM,
                    reason=(
                        "Several controls could be the submit button "
                        f"({', '.join(sorted({label for label, _ in matches}))}). "
                        "Choose the right one yourself."
                    ),
                ),
            )

        try:
            await matches[0][1].click()
            await page.wait_for_load_state("networkidle")
        except Exception as exc:  # noqa: BLE001
            return SubmissionResult(submitted=False, error=str(exc)[:300])
        return SubmissionResult(submitted=True)
