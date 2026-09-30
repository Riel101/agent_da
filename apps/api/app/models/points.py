"""Append-only points ledger.

``users.points_balance`` is a cached sum; this table is the source of truth.
Un-completing a to-do writes a *compensating negative row* rather than deleting.
``idempotency_key`` makes every award safe to retry.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models._types import JsonColumn, enum_type
from app.models.enums import LedgerReason


class PointsLedgerEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_points_ledger_idempotency"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agenda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agendas.id", ondelete="SET NULL")
    )
    sub_agenda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sub_agendas.id", ondelete="SET NULL")
    )
    todo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("todos.id", ondelete="SET NULL"))

    reason: Mapped[LedgerReason] = mapped_column(enum_type(LedgerReason), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JsonColumn)

    # The user-local date the points belong to; used for streaks and rollups.
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)

    @property
    def is_credit(self) -> bool:
        return self.delta >= 0
