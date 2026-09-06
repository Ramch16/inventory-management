"""iCIMS.

iCIMS embeds its application inside ``#icims_content_iframe``, so form analysis has to
run against that frame rather than the top-level document.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.enums import AtsKind

from jobapply_browser.adapters.base import BaseAdapter, wait_for_first
from jobapply_browser.forms import analyze_html
from jobapply_browser.models import FormSpec, RunContext

IFRAME_SELECTOR = "#icims_content_iframe"


class ICIMSAdapter(BaseAdapter):
    ats = AtsKind.ICIMS

    async def _after_navigate(self, page: Any) -> None:
        # Some tenants render inline instead of in the iframe; either is fine.
        await wait_for_first(page, (IFRAME_SELECTOR, "form"), timeout_ms=8_000)

    async def _content_frame(self, page: Any) -> Any:
        element = await page.query_selector(IFRAME_SELECTOR)
        if element is None:
            return page
        frame = await element.content_frame()
        return frame or page

    async def inspect_form(self, page: Any, context: RunContext) -> FormSpec:
        frame = await self._content_frame(page)
        html = await frame.content()
        spec = analyze_html(html, url=page.url, ats=self.ats)
        spec.page_title = spec.page_title or await page.title()
        return spec

    def submit_selectors(self) -> tuple[str, ...]:
        return (
            "#quickApplyBtn",
            "a.iCIMS_Anchor:has-text('Submit')",
            "button:has-text('Submit')",
            *super().submit_selectors(),
        )
