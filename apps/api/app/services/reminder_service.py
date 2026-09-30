"""Reminder scheduling, rendering and dispatch.

Exactly-once delivery rests on three things working together:

1. a unique ``dedupe_key`` per (agenda, day, kind, local date);
2. claiming due rows with ``SELECT ... FOR UPDATE SKIP LOCKED`` so two workers
   (the in-process scheduler and the Render cron safety net) never take the
   same row;
3. recording ``sent_at`` so a retry cannot re-send.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import motivation_line
from app.core.config import settings
from app.core.logging import get_logger
from app.core.timezones import combine_local, local_today, utc_now
from app.db.session import session_scope
from app.integrations.channels.base import OutboundMessage
from app.integrations.channels.registry import channel_status, deliver
from app.models import (
    Agenda,
    AgendaStatus,
    PointsLedgerEntry,
    Reminder,
    ReminderChannel,
    ReminderKind,
    ReminderStatus,
    SubAgenda,
    SubAgendaStatus,
    Todo,
    User,
)
from app.services import materializer

logger = get_logger(__name__)

#: Cap on the stored rendering so the log column stays sane.
BODY_LIMIT = 4000


def fire_time(agenda: Agenda, day: date, *, now: datetime | None = None) -> datetime:
    """UTC instant the reminder for ``day`` should go out."""
    moment = combine_local(day, agenda.reminder_time, agenda.timezone)
    current = now or utc_now()
    if moment < current:
        # Approved after today's time has passed: send once, promptly.
        return current
    return moment


async def schedule_agenda_reminders(
    session: AsyncSession, agenda: Agenda, *, expand_preview: bool = False
) -> dict[str, int]:
    """Create one reminder row per remaining day. Safe to call repeatedly."""
    today = local_today(agenda.timezone)
    days = (
        await session.execute(
            select(SubAgenda)
            .where(SubAgenda.agenda_id == agenda.id, SubAgenda.scheduled_date >= today)
            .order_by(SubAgenda.day_index)
        )
    ).scalars().all()

    created = 0
    for sub in days:
        key = Reminder.build_dedupe_key(agenda.id, sub.id, ReminderKind.DAILY, sub.scheduled_date)
        exists = await session.scalar(select(Reminder.id).where(Reminder.dedupe_key == key))
        if exists:
            continue
        session.add(
            Reminder(
                user_id=agenda.user_id,
                agenda_id=agenda.id,
                sub_agenda_id=sub.id,
                kind=ReminderKind.DAILY,
                channel=agenda.reminder_channel,
                status=ReminderStatus.PENDING,
                scheduled_for=fire_time(agenda, sub.scheduled_date),
                local_date=sub.scheduled_date,
                dedupe_key=key,
            )
        )
        created += 1

    await session.flush()

    expanded = 0
    if expand_preview:
        stats = await materializer.expand_missing_todos(
            session, agenda, horizon_days=settings.preexpand_days
        )
        expanded = stats["days_expanded"]

    return {"scheduled_reminders": created, "expanded_days": expanded}


async def schedule_weekly_rollups(session: AsyncSession) -> int:
    """Sunday rollups for active agendas, delivered through the same channel."""
    agendas = (
        await session.execute(select(Agenda).where(Agenda.status == AgendaStatus.ACTIVE))
    ).scalars().all()

    created = 0
    for agenda in agendas:
        today = local_today(agenda.timezone)
        if today > agenda.end_date:
            continue
        # ISO weekday 7 == Sunday.
        days_ahead = (7 - today.isoweekday()) % 7
        target = today + timedelta(days=days_ahead)
        if target > agenda.end_date:
            continue

        key = Reminder.build_dedupe_key(agenda.id, None, ReminderKind.WEEKLY_ROLLUP, target)
        exists = await session.scalar(select(Reminder.id).where(Reminder.dedupe_key == key))
        if exists:
            continue

        session.add(
            Reminder(
                user_id=agenda.user_id,
                agenda_id=agenda.id,
                sub_agenda_id=None,
                kind=ReminderKind.WEEKLY_ROLLUP,
                channel=agenda.reminder_channel,
                status=ReminderStatus.PENDING,
                scheduled_for=fire_time(agenda, target),
                local_date=target,
                dedupe_key=key,
            )
        )
        created += 1
    await session.flush()
    return created


# ------------------------------------------------------------------ rendering


async def _motivation(
    session: AsyncSession, agenda: Agenda, user: User, sub: SubAgenda
) -> str:
    if not settings.motivation_enabled:
        return ""
    done_days = await session.scalar(
        select(func.count(SubAgenda.id)).where(
            SubAgenda.agenda_id == agenda.id,
            SubAgenda.scheduled_date < sub.scheduled_date,
            SubAgenda.status == SubAgendaStatus.DONE,
        )
    )
    return await motivation_line(
        full_name=user.full_name,
        agenda_title=agenda.title,
        day_title=sub.title,
        day_index=sub.day_index,
        timeframe_days=agenda.timeframe_days,
        streak=user.current_streak,
        done_so_far=int(done_days or 0),
        total_days=agenda.timeframe_days,
    )


async def render_daily(
    session: AsyncSession, reminder: Reminder
) -> tuple[str, str] | None:
    """Build (subject, body) for a daily reminder, or None if data is missing."""
    user = await session.get(User, reminder.user_id)
    agenda = await session.get(Agenda, reminder.agenda_id)
    if user is None or agenda is None:
        return None

    sub = (
        await session.get(SubAgenda, reminder.sub_agenda_id)
        if reminder.sub_agenda_id
        else None
    )
    if sub is None:
        return None

    todos = (
        await session.execute(
            select(Todo).where(Todo.sub_agenda_id == sub.id).order_by(Todo.position)
        )
    ).scalars().all()

    motivation = await _motivation(session, agenda, user, sub)

    lines: list[str] = []
    if motivation:
        lines.extend([motivation, ""])
    lines.append(f"Today's focus — {sub.title}")
    if sub.description:
        lines.append(sub.description)
    if sub.expected_outcome:
        lines.append(f"Done when: {sub.expected_outcome}")
    lines.append("")

    if todos:
        for todo in todos:
            mark = "x" if todo.is_done else " "
            lines.append(f"[{mark}] {todo.title}")
    else:
        lines.append("(No to-dos recorded for today yet.)")

    done = sum(1 for todo in todos if todo.is_done)
    lines.extend(
        [
            "",
            f"Day {sub.day_index} of {agenda.timeframe_days} · {done}/{len(todos)} done · "
            f"{user.points_balance} points · {user.current_streak}-day streak",
        ]
    )

    subject = f"Day {sub.day_index} of {agenda.timeframe_days} — {sub.title}"
    return subject[:300], "\n".join(lines)


async def render_rollup(session: AsyncSession, reminder: Reminder) -> tuple[str, str] | None:
    user = await session.get(User, reminder.user_id)
    agenda = await session.get(Agenda, reminder.agenda_id)
    if user is None or agenda is None:
        return None

    week_start = reminder.local_date - timedelta(days=6)
    rows = (
        await session.execute(
            select(
                SubAgenda.scheduled_date,
                SubAgenda.status,
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
            )
            .outerjoin(Todo, Todo.sub_agenda_id == SubAgenda.id)
            .where(
                SubAgenda.agenda_id == agenda.id,
                SubAgenda.scheduled_date >= week_start,
                SubAgenda.scheduled_date <= reminder.local_date,
            )
            .group_by(SubAgenda.scheduled_date, SubAgenda.status)
            .order_by(SubAgenda.scheduled_date)
        )
    ).all()

    earned = await session.scalar(
        select(func.coalesce(func.sum(PointsLedgerEntry.delta), 0)).where(
            PointsLedgerEntry.user_id == user.id,
            PointsLedgerEntry.occurred_on >= week_start,
            PointsLedgerEntry.occurred_on <= reminder.local_date,
        )
    )

    lines = [
        f"Weekly review — {agenda.title}",
        "",
        f"Points this week: {int(earned or 0)}",
        f"Points balance: {user.points_balance}",
        f"Current streak: {user.current_streak} days (best {user.longest_streak})",
        "",
    ]
    for scheduled_date, status, total, done in rows:
        state = status.value if hasattr(status, "value") else str(status)
        lines.append(f"{scheduled_date.isoformat()}  {int(done or 0)}/{int(total or 0)}  ({state})")

    subject = f"Weekly review — {agenda.title}"
    return subject[:300], "\n".join(lines)


async def render_message(session: AsyncSession, reminder: Reminder) -> OutboundMessage | None:
    """Render (and cache) the message for a reminder."""
    user = await session.get(User, reminder.user_id)
    if user is None:
        return None

    cached_subject = reminder.body_subject
    cached_body = reminder.body_preview
    if not (cached_subject and cached_body):
        if reminder.kind is ReminderKind.WEEKLY_ROLLUP:
            rendered = await render_rollup(session, reminder)
        else:
            rendered = await render_daily(session, reminder)
        if rendered is None:
            return None
        cached_subject, cached_body = rendered
        reminder.body_subject = cached_subject
        reminder.body_preview = cached_body[:BODY_LIMIT]

    if reminder.channel is ReminderChannel.WHATSAPP:
        target = user.phone_e164 or ""
    else:
        target = user.email

    if not target:
        return None

    return OutboundMessage(
        to=target,
        subject=cached_subject,
        body=cached_body,
        email_fallback=user.email,
        meta={"agenda": reminder.agenda_id, "kind": reminder.kind.value},
    )


# ------------------------------------------------------------------- dispatch


async def claim_due(session: AsyncSession, limit: int) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(Reminder)
            .where(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.scheduled_for <= utc_now(),
                Reminder.attempted < settings.dispatch_max_attempts,
            )
            .order_by(Reminder.scheduled_for)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    ids: list[uuid.UUID] = []
    for row in rows:
        row.status = ReminderStatus.CLAIMED
        row.claimed_at = utc_now()
        row.attempted += 1
        ids.append(row.id)
    return ids


async def send_one(reminder_id: uuid.UUID) -> str:
    """Send a claimed reminder and record the outcome."""
    async with session_scope() as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder is None:
            return "missing"

        message = await render_message(session, reminder)
        if message is None:
            reminder.status = ReminderStatus.SKIPPED
            reminder.error = "No delivery target or agenda data available"
            return "skipped"

        result = await deliver(reminder.channel, message)

        reminder.provider = result.provider
        reminder.provider_message_id = result.message_id
        reminder.error = result.error

        if result.ok:
            reminder.status = ReminderStatus.SENT
            reminder.sent_at = utc_now()
            return "sent"

        if reminder.attempted >= settings.dispatch_max_attempts:
            reminder.status = ReminderStatus.FAILED
            return "failed"

        # Put it back for another attempt.
        reminder.status = ReminderStatus.PENDING
        return "retry"


async def dispatch_due(limit: int | None = None) -> dict[str, int]:
    """Process every due reminder. Called by the scheduler and by the cron."""
    batch = limit or settings.dispatch_batch_size
    async with session_scope() as session:
        claimed = await claim_due(session, batch)

    stats = {"claimed": len(claimed), "sent": 0, "failed": 0, "skipped": 0, "retry": 0}
    for reminder_id in claimed:
        try:
            outcome = await send_one(reminder_id)
        except Exception as exc:  # noqa: BLE001 - one bad reminder must not stop the batch
            logger.exception("reminder %s blew up", reminder_id)
            outcome = "failed"
            async with session_scope() as session:
                row = await session.get(Reminder, reminder_id)
                if row is not None:
                    row.status = ReminderStatus.FAILED
                    row.error = str(exc)[:1000]
        stats[outcome if outcome in stats else "failed"] += 1

    if claimed:
        logger.info("dispatch: %s", stats)
    return stats


async def pending_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(Reminder.id)).where(Reminder.status == ReminderStatus.PENDING)
        )
        or 0
    )


def diagnostics() -> dict[str, Any]:
    return {"channels": channel_status()}
