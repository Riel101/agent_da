"""Command-line entry points.

Used by the Render Cron Job (which calls ``python -m app.cli dispatch`` rather
than hitting HTTP) and for local end-to-end demos::

    python -m app.cli demo
    python -m app.cli dispatch
    python -m app.cli materialize
    python -m app.cli day-close
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.timezones import local_today
from app.db.session import dispose_engine, session_scope

logger = get_logger("app.cli")

DEMO_EMAIL = "demo@agentda.local"


async def _ensure_schema() -> None:
    if not settings.is_sqlite:
        return
    from app.db.base import Base
    from app.db.session import get_engine

    import app.models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def cmd_dispatch() -> int:
    from app.services import reminder_service

    stats = await reminder_service.dispatch_due()
    print(f"dispatch: {stats}")
    return 0


async def cmd_materialize() -> int:
    from app.services import materializer

    async with session_scope() as session:
        stats = await materializer.materialize_agendas(session)
    print(f"materialize: {stats}")
    return 0


async def cmd_day_close() -> int:
    from app.services import materializer

    async with session_scope() as session:
        stats = await materializer.close_finished_days(session)
    print(f"day-close: {stats}")
    return 0


async def cmd_demo() -> int:
    """Run the whole product offline, from goal to points, printing each step."""
    from sqlalchemy import select

    from app.models import Agenda, AgendaStatus, SubAgenda, User
    from app.services import (
        materializer,
        plan_service,
        points_service,
        reminder_service,
        todo_service,
    )
    from app.schemas.agenda import AgendaCreate
    from app.schemas.todo import TodoUpdate  # noqa: F401 - documents intent
    from app.services import agenda_service

    await _ensure_schema()

    async with session_scope() as session:
        user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            from app.services import user_service

            user = await user_service.create_user(
                session,
                email=DEMO_EMAIL,
                password="demo-password-123",
                full_name="Demo",
                timezone="Africa/Lagos",
            )

        today = local_today(user.timezone)
        existing = await session.scalar(
            select(Agenda).where(Agenda.user_id == user.id, Agenda.status != AgendaStatus.ARCHIVED)
        )
        if existing is not None:
            await session.delete(existing)
            await session.flush()

        agenda = await agenda_service.create_agenda(
            session,
            user,
            AgendaCreate(
                title="Launch my SaaS to 100 paying users",
                description=(
                    "Ship the product and get the first hundred customers paying "
                    "for the Pro plan."
                ),
                timeframe_days=30,
                start_date=today,
                reminder_channel="email",
                reminder_time="08:00",
                timezone=user.timezone,
            ),
        )
        user_id, agenda_id = user.id, agenda.id

    print(f"\n== agenda {agenda_id} created (30 days, starts {today}) ==\n")

    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        draft = await plan_service.create_draft(session, agenda)
        draft_id = draft.id

    outcome = await plan_service.run_generation_now(draft_id)
    print(f"graph paused for review after {len(outcome.state.get('sub_agendas', []))} days")

    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        days = (
            await session.execute(
                select(SubAgenda).where(SubAgenda.agenda_id == agenda_id).order_by(SubAgenda.day_index)
            )
        ).scalars().all()

    print("\n-- the plan --")
    for day in days[:5]:
        print(f"  day {day.day_index:>2}  {day.scheduled_date}  {day.title}")
        for todo in day.todos:
            print(f"          [ ] {todo.title}")
    print(f"  ... {len(days) - 5} more days")
    print(f"  final day {days[-1].scheduled_date}: {days[-1].title}")
    print(f"  expected outcome: {days[-1].expected_outcome}")

    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        draft = await plan_service.latest_draft(session, agenda_id)
        approval = await plan_service.approve_agenda(session, agenda, draft)

    print(f"\n-- approved -- {approval}")

    dispatched = await reminder_service.dispatch_due()
    print(f"-- reminders dispatched -- {dispatched}")

    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        today_day = await session.scalar(
            select(SubAgenda).where(
                SubAgenda.agenda_id == agenda_id, SubAgenda.scheduled_date == today
            )
        )
        todo_ids = [todo.id for todo in today_day.todos]

    print(f"\n-- completing today's {len(todo_ids)} to-dos --")
    for todo_id in todo_ids:
        async with session_scope() as session:
            user = await session.get(User, user_id)
            result = await todo_service.complete_todo(session, todo_id, user)
        print(
            f"  +{result.awarded:<3} balance={result.balance:<5} "
            f"day {result.day.done}/{result.day.total} streak={result.streak_current} "
            f"{result.bonuses}"
        )

    async with session_scope() as session:
        user = await session.get(User, user_id)
        summary = await points_service.summary(session, user_id)
        agenda = await session.get(Agenda, agenda_id)
        progress = await materializer.agenda_progress(session, agenda)
        streak = user.current_streak

    print("\n-- result --")
    print(f"  points balance : {summary['balance']}")
    print(f"  by reason      : {summary['by_reason']}")
    print(f"  streak         : {streak}")
    print(f"  agenda status  : {agenda.status.value}")
    print(f"  progress       : {progress['done_todos']}/{progress['total_todos']} to-dos")
    print(f"  missed days    : {progress['missed_days']}")

    print("\n-- simulating three elapsed, unfinished days --")
    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        agenda.start_date = today - timedelta(days=3)
        agenda.end_date = agenda.start_date + timedelta(days=agenda.timeframe_days - 1)
        days = (
            await session.execute(
                select(SubAgenda)
                .where(SubAgenda.agenda_id == agenda_id)
                .order_by(SubAgenda.day_index)
            )
        ).scalars().all()
        for offset, day in enumerate(days):
            day.scheduled_date = agenda.start_date + timedelta(days=offset)
            if offset >= 3:
                break
        await session.flush()
        closed = await materializer.close_finished_days(session)
        user = await session.get(User, user_id)
        user.streak = user.current_streak

    print(f"  day-close: {closed}")
    async with session_scope() as session:
        agenda = await session.get(Agenda, agenda_id)
        progress = await materializer.agenda_progress(session, agenda)
        user = await session.get(User, user_id)
    print(
        f"  after penalties: balance={user.points_balance} "
        f"streak={user.current_streak} missed_days={progress['missed_days']}"
    )
    return 0


COMMANDS = {
    "dispatch": cmd_dispatch,
    "materialize": cmd_materialize,
    "day-close": cmd_day_close,
    "demo": cmd_demo,
}


async def _run(command: str) -> int:
    handler = COMMANDS[command]
    try:
        return await handler()
    finally:
        from app.agents.checkpointer import close_checkpointer

        await close_checkpointer()
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Agent DA operations")
    parser.add_argument(
        "command",
        choices=sorted(COMMANDS),
        help="dispatch | materialize | day-close | demo",
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    args = parser.parse_args(argv)

    configure_logging("DEBUG" if (args.debug or settings.debug) else "INFO")
    return asyncio.run(_run(args.command))


if __name__ == "__main__":
    sys.exit(main())
