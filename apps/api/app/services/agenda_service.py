"""Agenda CRUD and summary aggregation."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.timezones import local_today
from app.models import (
    Agenda,
    AgendaStatus,
    ReminderChannel,
    SubAgenda,
    SubAgendaStatus,
    Todo,
    User,
)
from app.schemas.agenda import AgendaCreate, AgendaOut, AgendaSummary, AgendaUpdate


async def create_agenda(session: AsyncSession, user: User, data: AgendaCreate) -> Agenda:
    timeframe = int(data.timeframe_days)
    if not settings.min_timeframe_days <= timeframe <= settings.max_timeframe_days:
        raise ValidationError(
            f"Timeframe must be between {settings.min_timeframe_days} and "
            f"{settings.max_timeframe_days} days",
            code="TIMEFRAME_OUT_OF_RANGE",
        )

    start = data.start_date or local_today(user.timezone)
    today = local_today(user.timezone)
    if start < today:
        raise ValidationError(
            "The start date cannot be in the past", code="START_DATE_IN_PAST"
        )

    channel = data.reminder_channel
    phone = data.phone_e164 or user.phone_e164
    if channel is ReminderChannel.WHATSAPP and not phone:
        raise ValidationError(
            "A phone number is required for WhatsApp reminders",
            code="PHONE_REQUIRED",
        )

    agenda = Agenda(
        user_id=user.id,
        title=data.title.strip(),
        description=data.description.strip(),
        timeframe_days=timeframe,
        start_date=start,
        end_date=start + timedelta(days=timeframe - 1),
        reminder_channel=channel,
        reminder_time=data.reminder_time,
        timezone=data.timezone or user.timezone,
        status=AgendaStatus.DRAFT,
    )
    session.add(agenda)
    await session.flush()

    if data.phone_e164 and not user.phone_e164:
        user.phone_e164 = data.phone_e164
        await session.flush()

    return agenda


async def get_agenda(
    session: AsyncSession, agenda_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
) -> Agenda:
    stmt = select(Agenda).where(Agenda.id == agenda_id)
    if lock:
        stmt = stmt.with_for_update()
    agenda = await session.scalar(stmt)
    if agenda is None:
        raise NotFoundError("Agenda not found", code="AGENDA_NOT_FOUND")
    if agenda.user_id != user_id:
        raise PermissionDeniedError("This agenda belongs to another account")
    return agenda


async def list_agendas(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: AgendaStatus | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Agenda], int]:
    conditions = [Agenda.user_id == user_id]
    if status is not None:
        conditions.append(Agenda.status == status)

    total = await session.scalar(select(func.count(Agenda.id)).where(*conditions))
    rows = (
        await session.execute(
            select(Agenda)
            .where(*conditions)
            .order_by(Agenda.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()
    return list(rows), int(total or 0)


async def update_agenda(
    session: AsyncSession, agenda: Agenda, data: AgendaUpdate
) -> Agenda:
    if not agenda.is_editable:
        raise ConflictError(
            "A running agenda cannot be re-planned. Archive it and create a new one.",
            code="AGENDA_NOT_EDITABLE",
        )

    structural_change = False
    if data.title is not None:
        agenda.title = data.title.strip()
    if data.description is not None:
        agenda.description = data.description.strip()
    if data.timeframe_days is not None and int(data.timeframe_days) != agenda.timeframe_days:
        if not settings.min_timeframe_days <= int(data.timeframe_days) <= settings.max_timeframe_days:
            raise ValidationError(
                f"Timeframe must be between {settings.min_timeframe_days} and "
                f"{settings.max_timeframe_days} days",
                code="TIMEFRAME_OUT_OF_RANGE",
            )
        agenda.timeframe_days = int(data.timeframe_days)
        structural_change = True
    if data.start_date is not None and data.start_date != agenda.start_date:
        agenda.start_date = data.start_date
        structural_change = True

    if structural_change:
        agenda.end_date = agenda.start_date + timedelta(days=agenda.timeframe_days - 1)
        # The old plan no longer matches the timeframe, so it is discarded and
        # the user regenerates.
        await session.execute(delete(SubAgenda).where(SubAgenda.agenda_id == agenda.id))
        agenda.status = AgendaStatus.DRAFT

    if data.reminder_channel is not None:
        agenda.reminder_channel = data.reminder_channel
    if data.reminder_time is not None:
        agenda.reminder_time = data.reminder_time
    if data.timezone is not None:
        agenda.timezone = data.timezone
    if (
        agenda.reminder_channel is ReminderChannel.WHATSAPP
        and not data.phone_e164
        and not (await session.get(User, agenda.user_id)).phone_e164
    ):
        raise ValidationError(
            "A phone number is required for WhatsApp reminders", code="PHONE_REQUIRED"
        )

    await session.flush()
    return agenda


async def _aggregate(session: AsyncSession, agenda_ids: list[uuid.UUID]) -> dict:
    if not agenda_ids:
        return {}

    rows = (
        await session.execute(
            select(
                SubAgenda.agenda_id,
                func.count(func.distinct(SubAgenda.id)),
                func.count(Todo.id),
                func.sum(case((Todo.is_done.is_(True), 1), else_=0)),
                func.sum(case((SubAgenda.status == SubAgendaStatus.MISSED, 1), else_=0)),
            )
            .outerjoin(Todo, Todo.sub_agenda_id == SubAgenda.id)
            .where(SubAgenda.agenda_id.in_(agenda_ids))
            .group_by(SubAgenda.agenda_id)
        )
    ).all()

    result: dict = {}
    for agenda_id, days, total, done, missed in rows:
        total_i = int(total or 0)
        done_i = int(done or 0)
        result[agenda_id] = {
            "total_days_planned": int(days or 0),
            "total_todos": total_i,
            "done_todos": done_i,
            "progress_pct": round(done_i / total_i * 100) if total_i else 0,
            "missed_days": int(missed or 0),
        }
    return result


def base_dict(agenda: Agenda) -> dict:
    return AgendaOut.model_validate(agenda).model_dump()


async def summarise(session: AsyncSession, agenda: Agenda) -> dict:
    aggregates = await _aggregate(session, [agenda.id])
    return _merge(agenda, aggregates.get(agenda.id, {}))


async def summarise_many(session: AsyncSession, agendas: list[Agenda]) -> list[dict]:
    aggregates = await _aggregate(session, [agenda.id for agenda in agendas])
    return [_merge(agenda, aggregates.get(agenda.id, {})) for agenda in agendas]


def _merge(agenda: Agenda, aggregate: dict) -> dict:
    today = local_today(agenda.timezone)
    elapsed = max(0, min((today - agenda.start_date).days + 1, agenda.timeframe_days))
    if today < agenda.start_date:
        elapsed = 0
    return {
        **base_dict(agenda),
        "total_todos": aggregate.get("total_todos", 0),
        "done_todos": aggregate.get("done_todos", 0),
        "progress_pct": aggregate.get("progress_pct", 0),
        "missed_days": aggregate.get("missed_days", 0),
        "days_elapsed": elapsed,
    }


async def list_days(session: AsyncSession, agenda: Agenda) -> list[SubAgenda]:
    rows = (
        await session.execute(
            select(SubAgenda)
            .where(SubAgenda.agenda_id == agenda.id)
            .order_by(SubAgenda.day_index)
        )
    ).scalars().all()
    return list(rows)


async def get_day(session: AsyncSession, agenda: Agenda, day_index: int) -> SubAgenda:
    sub = await session.scalar(
        select(SubAgenda).where(
            SubAgenda.agenda_id == agenda.id, SubAgenda.day_index == day_index
        )
    )
    if sub is None:
        raise NotFoundError(f"Day {day_index} does not exist", code="DAY_NOT_FOUND")
    return sub


async def get_day_by_date(session: AsyncSession, agenda: Agenda, day: date) -> SubAgenda | None:
    return await session.scalar(
        select(SubAgenda).where(
            SubAgenda.agenda_id == agenda.id, SubAgenda.scheduled_date == day
        )
    )


async def update_day(
    session: AsyncSession,
    sub: SubAgenda,
    *,
    title: str | None = None,
    description: str | None = None,
    expected_outcome: str | None = None,
    expected_effort_minutes: int | None = None,
) -> SubAgenda:
    if title is not None:
        sub.title = title.strip()[:300]
    if description is not None:
        sub.description = description
    if expected_outcome is not None:
        sub.expected_outcome = expected_outcome
    if expected_effort_minutes is not None:
        sub.expected_effort_minutes = expected_effort_minutes
    sub.is_user_edited = True
    await session.flush()
    return sub


def summary_model(payload: dict) -> AgendaSummary:
    return AgendaSummary.model_validate(payload)
