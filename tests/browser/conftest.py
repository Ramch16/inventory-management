"""Browser test fixtures.

These tests drive a real Chromium against the local mock ATS sites in
``tests/mock_ats``. They never touch a real employer. The suite skips itself when
Playwright or a browser binary is unavailable, so the default test run stays
dependency-free.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest

from tests.mock_ats.server import MockAtsServer

pytestmark = pytest.mark.browser


def _chromium_path() -> str | None:
    """Find an installed Chromium, preferring an explicitly configured one."""
    configured = os.environ.get("BROWSER_EXECUTABLE_PATH")
    if configured and os.path.exists(configured):
        return configured
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root), reverse=True):
            candidate = os.path.join(root, entry, "chrome-linux", "chrome")
            if os.path.exists(candidate):
                return candidate
    return None


@pytest.fixture(scope="session")
def chromium_path() -> str:
    pytest.importorskip("playwright", reason="playwright is not installed")
    path = _chromium_path()
    if not path:
        pytest.skip("no Chromium binary available for browser tests")
    return path


@pytest.fixture(scope="session")
def mock_ats() -> Iterator[MockAtsServer]:
    with MockAtsServer() as server:
        yield server


@pytest.fixture
def run_async():
    """Run one coroutine per test on a fresh event loop."""

    def _run(coro):
        return asyncio.run(coro)

    return _run


@pytest.fixture
def browser_manager(chromium_path):
    from jobapply_browser.manager import BrowserManager, BrowserSettings

    return BrowserManager(
        BrowserSettings(headless=True, executable_path=chromium_path, timeout_ms=15_000)
    )
