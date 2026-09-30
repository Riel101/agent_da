"""Agenda endpoints: create, generate, review, approve, progress."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.errors import ConflictError
from app.db.session import get_db
from app.models import AgendaStatus, DraftStatus, User
from app.schemas.agenda import (
    AgendaCreate,
    AgendaOut,
    AgendaProgressOut,
    AgendaSummary,
    AgendaUpdate,
    ApproveOut,
    ClarifyingAnswersIn,
    DayDetailOut,
    DayUpdateIn,
    DraftOut,
    GenerateOut,
    RegenerateIn,
    SubAgendaOut,
)
from app.schemas.common import MessageOut, Page
from app.schemas.todo import TodoOut
from app.services import agenda_service, materializer, plan_service

router = APIRouter(prefix="/agendas", tags=["agendas"])


@router.get("", response_model=Page[AgendaSummary])
async def list_agendas(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    status_filter: AgendaStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[AgendaSummary]:
    agendas, total = await agenda_service.list_agendas(
        session, user.id, status=status_filter, page=page, limit=limit
    )
    return Page[AgendaSummary](
        items=[AgendaSummary.model_validate(row) for row in await agenda_service.summarise_many(session, agendas)],
        page=page,
        limit=limit,
        total=total,
    )


@router.post("", response_model=AgendaOut, status_code=status.HTTP_201_CREATED)
async def create_agenda(
    payload: AgendaCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AgendaOut:
    agenda = await agenda_service.create_agenda(session, user, payload)
    return AgendaOut.model_validate(agenda)


@router.get("/{agenda_id}", response_model=AgendaSummary)
async def read_agenda(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AgendaSummary:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    return AgendaSummary.model_validate(await agenda_service.summarise(session, agenda))


@router.patch("/{agenda_id}", response_model=AgendaSummary)
async def update_agenda(
    agenda_id: uuid.UUID,
    payload: AgendaUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AgendaSummary:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    await agenda_service.update_agenda(session, agenda, payload)
    return AgendaSummary.model_validate(await agenda_service.summarise(session, agenda))


@router.delete("/{agenda_id}", response_model=MessageOut)
async def cancel_agenda(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    agenda.status = AgendaStatus.CANCELLED
    return MessageOut(detail="Agenda cancelled")


@router.post("/{agenda_id}/archive", response_model=MessageOut)
async def archive_agenda(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MessageOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    if agenda.status not in {AgendaStatus.COMPLETED, AgendaStatus.CANCELLED, AgendaStatus.ACTIVE}:
        raise ConflictError("Only a running or finished agenda can be archived")
    agenda.status = AgendaStatus.ARCHIVED
    return MessageOut(detail="Agenda archived")


# --------------------------------------------------------------- generation


@router.post("/{agenda_id}/generate", response_model=GenerateOut, status_code=status.HTTP_202_ACCEPTED)
async def generate(
    agenda_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GenerateOut:
    ratelimit.enforce(
        f"generate:{user.id}",
        limit=settings.generate_rate_limit_per_hour,
        window_seconds=3600,
    )
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    if agenda.status is AgendaStatus.ACTIVE:
        raise ConflictError("This agenda is already running", code="AGENDA_ACTIVE")

    draft = await plan_service.latest_draft(session, agenda.id)
    if draft is not None and draft.status in {
        DraftStatus.QUEUED,
        DraftStatus.RUNNING,
        DraftStatus.NEEDS_INPUT,
        DraftStatus.NEEDS_REVIEW,
    }:
        # Reuse the in-flight draft rather than burning another generation.
        return GenerateOut(draft_id=draft.id, status=draft.status, revision=draft.revision)

    draft = await plan_service.create_draft(session, agenda)
    agenda.status = AgendaStatus.GENERATING
    await session.commit()

    plan_service.spawn_generation(draft.id)
    return GenerateOut(draft_id=draft.id, status=draft.status, revision=draft.revision)


@router.get("/{agenda_id}/draft", response_model=DraftOut)
async def read_draft(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DraftOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    draft = await plan_service.latest_draft(session, agenda.id)
    if draft is None:
        raise ConflictError(
            "No plan has been generated for this agenda yet", code="NO_DRAFT"
        )
    days = await agenda_service.list_days(session, agenda)
    return DraftOut.model_validate(plan_service.draft_out(draft, days))


@router.post("/{agenda_id}/draft/answers", response_model=GenerateOut, status_code=status.HTTP_202_ACCEPTED)
async def submit_answers(
    agenda_id: uuid.UUID,
    payload: ClarifyingAnswersIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GenerateOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    draft = await plan_service.latest_draft(session, agenda.id)
    if draft is None:
        raise ConflictError("No plan has been generated yet", code="NO_DRAFT")
    await plan_service.submit_answers(session, draft, payload.answers)
    return GenerateOut(draft_id=draft.id, status=draft.status, revision=draft.revision)


@router.post("/{agenda_id}/approve", response_model=ApproveOut)
async def approve(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApproveOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id, lock=True)
    draft = await plan_service.latest_draft(session, agenda.id)
    if draft is None:
        raise ConflictError("Generate a plan before approving", code="NO_DRAFT")

    result = await plan_service.approve_agenda(session, agenda, draft)
    summary = await agenda_service.summarise(session, agenda)
    return ApproveOut(
        agenda=AgendaOut.model_validate(summary),
        scheduled_reminders=result["scheduled_reminders"],
        expanded_days=result["expanded_days"],
    )


@router.post("/{agenda_id}/regenerate", response_model=GenerateOut, status_code=status.HTTP_202_ACCEPTED)
async def regenerate(
    agenda_id: uuid.UUID,
    payload: RegenerateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GenerateOut:
    ratelimit.enforce(
        f"generate:{user.id}",
        limit=settings.generate_rate_limit_per_hour,
        window_seconds=3600,
    )
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    draft = await plan_service.latest_draft(session, agenda.id)
    if draft is None:
        raise ConflictError("Generate a plan first", code="NO_DRAFT")

    await plan_service.regenerate(
        session,
        agenda,
        draft,
        scope=payload.scope,
        day_index=payload.day_index,
        instructions=payload.instructions,
    )
    return GenerateOut(draft_id=draft.id, status=draft.status, revision=draft.revision)


# ------------------------------------------------------------------- days


@router.get("/{agenda_id}/days", response_model=list[SubAgendaOut])
async def list_days(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SubAgendaOut]:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    return [SubAgendaOut.model_validate(row) for row in await agenda_service.list_days(session, agenda)]


@router.get("/{agenda_id}/days/{day_index}", response_model=DayDetailOut)
async def read_day(
    agenda_id: uuid.UUID,
    day_index: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DayDetailOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    sub = await agenda_service.get_day(session, agenda, day_index)
    return DayDetailOut(
        sub_agenda=SubAgendaOut.model_validate(sub),
        todos=[TodoOut.model_validate(todo) for todo in sub.todos],
    )


@router.patch("/{agenda_id}/days/{day_index}", response_model=SubAgendaOut)
async def update_day(
    agenda_id: uuid.UUID,
    day_index: int,
    payload: DayUpdateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SubAgendaOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    if agenda.status in {AgendaStatus.COMPLETED, AgendaStatus.ARCHIVED, AgendaStatus.CANCELLED}:
        raise ConflictError("This agenda is closed", code="AGENDA_CLOSED")
    sub = await agenda_service.get_day(session, agenda, day_index)
    await agenda_service.update_day(
        session,
        sub,
        title=payload.title,
        description=payload.description,
        expected_outcome=payload.expected_outcome,
        expected_effort_minutes=payload.expected_effort_minutes,
    )
    return SubAgendaOut.model_validate(sub)


@router.get("/{agenda_id}/progress", response_model=AgendaProgressOut)
async def progress(
    agenda_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AgendaProgressOut:
    agenda = await agenda_service.get_agenda(session, agenda_id, user.id)
    stats = await materializer.agenda_progress(session, agenda)
    return AgendaProgressOut.model_validate(
        {"agenda_id": agenda.id, "status": agenda.status, **stats}
    )
