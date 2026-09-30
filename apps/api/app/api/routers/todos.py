"""To-do endpoints, including completion and the points it awards."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import MessageOut
from app.schemas.todo import (
    CompleteResponse,
    CompletionPoints,
    DayCompletion,
    StreakSnapshot,
    TodoCreate,
    TodoOut,
    TodoReorder,
    TodoUpdate,
)
from app.services import todo_service

router = APIRouter(tags=["todos"])


def _complete_response(result: todo_service.CompletionResult) -> CompleteResponse:
    return CompleteResponse(
        todo=TodoOut.model_validate(result.todo),
        points=CompletionPoints(
            awarded=result.awarded,
            reason=result.bonuses[0] if result.bonuses else "task_completed",
            balance=result.balance,
            bonuses=result.bonuses,
        ),
        day=DayCompletion(
            complete=result.day.complete,
            done=result.day.done,
            total=result.day.total,
            bonus_awarded=result.day.bonus,
        ),
        streak=StreakSnapshot(current=result.streak_current, longest=result.streak_longest),
        agenda_completed=result.agenda_completed,
    )


@router.post(
    "/sub-agendas/{sub_agenda_id}/todos",
    response_model=TodoOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_todo(
    sub_agenda_id: uuid.UUID,
    payload: TodoCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    sub = await todo_service.get_owned_sub_agenda(session, sub_agenda_id, user.id)
    todo = await todo_service.create_todo(
        session, sub, title=payload.title, notes=payload.notes, position=payload.position
    )
    return TodoOut.model_validate(todo)


@router.post("/sub-agendas/{sub_agenda_id}/todos/reorder", response_model=list[TodoOut])
async def reorder_todos(
    sub_agenda_id: uuid.UUID,
    payload: TodoReorder,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    sub = await todo_service.get_owned_sub_agenda(session, sub_agenda_id, user.id)
    rows = await todo_service.reorder_todos(session, sub, payload.order)
    return [TodoOut.model_validate(row) for row in rows]


@router.patch("/todos/{todo_id}", response_model=TodoOut)
async def update_todo(
    todo_id: uuid.UUID,
    payload: TodoUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    todo = await todo_service.get_owned_todo(session, todo_id, user.id)
    await todo_service.update_todo(
        session, todo, title=payload.title, notes=payload.notes, position=payload.position
    )
    return TodoOut.model_validate(todo)


@router.delete("/todos/{todo_id}", response_model=MessageOut)
async def delete_todo(
    todo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    todo = await todo_service.get_owned_todo(session, todo_id, user.id)
    await todo_service.delete_todo(session, todo)
    return MessageOut(detail="To-do removed")


@router.post("/todos/{todo_id}/complete", response_model=CompleteResponse)
async def complete_todo(
    todo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CompleteResponse:
    result = await todo_service.complete_todo(session, todo_id, user)
    return _complete_response(result)


@router.post("/todos/{todo_id}/uncomplete", response_model=CompleteResponse)
async def uncomplete_todo(
    todo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CompleteResponse:
    result = await todo_service.uncomplete_todo(session, todo_id, user)
    return _complete_response(result)
