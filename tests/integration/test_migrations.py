"""Migrations must build the schema from scratch on PostgreSQL.

Skipped unless ``TEST_POSTGRES_URL`` points at a disposable database, so the default
suite stays dependency-free.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

EXPECTED_TABLES = {
    "users",
    "profiles",
    "education",
    "experience",
    "skills",
    "certifications",
    "projects",
    "resumes",
    "resume_versions",
    "jobs",
    "job_sources",
    "job_matches",
    "companies",
    "applications",
    "application_steps",
    "application_questions",
    "application_answers",
    "application_tasks",
    "browser_sessions",
    "interventions",
    "notifications",
    "automation_logs",
    "audit_logs",
    "subscriptions",
    "usage_records",
    "credentials",
    "automation_settings",
    "job_preferences",
    "oauth_accounts",
    "auth_tokens",
}


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_migrations_build_the_documented_schema():
    from alembic import command
    from alembic.config import Config

    engine = create_engine(POSTGRES_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    config = Config("packages/database/alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = POSTGRES_URL
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert tables >= EXPECTED_TABLES, f"missing: {sorted(EXPECTED_TABLES - tables)}"

    # Duplicate protection is enforced by the database, not only by application code.
    application_constraints = {c["name"] for c in inspector.get_unique_constraints("applications")}
    assert "uq_applications_user_dedupe" in application_constraints
    job_constraints = {c["name"] for c in inspector.get_unique_constraints("jobs")}
    assert "uq_jobs_dedupe_key" in job_constraints

    engine.dispose()


def test_model_metadata_covers_every_documented_table():
    """Runs everywhere: the ORM must define each table the ERD documents."""
    import jobapply_db.models  # noqa: F401
    from jobapply_db.base import Base

    assert set(Base.metadata.tables) >= EXPECTED_TABLES
