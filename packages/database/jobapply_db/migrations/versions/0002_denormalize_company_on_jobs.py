"""Denormalize the normalized company name onto jobs for duplicate detection.

Revision ID: 0002_normalized_company
Revises: 0001_initial
Create Date: 2026-09-06 10:37:04.813780
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_normalized_company"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Added nullable, backfilled from the existing companies row, then made NOT NULL,
    # so the migration is safe on a database that already holds jobs.
    op.add_column("jobs", sa.Column("normalized_company", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE jobs
           SET normalized_company = COALESCE(
                   (SELECT c.normalized_name FROM companies c WHERE c.id = jobs.company_id),
                   lower(jobs.company_name)
               )
         WHERE normalized_company IS NULL
        """
    )
    op.alter_column("jobs", "normalized_company", nullable=False)
    op.create_index(
        op.f("ix_jobs_normalized_company"), "jobs", ["normalized_company"], unique=False
    )
    op.create_index(
        "ix_jobs_normalized_company_title",
        "jobs",
        ["normalized_company", "normalized_title"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_normalized_company_title", table_name="jobs")
    op.drop_index(op.f("ix_jobs_normalized_company"), table_name="jobs")
    op.drop_column("jobs", "normalized_company")
