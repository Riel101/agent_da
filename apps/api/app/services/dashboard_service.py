"""Dashboard aggregation — one round-trip for the home screen."""

from __future__ import annotations

import calendar as calendar_module
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.core.timezones import local_today
from app.models import Agenda, AgendaStatus, SubAgenda, Todo, User


async def dashboard(session: AsyncSession, user: User) -> dict:
    today = local_today(user.timezone)
    agendas = (
        await session.execute(
            select(Agenda)
            .where(
                Agenda.user_id == user.id,
                Agenda.status.in_(
                    [
                        AgendaStatus.ACTIVE,
                        AgendaStatus.READY,
                        AgendaStatus.DRAFT,
                        AgendaStatus.GENERATING,
                        AgendaStatus.COMPLETED,
                    ]
                ),
            )
            .order_by(Agenda.start_date)
        )
    ).scalars().all()

    progress_rows = (
        await session.execute(
            select(
                Todo.agenda_id,
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
            )
            .where(Todo.user_id == user.id)
            .group_by(Todo.agenda_id)
        )
    ).all()
    progress = {
        agenda_id: (int(total or 0), int(done or 0)) for agenda_id, total, done in progress_rows
    }

    today_blocks = []
    active_ids = [agenda.id for agenda in agendas if agenda.status is AgendaStatus.ACTIVE]
    if active_ids:
        subs = (
            await session.execute(
                select(SubAgenda)
                .where(
                    SubAgenda.agenda_id.in_(active_ids),
                    SubAgenda.scheduled_date == today,
                )
                .order_by(SubAgenda.day_index)
            )
        ).scalars().all()

        by_id = {agenda.id: agenda for agenda in agendas}
        for sub in subs:
            agenda = by_id.get(sub.agenda_id)
            if agenda is None:
                continue
            done = sum(1 for todo in sub.todos if todo.is_done)
            total = len(sub.todos)
            today_blocks.append(
                {
                    "agenda_id": agenda.id,
                    "agenda_title": agenda.title,
                    "sub_agenda_id": sub.id,
                    "day_index": sub.day_index,
                    "title": sub.title,
                    "description": sub.description,
                    "expected_outcome": sub.expected_outcome,
                    "todos": sub.todos,
                    "done": done,
                    "total": total,
                }
            )

    cards = []
    for agenda in agendas:
        total, done = progress.get(agenda.id, (0, 0))
        offset = (today - agenda.start_date).days
        current_index = offset + 1 if 0 <= offset < agenda.timeframe_days else None
        cards.append(
            {
                "id": agenda.id,
                "title": agenda.title,
                "status": agenda.status,
                "start_date": agenda.start_date,
                "end_date": agenda.end_date,
                "progress_pct": round(done / total * 100) if total else 0,
                "current_day_index": current_index,
                "reminder_channel": agenda.reminder_channel.value
                if hasattr(agenda.reminder_channel, "value")
                else str(agenda.reminder_channel),
                "reminder_time": agenda.reminder_time.strftime("%H:%M"),
            }
        )

    return {
        "local_date": today,
        "timezone": user.timezone,
        "totals": {
            "points_balance": user.points_balance,
            "current_streak": user.current_streak,
            "longest_streak": user.longest_streak,
        },
        "today": today_blocks,
        "agendas": cards,
    }


async def calendar(session: AsyncSession, user: User, month: str | None = None) -> dict:
    today = local_today(user.timezone)
    if month:
        try:
            year_str, month_str = month.split("-", 1)
            year, month_number = int(year_str), int(month_str)
            if not 1 <= month_number <= 12:
                raise ValueError
        except (ValueError, AttributeError) as exc:
            raise ValidationError("month must look like 2026-10", code="BAD_MONTH") from exc
    else:
        year, month_number = today.year, today.month

    first = date(year, month_number, 1)
    last = date(year, month_number, calendar_module.monthrange(year, month_number)[1])

    rows = (
        await session.execute(
            select(
                SubAgenda.scheduled_date,
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
                func.sum(case((SubAgenda.status == "missed", 1), else_=0)),
            )
            .join(Todo, Todo.sub_agenda_id == SubAgenda.id)
            .join(Agenda, Agenda.id == SubAgenda.agenda_id)
            .where(
                Agenda.user_id == user.id,
                SubAgenda.scheduled_date >= first,
                SubAgenda.scheduled_date <= last,
            )
            .group_by(SubAgenda.scheduled_date)
        )
    ).all()

    by_date = {
        scheduled: (int(total or 0), int(done or 0), int(missed or 0))
        for scheduled, total, done, missed in rows
    }

    days = []
    cursor = first
    while cursor <= last:
        total, done, missed = by_date.get(cursor, (0, 0, 0))
        complete = total > 0 and done == total
        days.append(
            {
                "date": cursor,
                "total": total,
                "done": done,
                "complete": complete,
                "missed": bool(missed) or (cursor < today and total > 0 and not complete),
                "is_future": cursor > today,
            }
        )
        cursor = date.fromordinal(cursor.toordinal() + 1)

    return {"month": f"{year:04d}-{month_number:02d}", "days": days}
