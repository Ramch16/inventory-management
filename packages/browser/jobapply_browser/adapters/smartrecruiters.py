"""SmartRecruiters.

SmartRecruiters renders inside ``#st-app`` and marks its controls with ``data-test``
attributes.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first


class SmartRecruitersAdapter(BaseAdapter):
    ats = AtsKind.SMARTRECRUITERS

    async def _after_navigate(self, page: Any) -> None:
        await wait_for_first(
            page, ("#st-app form", "[data-test='application-form']", "form"), timeout_ms=8_000
        )

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "[data-test='submit-application']",
            "button:has-text('I'm interested')",
            "button:has-text('Apply')",
            *super().submit_selectors(),
        )
