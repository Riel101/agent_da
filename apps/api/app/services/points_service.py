"""Points ledger writes.

The ledger is append-only and idempotent: every award carries a deterministic
``idempotency_key``, so retries — a double-tapped button, a replayed scheduler
job, a resumed graph — can never double-award. Un-doing an award appends a
compensating negative row instead of deleting anything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Agenda, LedgerReason, PointsLedgerEntry, User

logger = get_logger(__name__)


@dataclass(slots=True)
class PointsMove:
    """Result of attempting to apply a ledger entry."""

    applied: bool
    delta: int
    balance: int
    entry: PointsLedgerEntry | None = None
    reason: LedgerReason | None = None
    meta: dict[str, Any] = field(default_factory=dict)


async def current_balance(session: AsyncSession, user_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(PointsLedgerEntry.delta), 0)).where(
            PointsLedgerEntry.user_id == user_id
        )
    )
    return int(total or 0)


async def apply(
    session: AsyncSession,
    *,
    key: str,
    user_id: uuid.UUID,
    reason: LedgerReason,
    delta: int,
    occurred_on: date,
    agenda_id: uuid.UUID | None = None,
    sub_agenda_id: uuid.UUID | None = None,
    todo_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> PointsMove:
    """Apply one ledger entry. No-op (``applied=False``) if the key already exists."""
    if delta == 0:
        return PointsMove(
            applied=False, delta=0, balance=await current_balance(session, user_id), reason=reason
        )

    entry = PointsLedgerEntry(
        user_id=user_id,
        agenda_id=agenda_id,
        sub_agenda_id=sub_agenda_id,
        todo_id=todo_id,
        reason=reason,
        delta=delta,
        meta=meta or None,
        occurred_on=occurred_on,
        idempotency_key=key,
    )
    # Savepoint so a duplicate key only rolls back this insert, not the caller's
    # whole transaction.
    try:
        async with session.begin_nested():
            session.add(entry)
            await session.flush()
    except IntegrityError:
        logger.debug("points entry %s already applied", key)
        return PointsMove(
            applied=False,
            delta=0,
            balance=await current_balance(session, user_id),
            reason=reason,
        )

    await session.execute(
        update(User).where(User.id == user_id).values(points_balance=User.points_balance + delta)
    )
    if agenda_id is not None and delta > 0:
        await session.execute(
            update(Agenda)
            .where(Agenda.id == agenda_id)
            .values(total_points=Agenda.total_points + delta)
        )

    balance = await current_balance(session, user_id)
    return PointsMove(
        applied=True,
        delta=delta,
        balance=balance,
        entry=entry,
        reason=reason,
        meta=meta or {},
    )


async def reconcile_user(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Repair the cached balance if it has drifted from the ledger."""
    balance = await current_balance(session, user_id)
    await session.execute(
        update(User).where(User.id == user_id).values(points_balance=balance)
    )
    return balance


async def summary(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(PointsLedgerEntry.reason, func.sum(PointsLedgerEntry.delta))
            .where(PointsLedgerEntry.user_id == user_id)
            .group_by(PointsLedgerEntry.reason)
        )
    ).all()

    by_reason = {reason.value if hasattr(reason, "value") else str(reason): int(total or 0) for reason, total in rows}
    earned = sum(value for value in by_reason.values() if value > 0)
    lost = sum(value for value in by_reason.values() if value < 0)
    return {
        "balance": earned + lost,
        "earned_total": earned,
        "spent_total": lost,
        "by_reason": by_reason,
    }
