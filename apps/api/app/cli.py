"""Command-line entry points.

Used by the Render Cron Job (which calls ``python -m app.cli dispatch`` rather
than hitting HTTP) and for local end-to-end demos::

    python -m app.cli demo
    python -m app.cli dispatch
    python -m app.cli materialize
    python -m app.cli day-close
    python -m app.cli reminders          # what was queued / sent / skipped
    python -m app.cli send-test          # prove delivery works, end to end
    python -m app.cli mail-catcher       # a local SMTP sink, for delivery with no account
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

DEMO_EMAIL = "demo@agentda.dev"
DEMO_PASSWORD = "demo-password-123"


async def _ensure_schema() -> None:
    if not settings.is_sqlite:
        return
    from app.db.base import Base
    from app.db.session import get_engine

    import app.models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def cmd_dispatch(args) -> int:  # noqa: ARG001 - uniform handler signature
    from app.services import reminder_service

    stats = await reminder_service.dispatch_due()
    print(f"dispatch: {stats}")
    if stats.get("skipped"):
        print(
            f"  {stats['skipped']} reminder(s) were logged but not delivered — "
            "no channel is configured. Run `python -m app.cli send-test` to check."
        )
    return 0


async def cmd_materialize(args) -> int:  # noqa: ARG001 - uniform handler signature
    from app.services import materializer

    async with session_scope() as session:
        stats = await materializer.materialize_agendas(session)
    print(f"materialize: {stats}")
    return 0


async def cmd_day_close(args) -> int:  # noqa: ARG001 - uniform handler signature
    """Close elapsed days and refresh the streaks and rollups that depend on them.

    Mirrors ``job_day_close`` exactly, so running this from cron does the same
    work as the in-process scheduler.
    """
    from app.services import materializer, reminder_service

    async with session_scope() as session:
        stats = await materializer.close_finished_days(session)
        stats["weekly_rollups"] = await reminder_service.schedule_weekly_rollups(session)
    print(f"day-close: {stats}")
    return 0


async def cmd_demo(args) -> int:  # noqa: ARG001 - uniform handler signature
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
                password=DEMO_PASSWORD,
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
    print(f"\nsign in at /signin with {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


async def cmd_reminders(args) -> int:
    """Show the reminder log: what was queued, what went out, and what did not.

    The point of this command is that the database never lies about delivery. A
    ``sent`` row reached a provider; a ``skipped`` row did not, and its ``error``
    column says what is missing.
    """
    import uuid as _uuid

    from sqlalchemy import func, select

    from app.integrations.channels.registry import delivers_for_real, resolve_sender
    from app.models import Reminder, ReminderChannel, ReminderStatus

    await _ensure_schema()

    async with session_scope() as session:
        query = select(Reminder).order_by(Reminder.scheduled_for.desc()).limit(args.limit)
        if args.status:
            query = query.where(Reminder.status == ReminderStatus(args.status))
        if args.agenda:
            try:
                query = query.where(Reminder.agenda_id == _uuid.UUID(args.agenda))
            except ValueError:
                print(f"not a valid agenda id: {args.agenda}")
                return 2
        rows = (await session.execute(query)).scalars().all()

        counts = (
            await session.execute(
                select(Reminder.status, func.count(Reminder.id)).group_by(Reminder.status)
            )
        ).all()

    for channel in (ReminderChannel.EMAIL, ReminderChannel.WHATSAPP):
        real = delivers_for_real(channel)
        print(
            f"{channel.value:<9} -> {resolve_sender(channel).name:<8} "
            f"{'delivers' if real else 'LOGS ONLY (not delivered)'}"
        )
    print()

    summary = "  ".join(f"{status.value}={int(count)}" for status, count in counts)
    print(f"totals: {summary or 'no reminders yet'}")
    print()

    if not rows:
        print("no reminders to show")
        return 0

    print(f"{'scheduled (UTC)':<20} {'status':<8} {'kind':<14} {'channel':<9} {'att':<3} detail")
    for row in rows:
        when = row.scheduled_for.strftime("%Y-%m-%d %H:%M") if row.scheduled_for else "-"
        detail = row.error or row.body_subject or "-"
        print(
            f"{when:<20} {row.status.value:<8} {row.kind.value:<14} "
            f"{row.channel.value:<9} {row.attempted:<3} {str(detail)[:70]}"
        )
    return 0


async def cmd_send_test(args) -> int:
    """Send one message through the configured channel and report what happened.

    This is a delivery probe, not a reminder: it writes nothing, so it can be run
    as often as you like without disturbing the once-per-day guarantee. Exit code
    is 0 only when a provider genuinely accepted the message.

    With ``--agenda`` the body is the plan's next real daily reminder, rendered
    but not recorded, so what you receive is exactly what would have gone out.
    """
    import uuid as _uuid

    from sqlalchemy import select

    from app.integrations.channels.base import OutboundMessage
    from app.integrations.channels.registry import (
        deliver,
        delivers_for_real,
        resolve_sender,
    )
    from app.models import (
        Agenda,
        AgendaStatus,
        Reminder,
        ReminderChannel,
        ReminderKind,
        ReminderStatus,
        User,
    )
    from app.services import reminder_service

    await _ensure_schema()

    channel = ReminderChannel(args.channel)
    sender = resolve_sender(channel)
    real = delivers_for_real(channel)

    subject = "AgentDa delivery test"
    body = (
        "This is a delivery test from AgentDa.\n\n"
        "If you are reading this in your inbox, daily reminders will reach you too."
    )
    to = args.to
    fallback = None

    async with session_scope() as session:
        agenda = None
        if args.agenda:
            try:
                agenda = await session.get(Agenda, _uuid.UUID(args.agenda))
            except ValueError:
                print(f"not a valid agenda id: {args.agenda}")
                return 2
            if agenda is None:
                print(f"no agenda with id {args.agenda}")
                return 2
        else:
            agenda = (
                await session.execute(
                    select(Agenda)
                    .where(Agenda.status == AgendaStatus.ACTIVE)
                    .order_by(Agenda.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()

        user = await session.get(User, agenda.user_id) if agenda is not None else None
        if user is not None:
            fallback = user.email
            if to is None:
                to = user.phone_e164 if channel is ReminderChannel.WHATSAPP else user.email

        if agenda is not None:
            reminder = (
                await session.execute(
                    select(Reminder)
                    .where(
                        Reminder.agenda_id == agenda.id,
                        Reminder.status == ReminderStatus.PENDING,
                        Reminder.kind == ReminderKind.DAILY,
                    )
                    .order_by(Reminder.scheduled_for)
                    .limit(1)
                )
            ).scalars().first()
            rendered = await reminder_service.render_daily(session, reminder) if reminder else None
            if rendered:
                subject, body = rendered

    if not to:
        print("No recipient. Pass --to <address>, or use an agenda whose owner has one.")
        return 2

    print(f"channel  : {channel.value} -> sender={sender.name} delivers_for_real={real}")
    print(f"to       : {to}")
    print(f"subject  : {subject}")

    result = await deliver(
        channel, OutboundMessage(to=to, subject=subject, body=body, email_fallback=fallback)
    )

    print(f"outcome  : {result.outcome.value}")
    print(f"provider : {result.provider}")
    print(f"message  : {result.message_id or '-'}")
    if result.error:
        print(f"error    : {result.error}")

    if not real:
        print(
            "\nNothing was delivered: no credentials are configured for this channel.\n"
            "Email — set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM.\n"
            "WhatsApp — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM."
        )
    return 0 if result.ok else 1


async def cmd_mail_catcher(args) -> int:
    """Run a local SMTP sink that saves messages to ``.eml`` files.

    Lets the whole delivery path run for real with no provider account: point
    ``SMTP_HOST`` at it and ``send-test`` reports ``sent`` because a mail server
    genuinely accepted the message. See ``app/dev/mailcatcher.py``.
    """
    import tempfile
    from pathlib import Path

    from app.dev.mailcatcher import serve

    out_dir = Path(args.out) if args.out else Path(tempfile.gettempdir()) / "agentda-mail"
    try:
        await serve(args.host, args.port, out_dir)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\ncatcher stopped; messages are in {out_dir}", flush=True)
    return 0


COMMANDS = {
    "dispatch": cmd_dispatch,
    "materialize": cmd_materialize,
    "day-close": cmd_day_close,
    "demo": cmd_demo,
    "reminders": cmd_reminders,
    "send-test": cmd_send_test,
    "mail-catcher": cmd_mail_catcher,
}


async def _run(command: str, args: argparse.Namespace) -> int:
    handler = COMMANDS[command]
    try:
        return await handler(args)
    finally:
        from app.agents.checkpointer import close_checkpointer

        await close_checkpointer()
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    from app.models import ReminderStatus

    parser = argparse.ArgumentParser(prog="app.cli", description="Agent DA operations")
    parser.add_argument(
        "command",
        choices=sorted(COMMANDS),
        help="dispatch | materialize | day-close | demo | reminders | send-test | mail-catcher",
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument(
        "--to",
        help="send-test: recipient; defaults to the agenda owner's address",
    )
    parser.add_argument("--agenda", help="send-test / reminders: limit to one agenda id")
    parser.add_argument(
        "--channel",
        choices=["email", "whatsapp"],
        default="email",
        help="send-test: which channel to probe",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="reminders: how many rows to show"
    )
    parser.add_argument(
        "--status",
        choices=[status.value for status in ReminderStatus],
        help="reminders: filter by status",
    )
    parser.add_argument("--host", default="127.0.0.1", help="mail-catcher: bind address")
    parser.add_argument("--port", type=int, default=1025, help="mail-catcher: SMTP port")
    parser.add_argument("--out", help="mail-catcher: directory to write .eml files into")
    args = parser.parse_args(argv)

    configure_logging("DEBUG" if (args.debug or settings.debug) else "INFO")
    return asyncio.run(_run(args.command, args))


if __name__ == "__main__":
    sys.exit(main())
