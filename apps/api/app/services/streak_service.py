"""Streaks, day closing and missed-day penalties.

Product decisions baked in here:

* A day counts toward the streak only when it had at least one to-do and **all**
  of them were completed.
* Days with nothing scheduled are skipped, not penalised.
* A missed day is worth ``-settings.missed_day_deduction`` points (5 by default)
  and resets ``current_streak``; already-earned points are never removed.
* Overdue tasks are *not* carried forward — the day is simply marked missed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.timezones import local_today
from app.models import Agenda, AgendaStatus, LedgerReason, SubAgenda, SubAgendaStatus, Todo, User
from app.services import points_service

logger = get_logger(__name__)

STREAK_LOOKBACK_DAYS = 400


@dataclass(slots=True)
class DayCount:
    total: int
    done: int

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.done == self.total


async def day_completion_map(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    start: date,
    end: date,
) -> dict[date, DayCount]:
    """``{date: DayCount}`` for every day the user had work scheduled."""
    rows = (
        await session.execute(
            select(
                SubAgenda.scheduled_date,
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
            )
            .join(Todo, Todo.sub_agenda_id == SubAgenda.id)
            .where(
                Todo.user_id == user_id,
                SubAgenda.scheduled_date >= start,
                SubAgenda.scheduled_date <= end,
            )
            .group_by(SubAgenda.scheduled_date)
        )
    ).all()

    return {
        row[0]: DayCount(total=int(row[1] or 0), done=int(row[2] or 0))
        for row in rows
    }


async def recompute(
    session: AsyncSession,
    user: User,
    *,
    through_date: date | None = None,
) -> int:
    """Recompute ``current_streak`` walking backwards from ``through_date``."""
    end = through_date or local_today(user.timezone)
    start = end - timedelta(days=STREAK_LOOKBACK_DAYS)

    counts = await day_completion_map(session, user.id, start=start, end=end)

    streak = 0
    cursor = end
    floor = start
    while cursor >= floor:
        count = counts.get(cursor)
        if count is None:
            # Nothing scheduled: skip, don't break, so agenda gaps are forgiving.
            cursor -= timedelta(days=1)
            continue
        if not count.complete:
            break
        streak += 1
        cursor -= timedelta(days=1)

    user.current_streak = streak
    user.longest_streak = max(user.longest_streak, streak)
    return streak


async def award_milestones(
    session: AsyncSession,
    user: User,
    *,
    occurred_on: date,
) -> int:
    """Award the streak bonus when the streak hits a milestone multiple."""
    every = settings.streak_milestone_every
    if every <= 0 or user.current_streak <= 0 or user.current_streak % every != 0:
        return 0

    move = await points_service.apply(
        session,
        key=f"streak:{user.id}:{user.current_streak}",
        user_id=user.id,
        reason=LedgerReason.STREAK_BONUS,
        delta=settings.streak_milestone_bonus,
        occurred_on=occurred_on,
        meta={"streak": user.current_streak},
    )
    return move.delta if move.applied else 0


async def close_day(session: AsyncSession, agenda: Agenda, day: date) -> dict[str, int]:
    """Finalise one finished day: mark it done or missed, and apply penalties."""
    sub = await session.scalar(
        select(SubAgenda)
        .where(SubAgenda.agenda_id == agenda.id, SubAgenda.scheduled_date == day)
        .with_for_update()
    )
    if sub is None:
        return {"closed": 0, "missed": 0, "penalty": 0}

    stats = {"closed": 1, "missed": 0, "penalty": 0}
    counts = await session.scalar(
        select(func.count(Todo.id)).where(Todo.sub_agenda_id == sub.id)
    )
    done = await session.scalar(
        select(func.count(Todo.id)).where(
            Todo.sub_agenda_id == sub.id, Todo.is_done.is_(True)
        )
    )
    total = int(counts or 0)
    completed = int(done or 0)

    if total > 0 and completed == total:
        if sub.status is not SubAgendaStatus.DONE:
            sub.status = SubAgendaStatus.DONE
    else:
        sub.status = SubAgendaStatus.MISSED
        stats["missed"] = 1
        if settings.allow_point_deductions and settings.missed_day_deduction > 0:
            move = await points_service.apply(
                session,
                key=f"day:{sub.id}:missed",
                user_id=agenda.user_id,
                reason=LedgerReason.DAY_MISSED,
                delta=-abs(settings.missed_day_deduction),
                occurred_on=day,
                agenda_id=agenda.id,
                sub_agenda_id=sub.id,
                meta={"day_index": sub.day_index, "done": completed, "total": total},
            )
            if move.applied:
                stats["penalty"] = move.delta

    sub.closed_at = sub.closed_at or func.now()
    return stats


async def close_finished_days(session: AsyncSession, agenda: Agenda) -> dict[str, int]:
    """Close every day of an agenda that has fully elapsed in the user's timezone."""
    today = local_today(agenda.timezone)
    last_finished = today - timedelta(days=1)
    if last_finished < agenda.start_date:
        return {"days": 0, "missed": 0, "penalty": 0}

    cursor = agenda.last_closed_date + timedelta(days=1) if agenda.last_closed_date else agenda.start_date
    totals = {"days": 0, "missed": 0, "penalty": 0}
    while cursor <= last_finished:
        stats = await close_day(session, agenda, cursor)
        totals["days"] += stats["closed"]
        totals["missed"] += stats["missed"]
        totals["penalty"] += stats["penalty"]
        cursor += timedelta(days=1)

    agenda.last_closed_date = last_finished
    return totals


async def has_missed_days(session: AsyncSession, agenda_id: uuid.UUID) -> bool:
    count = await session.scalar(
        select(func.count(SubAgenda.id)).where(
            SubAgenda.agenda_id == agenda_id, SubAgenda.status == SubAgendaStatus.MISSED
        )
    )
    return bool(count)


async def user_streak_snapshot(session: AsyncSession, user: User) -> dict[str, object]:
    today = local_today(user.timezone)
    start = today - timedelta(days=29)
    counts = await day_completion_map(session, user.id, start=start, end=today)
    recent = {
        (start + timedelta(days=offset)).isoformat(): counts.get(
            start + timedelta(days=offset), DayCount(0, 0)
        ).complete
        for offset in range((today - start).days + 1)
    }
    return {
        "current": user.current_streak,
        "longest": user.longest_streak,
        "last_complete_date": user.last_complete_date,
        "recent_days": recent,
    }


async def recompute_all_active(session: AsyncSession) -> int:
    """Recompute streaks for every user with an active agenda."""
    rows = await session.execute(
        select(User).where(
            User.id.in_(select(Agenda.user_id).where(Agenda.status == AgendaStatus.ACTIVE))
        )
    )
    users = rows.scalars().all()
    for user in users:
        await recompute(session, user)
    return len(users)
