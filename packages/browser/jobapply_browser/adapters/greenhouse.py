"""Greenhouse.

Greenhouse boards are ordinary server-rendered forms whose controls are named
``job_application[...]``. The board is often embedded in an employer's own page inside
``#grnhse_app``, so the adapter waits for that container before reading the form.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first


class GreenhouseAdapter(BaseAdapter):
    ats = AtsKind.GREENHOUSE

    async def _after_navigate(self, page: Any) -> None:
        await wait_for_first(
            page, ("#grnhse_app", "#application_form", "form#application-form"), timeout_ms=8_000
        )

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "#submit_app",
            "input#submit_app",
            "button#submit_app",
            "input[type='submit'][value*='Submit']",
            *super().submit_selectors(),
        )
