"""To-do lifecycle: CRUD, completion and un-completion.

Completion is the point where gamification happens, so this module owns the
transaction: task points, the day bonus, streak recomputation, milestone bonus
and agenda completion are all applied in one atomic step.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.core.logging import get_logger
from app.core.timezones import local_today, utc_now
from app.models import (
    Agenda,
    AgendaStatus,
    LedgerReason,
    SubAgenda,
    SubAgendaStatus,
    Todo,
    TodoSource,
    User,
)
from app.services import points_service, streak_service

logger = get_logger(__name__)


@dataclass(slots=True)
class DayEvaluation:
    total: int = 0
    done: int = 0
    complete: bool = False
    became_complete: bool = False
    bonus: int = 0


@dataclass(slots=True)
class CompletionResult:
    todo: Todo
    awarded: int = 0
    balance: int = 0
    bonuses: list[str] = field(default_factory=list)
    day: DayEvaluation = field(default_factory=DayEvaluation)
    streak_current: int = 0
    streak_longest: int = 0
    agenda_completed: bool = False


async def count_day(session: AsyncSession, sub_agenda_id: uuid.UUID) -> tuple[int, int]:
    total = await session.scalar(
        select(func.count(Todo.id)).where(Todo.sub_agenda_id == sub_agenda_id)
    )
    done = await session.scalar(
        select(func.count(Todo.id)).where(
            Todo.sub_agenda_id == sub_agenda_id, Todo.is_done.is_(True)
        )
    )
    return int(total or 0), int(done or 0)


async def evaluate_day(
    session: AsyncSession,
    sub: SubAgenda,
    *,
    occurred_on: date,
    user_id: uuid.UUID,
    award: bool = True,
) -> DayEvaluation:
    """Recount a day and, if it just became complete, pay the day bonus."""
    total, done = await count_day(session, sub.id)
    evaluation = DayEvaluation(total=total, done=done, complete=total > 0 and done == total)

    if not evaluation.complete or not award:
        if not evaluation.complete and sub.status is SubAgendaStatus.DONE:
            sub.status = SubAgendaStatus.IN_PROGRESS
        return evaluation

    if sub.status is SubAgendaStatus.DONE:
        return evaluation

    sub.status = SubAgendaStatus.DONE
    sub.completion_seq += 1
    evaluation.became_complete = True

    move = await points_service.apply(
        session,
        key=f"day:{sub.id}:complete:{sub.completion_seq}",
        user_id=user_id,
        reason=LedgerReason.DAY_COMPLETE,
        delta=settings.day_complete_bonus,
        occurred_on=occurred_on,
        agenda_id=sub.agenda_id,
        sub_agenda_id=sub.id,
        meta={"day_index": sub.day_index},
    )
    evaluation.bonus = move.delta if move.applied else 0
    return evaluation


async def get_owned_todo(
    session: AsyncSession, todo_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
) -> Todo:
    stmt = select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    todo = await session.scalar(stmt)
    if todo is None:
        raise NotFoundError("To-do not found", code="TODO_NOT_FOUND")
    return todo


async def get_owned_sub_agenda(
    session: AsyncSession, sub_agenda_id: uuid.UUID, user_id: uuid.UUID
) -> SubAgenda:
    sub = await session.scalar(
        select(SubAgenda)
        .join(Agenda, Agenda.id == SubAgenda.agenda_id)
        .where(SubAgenda.id == sub_agenda_id, Agenda.user_id == user_id)
    )
    if sub is None:
        raise NotFoundError("Day not found", code="SUB_AGENDA_NOT_FOUND")
    return sub


async def list_todos(session: AsyncSession, sub_agenda_id: uuid.UUID) -> list[Todo]:
    rows = await session.execute(
        select(Todo).where(Todo.sub_agenda_id == sub_agenda_id).order_by(Todo.position)
    )
    return list(rows.scalars().all())


async def create_todo(
    session: AsyncSession,
    sub: SubAgenda,
    *,
    title: str,
    notes: str | None = None,
    position: int | None = None,
) -> Todo:
    if sub.agenda.status in {AgendaStatus.COMPLETED, AgendaStatus.ARCHIVED, AgendaStatus.CANCELLED}:
        raise ValidationError("This agenda is closed and can no longer be edited")

    max_position = await session.scalar(
        select(func.coalesce(func.max(Todo.position), -1)).where(Todo.sub_agenda_id == sub.id)
    )
    target = position if position is not None else int(max_position or -1) + 1

    todo = Todo(
        sub_agenda_id=sub.id,
        user_id=sub.agenda.user_id,
        agenda_id=sub.agenda_id,
        position=int(target),
        title=title.strip(),
        notes=notes,
        points=settings.task_completed_points,
        source=TodoSource.USER,
    )
    session.add(todo)
    await session.flush()

    total, done = await count_day(session, sub.id)
    if sub.status is SubAgendaStatus.DONE and done != total:
        sub.status = SubAgendaStatus.IN_PROGRESS
    return todo


async def update_todo(
    session: AsyncSession,
    todo: Todo,
    *,
    title: str | None = None,
    notes: str | None = None,
    position: int | None = None,
) -> Todo:
    if title is not None:
        if not title.strip():
            raise ValidationError("Title cannot be blank")
        todo.title = title.strip()
    if notes is not None:
        todo.notes = notes
    if position is not None and position != todo.position:
        await _move_todo(session, todo, position)
    await session.flush()
    return todo


async def _move_todo(session: AsyncSession, todo: Todo, position: int) -> None:
    """Re-order within a day without tripping the (day, position) unique key."""
    siblings = (
        await session.execute(
            select(Todo)
            .where(Todo.sub_agenda_id == todo.sub_agenda_id)
            .order_by(Todo.position)
            .with_for_update()
        )
    ).scalars().all()

    ordered = [item for item in siblings if item.id != todo.id]
    index = max(0, min(position, len(ordered)))
    ordered.insert(index, todo)

    # Park every row on a temporary high position, then assign the final order.
    await session.execute(
        update(Todo)
        .where(Todo.sub_agenda_id == todo.sub_agenda_id)
        .values(position=Todo.position + 10_000)
    )
    for slot, item in enumerate(ordered):
        item.position = slot
    await session.flush()


async def reorder_todos(
    session: AsyncSession, sub: SubAgenda, order: list[uuid.UUID]
) -> list[Todo]:
    todos = await list_todos(session, sub.id)
    by_id = {item.id: item for item in todos}

    if set(order) != set(by_id):
        raise ValidationError("Order must list every to-do on this day exactly once")

    await session.execute(
        update(Todo).where(Todo.sub_agenda_id == sub.id).values(position=Todo.position + 10_000)
    )
    for slot, todo_id in enumerate(order):
        by_id[todo_id].position = slot
    await session.flush()
    return await list_todos(session, sub.id)


async def delete_todo(session: AsyncSession, todo: Todo) -> DayEvaluation:
    sub = await session.scalar(
        select(SubAgenda).where(SubAgenda.id == todo.sub_agenda_id).with_for_update()
    )
    agenda = await session.get(Agenda, todo.agenda_id)
    await session.delete(todo)
    await session.flush()
    if sub is None or agenda is None:
        return DayEvaluation()
    return await evaluate_day(
        session, sub, occurred_on=local_today(agenda.timezone), user_id=agenda.user_id
    )


async def complete_todo(
    session: AsyncSession, todo_id: uuid.UUID, user: User
) -> CompletionResult:
    todo = await get_owned_todo(session, todo_id, user.id, lock=True)
    agenda = await session.get(Agenda, todo.agenda_id)
    if agenda is None:
        raise NotFoundError("Agenda not found", code="AGENDA_NOT_FOUND")

    sub = await session.scalar(
        select(SubAgenda).where(SubAgenda.id == todo.sub_agenda_id).with_for_update()
    )
    if sub is None:
        raise NotFoundError("Day not found", code="SUB_AGENDA_NOT_FOUND")

    today = local_today(user.timezone)
    result = CompletionResult(todo=todo, balance=await points_service.current_balance(session, user.id))

    if todo.is_done:
        # Idempotent: already counted, so award nothing.
        result.awarded = 0
        result.bonuses.append("already_complete")
        return await _finalise(session, result, sub, user, today)

    todo.is_done = True
    todo.completed_at = utc_now()
    todo.completion_seq += 1

    move = await points_service.apply(
        session,
        key=f"todo:{todo.id}:completed:{todo.completion_seq}",
        user_id=user.id,
        reason=LedgerReason.TASK_COMPLETED,
        delta=todo.points,
        occurred_on=today,
        agenda_id=agenda.id,
        sub_agenda_id=sub.id,
        todo_id=todo.id,
    )
    result.awarded = move.delta if move.applied else 0
    result.balance = move.balance

    result.day = await evaluate_day(session, sub, occurred_on=today, user_id=user.id)
    if result.day.bonus:
        result.bonuses.append("day_complete")

    if result.day.became_complete:
        await streak_service.recompute(session, user, through_date=today)
        milestone = await streak_service.award_milestones(session, user, occurred_on=today)
        if milestone:
            result.bonuses.append("streak_milestone")
            result.balance = await points_service.current_balance(session, user.id)

        if sub.day_index == agenda.timeframe_days and agenda.status is AgendaStatus.ACTIVE:
            await _complete_agenda(session, agenda, user, today, result)

    return await _finalise(session, result, sub, user, today)


async def _complete_agenda(
    session: AsyncSession,
    agenda: Agenda,
    user: User,
    today: date,
    result: CompletionResult,
) -> None:
    agenda.status = AgendaStatus.COMPLETED
    agenda.completed_at = utc_now()

    move = await points_service.apply(
        session,
        key=f"agenda:{agenda.id}:complete",
        user_id=user.id,
        reason=LedgerReason.AGENDA_COMPLETE,
        delta=settings.agenda_complete_bonus,
        occurred_on=today,
        agenda_id=agenda.id,
        meta={"title": agenda.title, "days": agenda.timeframe_days},
    )
    if move.applied:
        result.bonuses.append("agenda_complete")

    if not await streak_service.has_missed_days(session, agenda.id):
        agenda.perfect_run = True
        perfect = await points_service.apply(
            session,
            key=f"agenda:{agenda.id}:perfect",
            user_id=user.id,
            reason=LedgerReason.PERFECT_RUN,
            delta=settings.perfect_run_bonus,
            occurred_on=today,
            agenda_id=agenda.id,
        )
        if perfect.applied:
            result.bonuses.append("perfect_run")

    result.agenda_completed = True


async def _finalise(
    session: AsyncSession,
    result: CompletionResult,
    sub: SubAgenda,
    user: User,
    today: date,
) -> CompletionResult:
    await session.flush()
    total, done = await count_day(session, sub.id)
    result.day = DayEvaluation(
        total=total, done=done, complete=total > 0 and done == total, bonus=result.day.bonus,
        became_complete=result.day.became_complete,
    )
    result.streak_current = user.current_streak
    result.streak_longest = user.longest_streak
    if result.awarded == 0 and not result.day.bonus:
        result.balance = await points_service.current_balance(session, user.id)
    return result


async def uncomplete_todo(
    session: AsyncSession, todo_id: uuid.UUID, user: User
) -> CompletionResult:
    todo = await get_owned_todo(session, todo_id, user.id, lock=True)
    agenda = await session.get(Agenda, todo.agenda_id)
    if agenda is None:
        raise NotFoundError("Agenda not found", code="AGENDA_NOT_FOUND")

    sub = await session.scalar(
        select(SubAgenda).where(SubAgenda.id == todo.sub_agenda_id).with_for_update()
    )
    if sub is None:
        raise NotFoundError("Day not found", code="SUB_AGENDA_NOT_FOUND")

    today = local_today(user.timezone)
    result = CompletionResult(todo=todo)

    if not todo.is_done:
        result.bonuses.append("already_open")
        return await _finalise(session, result, sub, user, today)

    todo.is_done = False
    todo.completed_at = None

    move = await points_service.apply(
        session,
        key=f"todo:{todo.id}:uncompleted:{todo.completion_seq}",
        user_id=user.id,
        reason=LedgerReason.TASK_UNCOMPLETED,
        delta=-todo.points,
        occurred_on=today,
        agenda_id=agenda.id,
        sub_agenda_id=sub.id,
        todo_id=todo.id,
    )
    result.awarded = move.delta if move.applied else 0
    if move.applied:
        result.bonuses.append("task_uncompleted")

    if sub.status is SubAgendaStatus.DONE:
        await points_service.apply(
            session,
            key=f"day:{sub.id}:uncompleted:{sub.completion_seq}",
            user_id=user.id,
            reason=LedgerReason.TASK_UNCOMPLETED,
            delta=-settings.day_complete_bonus,
            occurred_on=today,
            agenda_id=agenda.id,
            sub_agenda_id=sub.id,
        )
        sub.status = SubAgendaStatus.IN_PROGRESS
        result.bonuses.append("day_reopened")

    if agenda.status is AgendaStatus.COMPLETED:
        await points_service.apply(
            session,
            key=f"agenda:{agenda.id}:uncompleted",
            user_id=user.id,
            reason=LedgerReason.ADJUSTMENT,
            delta=-settings.agenda_complete_bonus,
            occurred_on=today,
            agenda_id=agenda.id,
        )
        agenda.status = AgendaStatus.ACTIVE
        agenda.completed_at = None
        if agenda.perfect_run:
            await points_service.apply(
                session,
                key=f"agenda:{agenda.id}:perfect_uncompleted",
                user_id=user.id,
                reason=LedgerReason.ADJUSTMENT,
                delta=-settings.perfect_run_bonus,
                occurred_on=today,
                agenda_id=agenda.id,
            )
            agenda.perfect_run = False
        result.bonuses.append("agenda_reopened")

    return await _finalise(session, result, sub, user, today)


async def ensure_owner(session: AsyncSession, sub: SubAgenda, user_id: uuid.UUID) -> None:
    owner = await session.scalar(select(Agenda.user_id).where(Agenda.id == sub.agenda_id))
    if owner != user_id:
        raise PermissionDeniedError("You do not own this day")


async def purge_day_todos(session: AsyncSession, sub_agenda_id: uuid.UUID) -> int:
    """Remove agent-generated to-dos for a day (used when regenerating a day)."""
    result = await session.execute(delete(Todo).where(Todo.sub_agenda_id == sub_agenda_id))
    return int(result.rowcount or 0)
