"""Plan lifecycle: generate, review, regenerate, approve.

The graph is *pure* — it returns state. This module owns everything that
persists: drafts, sub-agendas, to-dos and the activation that schedules
reminders. That separation keeps the graph testable and the DB writes
transactional.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import PROMPT_SET_VERSION
from app.agents.runner import GraphOutcome, runner
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.timezones import local_today, utc_now
from app.db.session import session_scope
from app.models import (
    Agenda,
    AgendaDraft,
    AgendaStatus,
    DraftStatus,
    SubAgenda,
    SubAgendaStatus,
    User,
)
from app.services import materializer, reminder_service

logger = get_logger(__name__)

#: Keeps fire-and-forget generation tasks referenced so they are not GC'd.
_background: set[asyncio.Task] = set()
_generation_slots = asyncio.Semaphore(2)


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def wait_for_background(timeout: float = 120.0) -> None:
    """Test/shutdown helper: wait for in-flight generation tasks."""
    pending = [task for task in _background if not task.done()]
    if pending:
        await asyncio.wait(pending, timeout=timeout)


# ------------------------------------------------------------------- state


def initial_state(agenda: Agenda, user: User, draft: AgendaDraft) -> dict[str, Any]:
    return {
        "user_id": str(user.id),
        "agenda_id": str(agenda.id),
        "draft_id": str(draft.id),
        "title": agenda.title,
        "description": agenda.description or "",
        "timeframe_days": agenda.timeframe_days,
        "start_date": agenda.start_date.isoformat(),
        "end_date": agenda.end_date.isoformat(),
        "timezone": agenda.timezone,
        "full_name": user.full_name or "",
        "streak": user.current_streak,
        "prompt_version": PROMPT_SET_VERSION,
        "repair_passes": 0,
        "phase": "intake",
        "tokens_in": 0,
        "tokens_out": 0,
        "sub_agendas": [],
        "todos": [],
        "issues": [],
    }


# -------------------------------------------------------------- persistence


def _day_from_state(raw: dict, agenda: Agenda, draft: AgendaDraft) -> SubAgenda:
    return SubAgenda(
        agenda_id=agenda.id,
        draft_id=draft.id,
        day_index=int(raw["day_index"]),
        scheduled_date=date.fromisoformat(raw["scheduled_date"]),
        title=str(raw["title"])[:300],
        description=raw.get("description"),
        expected_outcome=raw.get("expected_outcome"),
        expected_effort_minutes=raw.get("expected_effort_minutes"),
        phase=raw.get("phase"),
        status=SubAgendaStatus.PLANNED,
    )


async def persist_review(
    session: AsyncSession, agenda: Agenda, draft: AgendaDraft, state: dict[str, Any]
) -> dict[str, int]:
    """Write the graph's plan onto the agenda. Idempotent per day_index."""
    plan = state.get("sub_agendas") or []
    todos = state.get("todos") or []

    existing = {
        row.day_index: row
        for row in (
            await session.execute(select(SubAgenda).where(SubAgenda.agenda_id == agenda.id))
        ).scalars()
    }

    by_day: dict[int, list[dict]] = {}
    for entry in todos:
        by_day.setdefault(int(entry["day_index"]), []).append(entry)

    created = 0
    updated = 0
    for raw in plan:
        index = int(raw["day_index"])
        row = existing.get(index)
        expected_date = date.fromisoformat(raw["scheduled_date"])

        if row is None:
            row = _day_from_state(raw, agenda, draft)
            session.add(row)
            existing[index] = row
            created += 1
        else:
            # Never clobber a day the user hand-edited.
            row.draft_id = draft.id
            row.scheduled_date = expected_date
            if not row.is_user_edited:
                row.title = str(raw["title"])[:300]
                row.description = raw.get("description")
                row.expected_outcome = raw.get("expected_outcome")
                row.expected_effort_minutes = raw.get("expected_effort_minutes")
                row.phase = raw.get("phase")
            updated += 1

    await session.flush()

    for index, items in by_day.items():
        row = existing.get(index)
        if row is None:
            continue
        await materializer.replace_agent_todos(session, agenda, row, items)

    return {"days_created": created, "days_updated": updated, "todos": len(todos)}


# ------------------------------------------------------------------ outcomes


async def _apply_outcome(draft_id: uuid.UUID, outcome: GraphOutcome) -> None:
    async with session_scope() as session:
        draft = await session.get(AgendaDraft, draft_id)
        if draft is None:
            logger.warning("draft %s vanished before its outcome was applied", draft_id)
            return

        agenda = await session.get(Agenda, draft.agenda_id)
        if agenda is None:
            return

        draft.model = outcome.state.get("model") or draft.model
        draft.prompt_version = outcome.state.get("prompt_version") or PROMPT_SET_VERSION
        draft.tokens_in = int(outcome.state.get("tokens_in") or 0)
        draft.tokens_out = int(outcome.state.get("tokens_out") or 0)
        draft.repair_passes = int(outcome.state.get("repair_passes") or 0)
        draft.validation_issues = outcome.state.get("issues") or []
        draft.raw_plan = {
            "sub_agendas": outcome.state.get("sub_agendas") or [],
            "todos": outcome.state.get("todos") or [],
        }

        if outcome.failed:
            draft.status = DraftStatus.FAILED
            draft.error = outcome.error
            agenda.status = AgendaStatus.DRAFT
            logger.warning("draft %s failed: %s", draft_id, outcome.error)
            return

        if outcome.interrupted and outcome.kind == "clarifications":
            draft.status = DraftStatus.NEEDS_INPUT
            draft.clarifying_questions = outcome.payload.get("questions") or []
            agenda.status = AgendaStatus.GENERATING
            return

        stats = await persist_review(session, agenda, draft, outcome.state)
        draft.status = DraftStatus.NEEDS_REVIEW
        draft.clarifying_questions = []
        draft.stats = {
            "days": len(outcome.state.get("sub_agendas") or []),
            "todos": stats["todos"],
            "expanded_days": len(
                {int(entry["day_index"]) for entry in outcome.state.get("todos") or []}
            ),
        }
        agenda.status = AgendaStatus.READY
        logger.info("draft %s ready for review: %s", draft_id, draft.stats)


async def _run_guarded(draft_id: uuid.UUID, coro_factory) -> None:
    async with _generation_slots:
        try:
            outcome = await coro_factory()
        except Exception as exc:  # noqa: BLE001 - always recorded on the draft
            logger.exception("generation failed for draft %s", draft_id)
            async with session_scope() as session:
                draft = await session.get(AgendaDraft, draft_id)
                if draft is not None:
                    draft.status = DraftStatus.FAILED
                    draft.error = str(exc)[:1000]
                    agenda = await session.get(Agenda, draft.agenda_id)
                    if agenda is not None:
                        agenda.status = AgendaStatus.DRAFT
            return
        await _apply_outcome(draft_id, outcome)


def spawn_generation(draft_id: uuid.UUID) -> None:
    if not settings.agent_autostart:
        logger.info("agent autostart disabled; draft %s awaits a worker", draft_id)
        return
    spawn(_run_guarded(draft_id, lambda: _start(draft_id)))


def spawn_resume(draft_id: uuid.UUID, payload: dict[str, Any]) -> None:
    if not settings.agent_autostart:
        logger.info("agent autostart disabled; draft %s awaits a worker", draft_id)
        return
    spawn(_run_guarded(draft_id, lambda: _resume(draft_id, payload)))


async def _start(draft_id: uuid.UUID) -> GraphOutcome:
    async with session_scope() as session:
        draft = await session.get(AgendaDraft, draft_id)
        if draft is None:
            raise NotFoundError("Draft not found", code="DRAFT_NOT_FOUND")
        agenda = await session.get(Agenda, draft.agenda_id)
        user = await session.get(User, agenda.user_id)
        draft.status = DraftStatus.RUNNING
        draft.error = None
        agenda.status = AgendaStatus.GENERATING
        state = initial_state(agenda, user, draft)

    return await runner.start(str(draft_id), state)


async def _resume(draft_id: uuid.UUID, payload: dict[str, Any]) -> GraphOutcome:
    async with session_scope() as session:
        draft = await session.get(AgendaDraft, draft_id)
        if draft is None:
            raise NotFoundError("Draft not found", code="DRAFT_NOT_FOUND")
        draft.status = DraftStatus.RUNNING
        draft.error = None
    return await runner.resume(str(draft_id), payload)


async def run_generation_now(draft_id: uuid.UUID) -> GraphOutcome:
    """Synchronous variant used by tests and the CLI."""
    outcome = await _start(draft_id)
    await _apply_outcome(draft_id, outcome)
    return outcome


async def resume_now(draft_id: uuid.UUID, payload: dict[str, Any]) -> GraphOutcome:
    outcome = await _resume(draft_id, payload)
    await _apply_outcome(draft_id, outcome)
    return outcome


# ------------------------------------------------------------------- approve


async def approve_agenda(
    session: AsyncSession, agenda: Agenda, draft: AgendaDraft
) -> dict[str, int]:
    """Activate an agenda: finalise the graph, then schedule reminders."""
    if agenda.status is AgendaStatus.ACTIVE:
        raise ConflictError("This agenda is already active", code="ALREADY_ACTIVE")
    if agenda.status in {AgendaStatus.COMPLETED, AgendaStatus.ARCHIVED, AgendaStatus.CANCELLED}:
        raise ConflictError("This agenda can no longer be approved", code="AGENDA_CLOSED")

    days = (
        await session.execute(select(SubAgenda).where(SubAgenda.agenda_id == agenda.id))
    ).scalars().all()

    if len(days) != agenda.timeframe_days:
        raise ValidationError(
            "The plan is not complete yet. Generate the plan before approving.",
            code="PLAN_INCOMPLETE",
            details={"expected": agenda.timeframe_days, "found": len(days)},
        )

    # Best effort: close the graph's review interrupt so the thread is tidy.
    try:
        await runner.resume(str(draft.id), {"decision": "approve"})
    except Exception as exc:  # noqa: BLE001 - the DB is the source of truth
        logger.debug("could not resume graph for draft %s: %s", draft.id, exc)

    if settings.max_active_agendas_per_user:
        active = await session.scalar(
            select(Agenda.id)
            .where(
                Agenda.user_id == agenda.user_id,
                Agenda.status == AgendaStatus.ACTIVE,
                Agenda.id != agenda.id,
            )
            .limit(settings.max_active_agendas_per_user)
        )
        if active is not None:
            raise ConflictError(
                "You already have the maximum number of active agendas",
                code="ACTIVE_LIMIT_REACHED",
            )

    agenda.status = AgendaStatus.ACTIVE
    agenda.approved_at = utc_now()
    draft.status = DraftStatus.APPROVED
    await session.flush()

    return await reminder_service.schedule_agenda_reminders(session, agenda, expand_preview=True)


async def regenerate(
    session: AsyncSession,
    agenda: Agenda,
    draft: AgendaDraft,
    *,
    scope: str,
    day_index: int | None = None,
    instructions: str | None = None,
) -> None:
    if agenda.status is AgendaStatus.ACTIVE:
        raise ConflictError(
            "This agenda is already running. Regenerate a single day instead.",
            code="AGENDA_ACTIVE",
        )
    if scope == "day":
        if day_index is None:
            raise ValidationError("day_index is required", code="DAY_REQUIRED")
        exists = await session.scalar(
            select(SubAgenda.id).where(
                SubAgenda.agenda_id == agenda.id, SubAgenda.day_index == day_index
            )
        )
        if exists is None:
            raise NotFoundError(f"Day {day_index} does not exist", code="DAY_NOT_FOUND")

    draft.status = DraftStatus.RUNNING
    await session.commit()

    payload: dict[str, Any] = {
        "decision": "regenerate_day" if scope == "day" else "regenerate_all",
        "day_index": day_index,
        "instructions": instructions,
    }
    spawn_resume(draft.id, payload)


async def submit_answers(
    session: AsyncSession, draft: AgendaDraft, answers: dict[str, str]
) -> None:
    if draft.status is not DraftStatus.NEEDS_INPUT:
        raise ConflictError("This draft is not waiting for answers", code="NOT_AWAITING_INPUT")
    draft.clarifying_answers = answers
    draft.status = DraftStatus.RUNNING
    await session.commit()
    spawn_resume(draft.id, {"answers": answers})


# ------------------------------------------------------------------ helpers


async def create_draft(session: AsyncSession, agenda: Agenda) -> AgendaDraft:
    revision = await session.scalar(
        select(AgendaDraft.revision)
        .where(AgendaDraft.agenda_id == agenda.id)
        .order_by(AgendaDraft.revision.desc())
        .limit(1)
    )
    draft = AgendaDraft(
        agenda_id=agenda.id,
        revision=int(revision or 0) + 1,
        status=DraftStatus.QUEUED,
        prompt_version=PROMPT_SET_VERSION,
    )
    session.add(draft)
    await session.flush()
    return draft


async def latest_draft(session: AsyncSession, agenda_id: uuid.UUID) -> AgendaDraft | None:
    return await session.scalar(
        select(AgendaDraft)
        .where(AgendaDraft.agenda_id == agenda_id)
        .order_by(AgendaDraft.revision.desc())
        .limit(1)
    )


def draft_out(draft: AgendaDraft, days: list[SubAgenda]) -> dict[str, Any]:
    return {
        "draft_id": draft.id,
        "agenda_id": draft.agenda_id,
        "status": draft.status,
        "revision": draft.revision,
        "clarifying_questions": draft.clarifying_questions or [],
        "clarifying_answers": draft.clarifying_answers,
        "validation_issues": draft.validation_issues or [],
        "error": draft.error,
        "model": draft.model,
        "prompt_version": draft.prompt_version,
        "repair_passes": draft.repair_passes,
        "stats": draft.stats or {"days": len(days)},
        "sub_agendas": [
            {
                "day_index": day.day_index,
                "scheduled_date": day.scheduled_date,
                "title": day.title,
                "description": day.description,
                "expected_outcome": day.expected_outcome,
                "expected_effort_minutes": day.expected_effort_minutes,
                "phase": day.phase,
                "todos": [
                    {"title": todo.title, "notes": todo.notes, "points": todo.points}
                    for todo in day.todos
                ],
            }
            for day in sorted(days, key=lambda row: row.day_index)
        ],
    }


def plan_window(agenda: Agenda) -> list[date]:
    return [agenda.start_date + timedelta(days=offset) for offset in range(agenda.timeframe_days)]


def current_day_index(agenda: Agenda) -> int | None:
    today = local_today(agenda.timezone)
    offset = (today - agenda.start_date).days
    if offset < 0 or offset >= agenda.timeframe_days:
        return None
    return offset + 1
