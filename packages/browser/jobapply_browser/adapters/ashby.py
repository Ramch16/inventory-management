"""Ashby.

Ashby renders its application client-side, so the adapter waits for the form node
rather than for navigation to settle.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first


class AshbyAdapter(BaseAdapter):
    ats = AtsKind.ASHBY

    async def _after_navigate(self, page: Any) -> None:
        await wait_for_first(page, ("[data-testid='application-form']", "form"), timeout_ms=8_000)

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "[data-testid='submit-application-button']",
            "button:has-text('Submit Application')",
            *super().submit_selectors(),
        )
