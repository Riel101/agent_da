"""Missed days: the penalty, the streak reset, and the no-rollover rule."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.timezones import local_today
from app.db.session import session_scope
from app.models import (
    Agenda,
    AgendaStatus,
    LedgerReason,
    PointsLedgerEntry,
    ReminderChannel,
    SubAgenda,
    SubAgendaStatus,
    Todo,
    TodoSource,
    User,
)
from app.services import points_service, streak_service

TZ = "Africa/Lagos"


async def _seed_history(*, days_elapsed: int, completed_days: int) -> dict:
    """An agenda that started ``days_elapsed`` days ago with one to-do per day."""
    today = local_today(TZ)
    start = today - timedelta(days=days_elapsed)

    async with session_scope() as session:
        user = User(
            email="history@example.com",
            password_hash="x",
            full_name="Historian",
            timezone=TZ,
        )
        session.add(user)
        await session.flush()

        agenda = Agenda(
            user_id=user.id,
            title="Finish the dissertation",
            description="Write and defend.",
            timeframe_days=days_elapsed + 2,
            start_date=start,
            end_date=start + timedelta(days=days_elapsed + 1),
            reminder_channel=ReminderChannel.EMAIL,
            timezone=TZ,
            status=AgendaStatus.ACTIVE,
        )
        session.add(agenda)
        await session.flush()

        for offset in range(days_elapsed + 2):
            day = start + timedelta(days=offset)
            sub = SubAgenda(
                agenda_id=agenda.id,
                day_index=offset + 1,
                scheduled_date=day,
                title=f"Day {offset + 1}",
                expected_outcome="A section exists.",
                status=SubAgendaStatus.PLANNED,
            )
            session.add(sub)
            await session.flush()

            for position in range(2):
                done = offset < completed_days
                session.add(
                    Todo(
                        sub_agenda_id=sub.id,
                        user_id=user.id,
                        agenda_id=agenda.id,
                        position=position,
                        title=f"Task {position + 1}",
                        points=settings.task_completed_points,
                        source=TodoSource.AGENT,
                        is_done=done,
                        completion_seq=1 if done else 0,
                    )
                )
            if done:
                await points_service.apply(
                    session,
                    key=f"todo:{sub.id}:completed:1",
                    user_id=user.id,
                    reason=LedgerReason.TASK_COMPLETED,
                    delta=2 * settings.task_completed_points,
                    occurred_on=day,
                    agenda_id=agenda.id,
                    sub_agenda_id=sub.id,
                )

        await session.flush()
        return {"user_id": user.id, "agenda_id": agenda.id, "start": start}


@pytest.mark.asyncio
async def test_missed_days_are_penalised_and_streak_resets():
    seeded = await _seed_history(days_elapsed=3, completed_days=1)

    async with session_scope() as session:
        agenda = await session.get(Agenda, seeded["agenda_id"])
        stats = await streak_service.close_finished_days(session, agenda)
        user = await session.get(User, seeded["user_id"])
        await streak_service.recompute(session, user)

    assert stats["days"] == 3
    assert stats["missed"] == 2
    assert stats["penalty"] == -2 * settings.missed_day_deduction

    async with session_scope() as session:
        statuses = dict(
            (
                await session.execute(
                    select(SubAgenda.day_index, SubAgenda.status).where(
                        SubAgenda.agenda_id == seeded["agenda_id"]
                    )
                )
            ).all()
        )
        assert statuses[1] is SubAgendaStatus.DONE
        assert statuses[2] is SubAgendaStatus.MISSED
        assert statuses[3] is SubAgendaStatus.MISSED

        # Today's day and the one after it are untouched.
        assert statuses[4] is SubAgendaStatus.PLANNED

        user = await session.get(User, seeded["user_id"])
        # Day 1 complete, day 2 missed, so the streak is zero.
        assert user.current_streak == 0

        ledger_total = await session.scalar(
            select(func.coalesce(func.sum(PointsLedgerEntry.delta), 0)).where(
                PointsLedgerEntry.user_id == seeded["user_id"]
            )
        )
        expected = 2 * settings.task_completed_points - 2 * settings.missed_day_deduction
        assert int(ledger_total) == expected
        assert user.points_balance == expected


@pytest.mark.asyncio
async def test_closing_days_is_idempotent():
    seeded = await _seed_history(days_elapsed=2, completed_days=0)

    async with session_scope() as session:
        agenda = await session.get(Agenda, seeded["agenda_id"])
        await streak_service.close_finished_days(session, agenda)

    async with session_scope() as session:
        agenda = await session.get(Agenda, seeded["agenda_id"])
        second = await streak_service.close_finished_days(session, agenda)

    assert second["days"] == 0, "already-closed days must not be closed again"

    async with session_scope() as session:
        penalties = await session.scalar(
            select(func.count(PointsLedgerEntry.id)).where(
                PointsLedgerEntry.reason == LedgerReason.DAY_MISSED
            )
        )
        assert penalties == 2


@pytest.mark.asyncio
async def test_overdue_tasks_are_not_carried_forward():
    await _seed_history(days_elapsed=2, completed_days=0)

    async with session_scope() as session:
        today = local_today(TZ)
        today_todos = await session.scalar(
            select(func.count(Todo.id))
            .join(SubAgenda, SubAgenda.id == Todo.sub_agenda_id)
            .where(SubAgenda.scheduled_date == today)
        )
        # Today's day has its own two to-dos and nothing rolled in from the past.
        assert today_todos == 2

        overdue_still_there = await session.scalar(
            select(func.count(Todo.id))
            .join(SubAgenda, SubAgenda.id == Todo.sub_agenda_id)
            .where(SubAgenda.scheduled_date < today, Todo.is_done.is_(False))
        )
        assert overdue_still_there == 4


@pytest.mark.asyncio
async def test_disabling_deductions_makes_missed_days_points_neutral(monkeypatch):
    monkeypatch.setattr(settings, "allow_point_deductions", False)
    seeded = await _seed_history(days_elapsed=1, completed_days=0)

    async with session_scope() as session:
        agenda = await session.get(Agenda, seeded["agenda_id"])
        stats = await streak_service.close_finished_days(session, agenda)

    assert stats["missed"] == 1
    assert stats["penalty"] == 0
