"""Browser lifecycle.

Every application runs in its own browser context: separate cookies, storage and
cache. Nothing is shared between users or between runs, and a context is destroyed at
the end unless it is deliberately parked for the user to finish a verification step.

The browser is a normal Chromium with a normal user agent. There is no fingerprint
spoofing, no stealth plugin and no attempt to look like something it is not.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from jobapply_shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
DEFAULT_TIMEOUT_MS = 30_000


@dataclass
class BrowserSettings:
    headless: bool = True
    executable_path: str | None = None
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    #: How long a context parked for user verification is kept before it is reaped.
    park_ttl_seconds: int = 1800
    slow_mo_ms: int = 0


@dataclass
class ParkedSession:
    """A context held open because the user has to complete something themselves."""

    session_id: str
    context: Any
    page: Any
    expires_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserManager:
    """Owns the Playwright instance and hands out isolated contexts."""

    def __init__(self, settings: BrowserSettings | None = None) -> None:
        self.settings = settings or BrowserSettings()
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._parked: dict[str, ParkedSession] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_args: dict[str, Any] = {
            "headless": self.settings.headless,
            "slow_mo": self.settings.slow_mo_ms,
        }
        if self.settings.executable_path:
            launch_args["executable_path"] = self.settings.executable_path
        self._browser = await self._playwright.chromium.launch(**launch_args)
        logger.info(
            "browser.started",
            extra={"context": {"event": "browser.started", "headless": self.settings.headless}},
        )

    async def stop(self) -> None:
        for session_id in list(self._parked):
            await self.discard_parked(session_id)
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        logger.info("browser.stopped", extra={"context": {"event": "browser.stopped"}})

    async def _new_context(self, *, record_trace: bool = False) -> Any:
        await self.start()
        assert self._browser is not None
        context = await self._browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            accept_downloads=False,
            java_script_enabled=True,
        )
        context.set_default_timeout(self.settings.timeout_ms)
        if record_trace:
            await context.tracing.start(screenshots=True, snapshots=True)
        return context

    @asynccontextmanager
    async def session(self, *, record_trace: bool = False):
        """One isolated context for one application run.

        The context is always closed, including on failure — a leaked context keeps
        the applicant's session data alive in memory longer than it should be.
        """
        context = await self._new_context(record_trace=record_trace)
        page = await context.new_page()
        try:
            yield page
        finally:
            with_close = getattr(context, "close", None)
            if with_close is not None:
                await context.close()

    # ------------------------------------------------------------------ parking
    async def park(
        self, session_id: str, context: Any, page: Any, **metadata: Any
    ) -> ParkedSession:
        """Hold a context open so the user can finish a verification step in it."""
        async with self._lock:
            parked = ParkedSession(
                session_id=session_id,
                context=context,
                page=page,
                expires_at=datetime.now(tz=UTC) + timedelta(seconds=self.settings.park_ttl_seconds),
                metadata=metadata,
            )
            self._parked[session_id] = parked
        logger.info(
            "browser.session_parked",
            extra={
                "context": {
                    "event": "browser.session_parked",
                    "session_id": session_id,
                    "expires_at": parked.expires_at.isoformat(),
                }
            },
        )
        return parked

    def get_parked(self, session_id: str) -> ParkedSession | None:
        parked = self._parked.get(session_id)
        if parked is None:
            return None
        if parked.expires_at < datetime.now(tz=UTC):
            return None
        return parked

    async def discard_parked(self, session_id: str) -> None:
        parked = self._parked.pop(session_id, None)
        if parked is None:
            return
        try:
            await parked.context.close()
        except Exception:  # pragma: no cover - the context may already be gone
            logger.warning(
                "browser.parked_close_failed",
                extra={
                    "context": {"event": "browser.parked_close_failed", "session_id": session_id}
                },
            )

    async def reap_expired(self) -> int:
        """Close parked contexts whose TTL has passed."""
        now = datetime.now(tz=UTC)
        expired = [key for key, value in self._parked.items() if value.expires_at < now]
        for session_id in expired:
            await self.discard_parked(session_id)
        if expired:
            logger.info(
                "browser.parked_reaped",
                extra={"context": {"event": "browser.parked_reaped", "count": len(expired)}},
            )
        return len(expired)
