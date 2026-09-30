"""Graph nodes.

Design principle: **the model proposes, deterministic code disposes.** Every LLM
node is followed by normalisation that forces the output onto the dated skeleton,
so the count of days and their dates can never drift no matter what the model
returns.
"""

from __future__ import annotations

from datetime import date, timedelta

from langgraph.types import interrupt

from app.agents import fake
from app.agents.llm import structured_call
from app.agents.prompts import PROMPT_SET_VERSION
from app.agents.prompts import critique_v1, intake_v1, motivation_v1, plan_v1, todos_v1
from app.agents.schemas import (
    CritiqueOutput,
    DayRegenerationOutput,
    IntakeOutput,
    MotivationOutput,
    PlanOutput,
    TodoListOutput,
    TodoDraft,
)
from app.agents.state import AgendaState
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------- helpers


def phase_for(index: int, total: int) -> str:
    if total <= 1 or index >= total:
        return "finish"
    ratio = index / total
    if ratio <= 0.15:
        return "foundation"
    if ratio <= 0.50:
        return "build"
    if ratio <= 0.85:
        return "push"
    return "finish"


def _parse(value: str) -> date:
    return date.fromisoformat(value)


def _slots(state: AgendaState, *, offset: int, size: int) -> list[dict]:
    return [dict(slot) for slot in state["skeleton"][offset : offset + size]]


def _fallback_day(state: AgendaState, slot: dict) -> dict:
    raw = fake._plan_day(  # noqa: SLF001 - intentional reuse of the offline planner
        {
            "title": state["title"],
            "timeframe_days": state["timeframe_days"],
            "day": {
                "day_index": slot["day_index"],
                "phase": slot.get("phase"),
            },
        }
    )
    raw["scheduled_date"] = slot["scheduled_date"]
    raw["phase"] = slot.get("phase")
    return raw


def _normalise_plan(
    returned: list, state: AgendaState, window: list[dict]
) -> tuple[list[dict], list[str]]:
    """Force model output onto the expected days. Returns (days, problems)."""
    problems: list[str] = []
    by_index: dict[int, object] = {}
    for item in returned:
        index = getattr(item, "day_index", None)
        if index is None and isinstance(item, dict):
            index = item.get("day_index")
        if index is not None:
            by_index[int(index)] = item

    if len(by_index) != len(returned):
        problems.append("model returned duplicate day_index values")

    days: list[dict] = []
    for slot in window:
        index = int(slot["day_index"])
        item = by_index.get(index)
        if item is None:
            problems.append(f"day {index} missing from model output; used a fallback")
            days.append(_fallback_day(state, slot))
            continue

        title = str(getattr(item, "title", "") or "").strip()
        description = str(getattr(item, "description", "") or "").strip()
        outcome = str(getattr(item, "expected_outcome", "") or "").strip()
        if not title or not description or not outcome:
            problems.append(f"day {index} had empty fields; used a fallback")
            days.append(_fallback_day(state, slot))
            continue

        effort = getattr(item, "expected_effort_minutes", None) or 60
        days.append(
            {
                "day_index": index,
                "scheduled_date": slot["scheduled_date"],
                "title": title[:300],
                "description": description,
                "expected_outcome": outcome,
                "expected_effort_minutes": max(5, min(int(effort), 720)),
                "phase": slot.get("phase") or "build",
            }
        )
    return days, problems


def _check_plan(state: AgendaState) -> list[dict]:
    """Deterministic structural validation. These are always errors."""
    issues: list[dict] = []
    plan = state.get("sub_agendas") or []
    expected = state["timeframe_days"]

    if len(plan) != expected:
        issues.append(
            {
                "severity": "error",
                "code": "DAY_COUNT",
                "day_index": None,
                "message": f"Expected {expected} days but the plan has {len(plan)}.",
            }
        )
        return issues

    start = _parse(state["start_date"])
    seen_titles: dict[str, int] = {}
    seen_indexes: set[int] = set()

    for position, day in enumerate(plan, start=1):
        index = day["day_index"]
        if index in seen_indexes:
            issues.append(
                {
                    "severity": "error",
                    "code": "DUPLICATE_DAY",
                    "day_index": index,
                    "message": f"day_index {index} appears more than once.",
                }
            )
        seen_indexes.add(index)

        if index != position:
            issues.append(
                {
                    "severity": "error",
                    "code": "DAY_ORDER",
                    "day_index": index,
                    "message": f"Expected day_index {position}, found {index}.",
                }
            )

        expected_date = (start + timedelta(days=position - 1)).isoformat()
        if day["scheduled_date"] != expected_date:
            issues.append(
                {
                    "severity": "error",
                    "code": "DATE_DRIFT",
                    "day_index": index,
                    "message": f"Expected {expected_date}, found {day['scheduled_date']}.",
                }
            )

        key = day["title"].strip().lower()
        if key in seen_titles:
            issues.append(
                {
                    "severity": "warning",
                    "code": "DUPLICATE_TITLE",
                    "day_index": index,
                    "message": f"Title repeats day {seen_titles[key]}.",
                }
            )
        seen_titles[key] = index

        if day["expected_effort_minutes"] > 300:
            issues.append(
                {
                    "severity": "warning",
                    "code": "OVERLOADED_DAY",
                    "day_index": index,
                    "message": f"Day asks for {day['expected_effort_minutes']} minutes.",
                }
            )

    final = plan[-1]
    agenda_words = {word for word in state["title"].lower().split() if len(word) > 3}
    outcome_words = set(final["expected_outcome"].lower().split())
    if agenda_words and not (agenda_words & outcome_words):
        issues.append(
            {
                "severity": "warning",
                "code": "WEAK_FINALE",
                "day_index": final["day_index"],
                "message": "The final day's outcome does not restate the agenda's success condition.",
            }
        )
    return issues


# ----------------------------------------------------------------------- nodes


async def intake_validate(state: AgendaState) -> dict:
    timeframe = int(state["timeframe_days"])
    if not settings.min_timeframe_days <= timeframe <= settings.max_timeframe_days:
        return {
            "phase": "failed",
            "error": (
                f"Timeframe must be between {settings.min_timeframe_days} and "
                f"{settings.max_timeframe_days} days."
            ),
            "sub_agendas": [],
            "todos": [],
        }

    if state.get("clarifying_answers"):
        # Already clarified; skip the second triage call.
        return {"agenda_type": state.get("agenda_type") or "other", "clarifying_questions": []}

    result = await structured_call(
        IntakeOutput,
        intake_v1.build(
            title=state["title"],
            description=state["description"],
            timeframe_days=timeframe,
        ),
        node="intake_validate",
        context={"title": state["title"], "description": state["description"]},
    )
    intake: IntakeOutput = result.parsed  # type: ignore[assignment]

    questions: list[str] = []
    if not intake.is_specific:
        questions = [question.strip() for question in intake.clarifying_questions if question.strip()][:3]
        if not questions:
            questions = [
                "What does success look like in measurable terms?",
                "What is the single output you want to have at the end?",
            ]

    return {
        "agenda_type": intake.agenda_type or "other",
        "clarifying_questions": questions,
        "tokens_in": state.get("tokens_in", 0) + result.tokens_in,
        "tokens_out": state.get("tokens_out", 0) + result.tokens_out,
    }


async def ask_clarifications(state: AgendaState) -> dict:
    """Pause the graph and hand the questions to the UI."""
    answers = interrupt(
        {
            "kind": "clarifications",
            "questions": state.get("clarifying_questions") or [],
            "message": "A few answers will make this plan much sharper.",
        }
    )
    if isinstance(answers, dict):
        answers = answers.get("answers", answers)
    return {"clarifying_answers": {str(k): str(v) for k, v in dict(answers).items()}}


async def build_skeleton(state: AgendaState) -> dict:
    start = _parse(state["start_date"])
    total = int(state["timeframe_days"])
    skeleton = [
        {
            "day_index": index,
            "scheduled_date": (start + timedelta(days=index - 1)).isoformat(),
            "phase": phase_for(index, total),
        }
        for index in range(1, total + 1)
    ]
    return {
        "skeleton": skeleton,
        "end_date": skeleton[-1]["scheduled_date"],
        "repair_passes": 0,
        "prompt_version": PROMPT_SET_VERSION,
    }


async def plan(state: AgendaState) -> dict:
    skeleton = state["skeleton"]
    total = len(skeleton)
    chunked = total > settings.plan_chunk_threshold_days
    size = settings.plan_chunk_days if chunked else total

    clarifications = None
    if state.get("clarifying_answers"):
        clarifications = "\n".join(
            f"- {question}: {answer}"
            for question, answer in state["clarifying_answers"].items()
        )

    days: list[dict] = []
    problems: list[str] = []
    outcomes: list[str] = []
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)
    model = state.get("model", "")

    for offset in range(0, total, size):
        window = _slots(state, offset=offset, size=size)
        is_final_window = window[-1]["day_index"] == total

        result = await structured_call(
            PlanOutput,
            plan_v1.build(
                title=state["title"],
                description=state["description"],
                timeframe_days=total,
                agenda_type=state.get("agenda_type") or "other",
                window=window,
                previous_outcomes=outcomes[-7:],
                is_final_window=is_final_window,
                is_final_day_visible=is_final_window,
                clarifications=clarifications,
                instructions=state.get("instructions"),
            ),
            node="plan",
            temperature=0.5,
            context={
                "title": state["title"],
                "timeframe_days": total,
                "days": window,
            },
        )
        output: PlanOutput = result.parsed  # type: ignore[assignment]
        normalised, issues = _normalise_plan(output.sub_agendas, state, window)
        days.extend(normalised)
        problems.extend(issues)
        outcomes.extend(day["expected_outcome"] for day in normalised)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        model = result.model or model

    return {
        "sub_agendas": days,
        "issues": problems and [
            {
                "severity": "warning",
                "code": "NORMALISED",
                "day_index": None,
                "message": problem,
            }
            for problem in problems
        ] or [],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "phase": "planning",
    }


async def critique(state: AgendaState) -> dict:
    structural = _check_plan(state)
    plan_days = state.get("sub_agendas") or []

    issues: list[dict] = list(structural)
    reaches_goal = True
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)

    if plan_days:
        result = await structured_call(
            CritiqueOutput,
            critique_v1.build(
                title=state["title"],
                description=state["description"],
                timeframe_days=int(state["timeframe_days"]),
                plan=plan_days,
            ),
            node="critique",
            temperature=0.2,
            context={},
        )
        review: CritiqueOutput = result.parsed  # type: ignore[assignment]
        reaches_goal = review.reaches_goal_on_final_day
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out

        existing = {(issue.get("code"), issue.get("day_index")) for issue in issues}
        for issue in review.issues[:6]:
            if (issue.code, issue.day_index) in existing:
                continue
            issues.append(issue.model_dump())

        if not reaches_goal:
            issues.append(
                {
                    "severity": "error",
                    "code": "GOAL_NOT_REACHED",
                    "day_index": plan_days[-1]["day_index"],
                    "message": "The plan does not deliver the agenda's success condition on the final day.",
                }
            )

    return {
        "issues": issues,
        "reaches_goal_on_final_day": reaches_goal,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "phase": "critique",
    }


async def repair(state: AgendaState) -> dict:
    """Ask the model to fix the specific problems the critic found."""
    error_issues = [issue for issue in state.get("issues", []) if issue.get("severity") == "error"]
    if not error_issues:
        return {"repair_passes": state.get("repair_passes", 0) + 1}

    notes = "\n".join(
        f"- day {issue.get('day_index') or 'plan'}: {issue['message']}"
        + (f" (fix: {issue['fix']})" if issue.get("fix") else "")
        for issue in error_issues[:8]
    )
    existing = {day["day_index"]: day for day in (state.get("sub_agendas") or [])}
    skeleton = state["skeleton"]
    total = len(skeleton)
    size = settings.plan_chunk_days if total > settings.plan_chunk_threshold_days else total

    days: list[dict] = []
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)

    for offset in range(0, total, size):
        sub_window = [dict(slot) for slot in skeleton[offset : offset + size]]
        is_final_window = sub_window[-1]["day_index"] == total
        current = [existing.get(slot["day_index"]) for slot in sub_window]
        result = await structured_call(
            PlanOutput,
            plan_v1.build(
                title=state["title"],
                description=state["description"],
                timeframe_days=total,
                agenda_type=state.get("agenda_type") or "other",
                window=sub_window,
                is_final_window=is_final_window,
                is_final_day_visible=is_final_window,
                instructions=(
                    "A reviewer found these problems. Fix exactly these, keep everything "
                    f"else that already works:\n{notes}"
                ),
            ),
            node="repair",
            temperature=0.4,
            context={
                "title": state["title"],
                "timeframe_days": total,
                "days": sub_window,
                "existing": current,
            },
        )
        output: PlanOutput = result.parsed  # type: ignore[assignment]
        normalised, _ = _normalise_plan(output.sub_agendas, state, sub_window)
        days.extend(normalised)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out

    return {
        "sub_agendas": days,
        "repair_passes": state.get("repair_passes", 0) + 1,
        "issues": [],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "phase": "repair",
    }


async def expand_todos(state: AgendaState) -> dict:
    """Expand the first few days so the user can review real to-dos immediately.

    ``state["todos"]`` is always a flat list of
    ``{day_index, position, title, notes}``, so re-running this after a
    regeneration only rebuilds the days that actually need it.
    """
    plan_days = state.get("sub_agendas") or []
    if not plan_days:
        return {"todos": []}

    limit = max(1, min(settings.preexpand_days, len(plan_days)))
    regenerated = {int(day) for day in (state.get("regenerated_days") or [])}

    by_day: dict[int, list[dict]] = {}
    for entry in state.get("todos") or []:
        by_day.setdefault(int(entry["day_index"]), []).append(entry)

    todos: list[dict] = []
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)

    for day in plan_days:
        index = int(day["day_index"])
        needs_expansion = index <= limit or index in regenerated

        if not needs_expansion:
            # Keep whatever already exists; days beyond the window are expanded
            # lazily by the daily materialiser.
            todos.extend(by_day.get(index, []))
            continue

        produced, result = await expand_day_todos(
            agenda_title=state["title"],
            day=day,
            day_index=index,
            timeframe_days=int(state["timeframe_days"]),
        )
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        for position, item in enumerate(produced):
            todos.append(
                {
                    "day_index": index,
                    "position": position,
                    "title": item["title"],
                    "notes": item.get("notes"),
                }
            )

    return {
        "todos": todos,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "phase": "todos",
    }


async def expand_day_todos(
    *,
    agenda_title: str,
    day: dict,
    day_index: int,
    timeframe_days: int,
    previous_context: str | None = None,
):
    """Expand one day into checkable to-dos. Also used by the daily materialiser."""
    result = await structured_call(
        TodoListOutput,
        todos_v1.build(
            agenda_title=agenda_title,
            day_title=day["title"],
            day_description=day.get("description") or "",
            expected_outcome=day.get("expected_outcome") or "",
            day_index=day_index,
            timeframe_days=timeframe_days,
            previous_context=previous_context,
            todo_min=settings.todos_per_day_min,
            todo_max=settings.todos_per_day_max,
        ),
        node="expand_todos",
        temperature=0.4,
        context={"day": {**day, "day_index": day_index}},
    )
    output: TodoListOutput = result.parsed  # type: ignore[assignment]
    items = _normalise_todos(output.todos)
    return items, result


def _normalise_todos(items: list[TodoDraft]) -> list[dict]:
    minimum = settings.todos_per_day_min
    maximum = settings.todos_per_day_max
    seen: set[str] = set()
    clean: list[dict] = []

    for item in items:
        title = " ".join(str(item.title).split()).strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append({"title": title[:300], "notes": item.notes})

    if len(clean) < minimum:
        filler = fake._todos_for(  # noqa: SLF001
            clean[0]["title"] if clean else "today", ""
        )
        for candidate in filler:
            if len(clean) >= minimum:
                break
            if candidate["title"].lower() in seen:
                continue
            seen.add(candidate["title"].lower())
            clean.append(candidate)

    return clean[:maximum]


async def persist_draft(state: AgendaState) -> dict:
    """Normalise ordering. Actual storage is done by the runner."""
    todos = sorted(
        (dict(entry) for entry in (state.get("todos") or [])),
        key=lambda entry: (int(entry["day_index"]), int(entry.get("position", 0))),
    )
    for day_index in {int(entry["day_index"]) for entry in todos}:
        position = 0
        for entry in todos:
            if int(entry["day_index"]) == day_index:
                entry["position"] = position
                position += 1

    return {
        "todos": todos,
        "sub_agendas": state.get("sub_agendas") or [],
        "phase": "review",
    }


async def await_review(state: AgendaState) -> dict:
    """Pause and hand the whole draft to the human for edit/approve."""
    decision = interrupt(
        {
            "kind": "review",
            "status": "needs_review",
            "days": len(state.get("sub_agendas") or []),
            "todos": len(state.get("todos") or []),
            "issues": state.get("issues") or [],
            "message": "Review the plan. Edit any day, then approve to start.",
        }
    )
    payload = decision if isinstance(decision, dict) else {}
    action = str(payload.get("decision") or "approve")

    if action == "regenerate_all":
        return {
            "user_decision": action,
            "instructions": payload.get("instructions"),
            "repair_passes": 0,
            "todos": [],
        }
    if action == "regenerate_day":
        target = payload.get("day_index")
        return {
            "user_decision": action,
            "target_day": int(target) if target else None,
            "instructions": payload.get("instructions"),
            "regenerated_days": [int(target)] if target else [],
            "issues": [],
            "todos": [
                entry
                for entry in (state.get("todos") or [])
                if int(entry["day_index"]) != int(target or -1)
            ],
        }
    if action == "edit":
        return {"user_decision": action, "instructions": payload.get("instructions")}
    return {"user_decision": "approve"}


async def apply_edits(state: AgendaState) -> dict:
    """Re-plan a single day, or fold in notes, then re-validate."""
    decision = state.get("user_decision")
    plan_days = list(state.get("sub_agendas") or [])

    if decision == "regenerate_day":
        target = int(state.get("target_day") or 1)
        day = next((item for item in plan_days if item["day_index"] == target), None)
        if day is None:
            return {"phase": "planning"}

        result = await structured_call(
            DayRegenerationOutput,
            plan_v1.build(
                title=state["title"],
                description=state["description"],
                timeframe_days=int(state["timeframe_days"]),
                agenda_type=state.get("agenda_type") or "other",
                window=[
                    {
                        "day_index": day["day_index"],
                        "scheduled_date": day["scheduled_date"],
                        "phase": day.get("phase"),
                    }
                ],
                is_final_window=target == int(state["timeframe_days"]),
                is_final_day_visible=target == int(state["timeframe_days"]),
                instructions=(
                    "Rewrite ONLY this single day. Keep it consistent with the days around it. "
                    + (state.get("instructions") or "")
                ),
            ),
            node="regenerate_day",
            temperature=0.6,
            context={
                "title": state["title"],
                "timeframe_days": int(state["timeframe_days"]),
                "day_index": target,
                "day": day,
            },
        )
        output: DayRegenerationOutput = result.parsed  # type: ignore[assignment]
        replacement = {
            "day_index": target,
            "scheduled_date": day["scheduled_date"],
            "title": output.sub_agenda.title[:300],
            "description": output.sub_agenda.description,
            "expected_outcome": output.sub_agenda.expected_outcome,
            "expected_effort_minutes": max(
                5, min(int(output.sub_agenda.expected_effort_minutes or 60), 720)
            ),
            "phase": day.get("phase"),
        }
        plan_days = [replacement if item["day_index"] == target else item for item in plan_days]
        return {
            "sub_agendas": plan_days,
            "tokens_in": state.get("tokens_in", 0) + result.tokens_in,
            "tokens_out": state.get("tokens_out", 0) + result.tokens_out,
            "regenerated_days": [target],
        }

    return {"sub_agendas": plan_days}


async def finalize(state: AgendaState) -> dict:
    return {"phase": "done", "approved": True}


# ---------------------------------------------------------------- motivation


async def motivation_line(
    *,
    full_name: str | None,
    agenda_title: str,
    day_title: str,
    day_index: int,
    timeframe_days: int,
    streak: int,
    done_so_far: int,
    total_days: int,
) -> str:
    """One LLM call per user per day, as decided in the product review."""
    if not settings.motivation_enabled:
        return ""

    try:
        result = await structured_call(
            MotivationOutput,
            motivation_v1.build(
                full_name=full_name,
                agenda_title=agenda_title,
                day_title=day_title,
                day_index=day_index,
                timeframe_days=timeframe_days,
                streak=streak,
                done_so_far=done_so_far,
                total_days=total_days,
            ),
            node="motivation",
            temperature=0.7,
            context={
                "full_name": full_name,
                "day_index": day_index,
                "timeframe_days": timeframe_days,
                "streak": streak,
            },
        )
        output: MotivationOutput = result.parsed  # type: ignore[assignment]
        return " ".join(output.message.split())[:280]
    except Exception as exc:  # noqa: BLE001 - motivation is decorative, never fatal
        logger.warning("motivation line unavailable: %s", exc)
        return ""
