"""Declarative base, shared column types and mixins.

Every table gets a UUID primary key and timestamps. Tables holding user content also
get ``deleted_at`` so a deletion is reversible for a grace period before the purge job
removes the rows and the stored objects.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

# Explicit naming convention so Alembic autogenerate produces stable constraint names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Portable JSON column: JSONB on PostgreSQL, JSON elsewhere (SQLite in unit tests).
JSONColumn = JSON().with_variant(JSONB, "postgresql")

#: UUID column type, native on PostgreSQL and CHAR(32) on SQLite.
UUIDColumn = Uuid(as_uuid=True)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {dict[str, Any]: JSONColumn, list[Any]: JSONColumn}

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        skip = exclude or set()
        return {
            column.key: getattr(self, column.key)
            for column in self.__table__.columns
            if column.key not in skip
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        return f"<{self.__class__.__name__} id={getattr(self, 'id', None)}>"


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUIDColumn, primary_key=True, default=uuid.uuid4, sort_order=-100
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=101,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, sort_order=102
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def enum_column(length: int = 40, **kwargs: Any) -> Mapped[Any]:
    """String-backed enum column.

    Native PostgreSQL enums require a migration for every new value; the workflow in
    this platform gains states regularly, so values are stored as short strings and
    validated by Pydantic at the edges instead.
    """
    return mapped_column(String(length), **kwargs)
