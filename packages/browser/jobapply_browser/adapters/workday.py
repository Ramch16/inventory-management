"""Workday.

Workday is a multi-step wizard behind ``data-automation-id`` attributes, and most
tenants require an account before the application form is reachable. The adapter
therefore checks for the sign-in wall first and stops there: the platform does not
create employer accounts on a user's behalf.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind, InterventionType

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first
from jobapply_browser.models import FormSpec, SubmissionResult, VerificationSignal
from jobapply_browser.verification import scan_page


class WorkdayAdapter(BaseAdapter):
    ats = AtsKind.WORKDAY

    async def _after_navigate(self, page: Any) -> None:
        await wait_for_first(
            page,
            (
                "[data-automation-id='applyFlow']",
                "[data-automation-id='jobPostingPage']",
                "form",
            ),
            timeout_ms=8_000,
        )

    async def submit(self, page: Any, form: FormSpec) -> SubmissionResult:
        scan = scan_page(await page.content(), url=page.url)
        blocking = scan.blocking
        if blocking is not None:
            return SubmissionResult(submitted=False, blocked_by=blocking)

        # A Workday application spans several steps; submitting from the wrong one
        # would send an incomplete application, so the final step must be visible.
        final_step = await page.query_selector(
            "[data-automation-id='bottom-navigation-next-button'], "
            "[data-automation-id='submitButton'], button:has-text('Submit')"
        )
        if final_step is None:
            return SubmissionResult(
                submitted=False,
                blocked_by=VerificationSignal(
                    type=InterventionType.UNSUPPORTED_FORM,
                    reason=(
                        "This Workday application has further steps that the platform "
                        "cannot complete on its own."
                    ),
                ),
            )
        return await super().submit(page, form)

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "[data-automation-id='submitButton']",
            "button:has-text('Submit')",
            *super().submit_selectors(),
        )
