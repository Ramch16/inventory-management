"""Engine and session management.

The API and the workers share this module so they observe the same pooling and the
same naming conventions. Unit tests point ``DATABASE_URL`` at SQLite; integration
tests use PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from jobapply_shared.settings import get_settings
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str | None = None, **kwargs: object) -> Engine:
    settings = get_settings()
    url = database_url or settings.database_url
    options: dict[str, object] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        # SQLite is only used for fast unit tests; a shared in-memory database needs a
        # static pool so every session sees the same schema.
        from sqlalchemy.pool import StaticPool

        options.update({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool})
    else:
        options.update(
            {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
            }
        )
    options.update(kwargs)
    engine = create_engine(url, **options)  # type: ignore[arg-type]
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return build_engine()


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for workers and scripts."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency. The request handler owns the commit."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
