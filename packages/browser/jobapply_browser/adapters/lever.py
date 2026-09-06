"""Lever.

Lever's hosted forms use ``.application-form`` with ``data-qa`` hooks, and the apply
page is normally the posting URL with ``/apply`` appended.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first
from jobapply_browser.models import RunContext


class LeverAdapter(BaseAdapter):
    ats = AtsKind.LEVER

    async def navigate(self, page: Any, context: RunContext) -> None:
        url = context.apply_url
        # A Lever posting URL only shows the form once /apply is appended.
        if "jobs.lever.co" in url and not url.rstrip("/").endswith("/apply"):
            url = f"{url.rstrip('/')}/apply"
        await page.goto(url, wait_until="domcontentloaded")
        await self._after_navigate(page)

    async def _after_navigate(self, page: Any) -> None:
        await wait_for_first(
            page,
            ("form.application-form", "[data-qa='application-form']", "form"),
            timeout_ms=8_000,
        )

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "button[data-qa='btn-submit']",
            "button.template-btn-submit",
            "button:has-text('Submit application')",
            *super().submit_selectors(),
        )
