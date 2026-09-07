"""Shared test configuration.

Unit and integration tests run against an in-memory SQLite database and the local
filesystem storage backend, so the whole suite runs with no external services. The
PostgreSQL-specific paths are covered by the migration test, which is skipped unless a
PostgreSQL URL is provided.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Environment must be configured before any settings-consuming module is imported.
_STORAGE_ROOT = tempfile.mkdtemp(prefix="jobapply-test-storage-")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_ROOT": _STORAGE_ROOT,
        "EMAIL_BACKEND": "console",
        "AI_PROVIDER": "mock",
        "LOG_LEVEL": "WARNING",
        "LOG_FORMAT": "console",
        "COOKIE_SECURE": "false",
    }
)

import jobapply_db.models  # noqa: E402,F401  registers every table
from fastapi.testclient import TestClient  # noqa: E402
from jobapply_api.main import create_app  # noqa: E402
from jobapply_db.base import Base  # noqa: E402
from jobapply_db.session import get_engine, get_sessionmaker  # noqa: E402
from jobapply_shared.settings import get_settings  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(autouse=True)
def database(settings) -> Iterator[None]:
    """A clean schema for every test."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def reset_process_state() -> Iterator[None]:
    """Rate limiter and e-mail outbox are process-wide singletons; give each test a
    clean one so ordering never changes an outcome."""
    from jobapply_api.deps import _email_sender, _rate_limiter

    limiter = _rate_limiter()
    if hasattr(limiter, "reset"):
        limiter.reset()
    sender = _email_sender()
    if hasattr(sender, "outbox"):
        sender.outbox.clear()
    yield


@pytest.fixture
def outbox():
    """Messages sent by the console e-mail backend during a test."""
    from jobapply_api.deps import _email_sender

    return _email_sender().outbox


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


class ApiClient:
    """TestClient wrapper that carries the CSRF header the API requires for
    cookie-authenticated writes."""

    def __init__(self, client: TestClient, prefix: str = "/api/v1") -> None:
        self._client = client
        self.prefix = prefix

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.prefix}{path}"

    def set_csrf(self, token: str) -> None:
        self._client.headers["X-CSRF-Token"] = token

    def get(self, path: str, **kwargs):
        return self._client.get(self._url(path), **kwargs)

    def post(self, path: str, **kwargs):
        return self._client.post(self._url(path), **kwargs)

    def put(self, path: str, **kwargs):
        return self._client.put(self._url(path), **kwargs)

    def patch(self, path: str, **kwargs):
        return self._client.patch(self._url(path), **kwargs)

    def delete(self, path: str, **kwargs):
        return self._client.request("DELETE", self._url(path), **kwargs)

    @property
    def raw(self) -> TestClient:
        return self._client


@pytest.fixture
def api(client: TestClient) -> ApiClient:
    return ApiClient(client)


DEFAULT_PASSWORD = "Str0ngPassword!"


@pytest.fixture
def registered(api: ApiClient) -> dict:
    """Register a user and leave the client authenticated as them."""
    response = api.post(
        "/auth/register",
        json={
            "email": "jordan@example.com",
            "password": DEFAULT_PASSWORD,
            "first_name": "Jordan",
            "last_name": "Rivera",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    api.set_csrf(payload["csrf_token"])
    return payload
