"""Materialisation: turning plan days into concrete, day-of to-dos.

To-dos for the first few days are expanded when the agenda is approved so the
user can review them. Everything after that is expanded lazily the day before,
which keeps a 90-day agenda affordable and lets the plan react to slippage.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import expand_day_todos
from app.core.config import settings
from app.core.logging import get_logger
from app.core.timezones import local_today
from app.models import (
    Agenda,
    AgendaStatus,
    SubAgenda,
    SubAgendaStatus,
    Todo,
    TodoSource,
)
from app.services import streak_service

logger = get_logger(__name__)


async def replace_agent_todos(
    session: AsyncSession, agenda: Agenda, sub: SubAgenda, items: list[dict]
) -> None:
    """Swap the agent's to-dos for a day, leaving user-added ones in place."""
    await session.execute(
        delete(Todo).where(Todo.sub_agenda_id == sub.id, Todo.source == TodoSource.AGENT)
    )
    await session.flush()

    kept = (
        await session.execute(
            select(Todo).where(Todo.sub_agenda_id == sub.id).order_by(Todo.position)
        )
    ).scalars().all()

    if kept:
        # Park user rows out of the way so positions stay unique while inserting.
        await session.execute(
            update(Todo)
            .where(Todo.id.in_([row.id for row in kept]))
            .values(position=Todo.position + 10_000)
        )

    for position, item in enumerate(items):
        session.add(
            Todo(
                sub_agenda_id=sub.id,
                user_id=agenda.user_id,
                agenda_id=agenda.id,
                position=position,
                title=str(item["title"])[:300],
                notes=item.get("notes"),
                points=settings.task_completed_points,
                source=TodoSource.AGENT,
            )
        )

    for offset, row in enumerate(kept):
        row.position = len(items) + offset

    sub.todos_expanded = True
    await session.flush()


async def previous_context(session: AsyncSession, agenda: Agenda, sub: SubAgenda) -> str | None:
    """A one-line summary of how the day before actually went."""
    if sub.day_index <= 1:
        return None

    previous = await session.scalar(
        select(SubAgenda).where(
            SubAgenda.agenda_id == agenda.id, SubAgenda.day_index == sub.day_index - 1
        )
    )
    if previous is None:
        return None

    total = await session.scalar(
        select(func.count(Todo.id)).where(Todo.sub_agenda_id == previous.id)
    )
    done = await session.scalar(
        select(func.count(Todo.id)).where(
            Todo.sub_agenda_id == previous.id, Todo.is_done.is_(True)
        )
    )
    total_i, done_i = int(total or 0), int(done or 0)
    if total_i == 0:
        return f"Day {previous.day_index} had no to-dos recorded."
    if done_i == total_i:
        return (
            f"Day {previous.day_index} was completed in full ({done_i}/{total_i}). "
            f"Its outcome was: {previous.expected_outcome or previous.title}."
        )
    return (
        f"Day {previous.day_index} finished with {done_i} of {total_i} to-dos done, "
        "so today may need to absorb some of that carry-over."
    )


async def expand_day(
    session: AsyncSession, agenda: Agenda, sub: SubAgenda, *, use_context: bool = True
) -> int:
    """Generate and store to-dos for one day. Returns how many were created."""
    context = await previous_context(session, agenda, sub) if use_context else None
    items, _ = await expand_day_todos(
        agenda_title=agenda.title,
        day={
            "day_index": sub.day_index,
            "title": sub.title,
            "description": sub.description,
            "expected_outcome": sub.expected_outcome,
        },
        day_index=sub.day_index,
        timeframe_days=agenda.timeframe_days,
        previous_context=context,
    )
    if not items:
        return 0
    await replace_agent_todos(session, agenda, sub, items)
    return len(items)


async def expand_missing_todos(
    session: AsyncSession, agenda: Agenda, *, horizon_days: int
) -> dict[str, int]:
    """Expand every day up to ``horizon_days`` ahead that has no to-dos yet."""
    today = local_today(agenda.timezone)
    cutoff = today + timedelta(days=horizon_days)

    days = (
        await session.execute(
            select(SubAgenda)
            .where(
                SubAgenda.agenda_id == agenda.id,
                SubAgenda.scheduled_date <= cutoff,
                SubAgenda.todos_expanded.is_(False),
            )
            .order_by(SubAgenda.day_index)
        )
    ).scalars().all()

    expanded = 0
    created = 0
    for sub in days:
        try:
            created += await expand_day(session, agenda, sub)
            expanded += 1
        except Exception as exc:  # noqa: BLE001 - one bad day must not stop the rest
            logger.warning("could not expand day %s of agenda %s: %s", sub.day_index, agenda.id, exc)
            break
    return {"days_expanded": expanded, "todos_created": created}


async def materialize_agendas(session: AsyncSession) -> dict[str, int]:
    """Nightly/hourly job: fill in upcoming to-dos for every active agenda."""
    agendas = (
        await session.execute(select(Agenda).where(Agenda.status == AgendaStatus.ACTIVE))
    ).scalars().all()

    totals = {"agendas": 0, "days_expanded": 0, "todos_created": 0}
    for agenda in agendas:
        today = local_today(agenda.timezone)
        if today > agenda.end_date:
            continue
        # Days beyond the end of the window stay unexpanded until they are near.
        stats = await expand_missing_todos(session, agenda, horizon_days=settings.preexpand_days)
        agenda.last_materialized_date = today
        totals["agendas"] += 1
        totals["days_expanded"] += stats["days_expanded"]
        totals["todos_created"] += stats["todos_created"]
    return totals


async def close_finished_days(session: AsyncSession) -> dict[str, int]:
    """Mark elapsed days done or missed and apply the missed-day penalty."""
    agendas = (
        await session.execute(
            select(Agenda).where(
                Agenda.status.in_([AgendaStatus.ACTIVE, AgendaStatus.COMPLETED])
            )
        )
    ).scalars().all()

    totals = {"agendas": 0, "days": 0, "missed": 0, "penalty": 0}
    for agenda in agendas:
        try:
            stats = await streak_service.close_finished_days(session, agenda)
        except Exception as exc:  # noqa: BLE001
            logger.warning("day close failed for agenda %s: %s", agenda.id, exc)
            continue
        if stats["days"]:
            totals["agendas"] += 1
            totals["days"] += stats["days"]
            totals["missed"] += stats["missed"]
            totals["penalty"] += stats["penalty"]

    if totals["days"]:
        await streak_service.recompute_all_active(session)
    return totals


async def agenda_progress(session: AsyncSession, agenda: Agenda) -> dict[str, object]:
    """Counts used by the progress endpoint and the dashboard cards."""
    today = local_today(agenda.timezone)

    total_todos = await session.scalar(
        select(func.count(Todo.id)).where(Todo.agenda_id == agenda.id)
    )
    done_todos = await session.scalar(
        select(func.count(Todo.id)).where(Todo.agenda_id == agenda.id, Todo.is_done.is_(True))
    )
    rows = (
        await session.execute(
            select(
                SubAgenda.day_index,
                SubAgenda.scheduled_date,
                SubAgenda.title,
                SubAgenda.status,
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
            )
            .outerjoin(Todo, Todo.sub_agenda_id == SubAgenda.id)
            .where(SubAgenda.agenda_id == agenda.id)
            .group_by(
                SubAgenda.day_index,
                SubAgenda.scheduled_date,
                SubAgenda.title,
                SubAgenda.status,
            )
            .order_by(SubAgenda.day_index)
        )
    ).all()

    per_day = []
    completed_days = 0
    missed_days = 0
    for day_index, scheduled_date, title, status, total, done in rows:
        total_i = int(total or 0)
        done_i = int(done or 0)
        complete = total_i > 0 and done_i == total_i
        if status is SubAgendaStatus.MISSED:
            missed_days += 1
        if complete:
            completed_days += 1
        per_day.append(
            {
                "day_index": day_index,
                "date": scheduled_date.isoformat(),
                "title": title,
                "status": status.value if hasattr(status, "value") else str(status),
                "total": total_i,
                "done": done_i,
                "complete": complete,
                "is_today": scheduled_date == today,
            }
        )

    total_i = int(total_todos or 0)
    done_i = int(done_todos or 0)
    offset = (today - agenda.start_date).days
    current_index = offset + 1 if 0 <= offset < agenda.timeframe_days else None

    return {
        "progress_pct": round(done_i / total_i * 100) if total_i else 0,
        "total_todos": total_i,
        "done_todos": done_i,
        "total_days": agenda.timeframe_days,
        "completed_days": completed_days,
        "missed_days": missed_days,
        "days_remaining": max(0, (agenda.end_date - today).days),
        "points_earned": agenda.total_points,
        "current_day_index": current_index,
        "per_day": per_day,
    }
