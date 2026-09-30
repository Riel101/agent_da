"""Shared column types."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import JSON, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB

#: JSON that becomes JSONB on Postgres and stays TEXT-backed JSON elsewhere.
JsonColumn = JSON().with_variant(JSONB, "postgresql")


def enum_type(enum_cls: type[PyEnum]) -> SAEnum:
    """Portable enum column: VARCHAR + CHECK constraint, values not member names."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=32,
        validate_strings=True,
        values_callable=lambda e: [member.value for member in e],
    )


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}
