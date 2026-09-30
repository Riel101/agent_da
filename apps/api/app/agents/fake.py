"""Deterministic offline planner.

Used when ``NVIDIA_API_KEY`` is unset (local development, CI, demos). It cannot
tailor a plan to the goal the way the real model does, but it produces a
well-formed, date-anchored plan so every downstream behaviour — review, edits,
reminders, points, streaks — is fully exercisable without credentials.
"""

from __future__ import annotations

from typing import Any

from app.agents import schemas

_TYPE_KEYWORDS = {
    "fitness": ("run", "gym", "fit", "weight", "marathon", "muscle", "yoga"),
    "learning": ("learn", "study", "course", "language", "read", "exam", "certif"),
    "writing": ("write", "book", "novel", "blog", "essay", "thesis"),
    "shipping": ("ship", "launch", "build", "app", "mvp", "saas", "website"),
    "business": ("revenue", "customer", "sales", "startup", "business", "client"),
}


def _guess_type(text: str) -> str:
    lowered = text.lower()
    for agenda_type, keywords in _TYPE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return agenda_type
    return "other"


def build_response(schema: type, messages: list, context: dict[str, Any]) -> dict:
    if schema is schemas.IntakeOutput:
        return _intake(context)
    if schema is schemas.PlanOutput:
        return _plan(context)
    if schema is schemas.CritiqueOutput:
        return {"issues": [], "reaches_goal_on_final_day": True}
    if schema is schemas.TodoListOutput:
        return _todos(context)
    if schema is schemas.MotivationOutput:
        return _motivation(context)
    if schema is schemas.DayRegenerationOutput:
        day = _plan_day(context)
        return {"sub_agenda": day, "todos": _todos_for(day["title"], day["expected_outcome"])}
    return {}


def _intake(context: dict[str, Any]) -> dict:
    """Mirror the real triage closely enough for offline runs.

    A description is treated as specific when it is long enough to imply a
    verifiable outcome. Short aspirations ("Improve myself") are not.
    """
    description = str(context.get("description") or "").strip()
    title = str(context.get("title") or "").strip()
    is_specific = len(description) >= 30
    if not is_specific:
        questions = [
            "What measurable result do you want at the end of the timeframe?",
            "What will you be able to show someone that proves it is done?",
        ]
    else:
        questions = []
    return {
        "is_specific": is_specific,
        "clarifying_questions": questions,
        "agenda_type": _guess_type(f"{title} {description}"),
    }


def _plan(context: dict[str, Any]) -> dict:
    days = context.get("days") or []
    return {"sub_agendas": [_plan_day({**context, "day": day}) for day in days]}


def _plan_day(context: dict[str, Any]) -> dict:
    day = context.get("day") or {}
    index = int(day.get("day_index", context.get("day_index", 1)))
    total = int(context.get("timeframe_days", day.get("total", index)) or index)
    phase = day.get("phase") or "build"
    goal = (context.get("title") or "the goal").strip()
    is_final = index >= total

    if is_final:
        title = f"Final day: deliver {goal}"
        description = (
            f"Complete the last outstanding piece and confirm {goal} is achieved. "
            "Review the whole run, close the loops and record the result."
        )
        outcome = f"{goal} is achieved on day {index} of {total}."
        effort = 120
    elif index == 1:
        title = f"Start with the smallest step toward {goal}"
        description = (
            f"Set up the baseline for {goal}: decide the one metric that matters, "
            "gather what you already have, and take the first concrete action."
        )
        outcome = "A baseline and a first concrete output exist."
        effort = 45
    else:
        title = f"{phase.capitalize()} {index}/{total}: build on yesterday"
        description = (
            f"Extend yesterday's outcome toward {goal}. Produce one visible artefact "
            f"and remove one blocker."
        )
        outcome = f"Artefact for step {index} exists and the next step is unblocked."
        effort = min(60 + index * 3, 180)

    return {
        "day_index": index,
        "title": title[:100],
        "description": description,
        "expected_outcome": outcome,
        "expected_effort_minutes": effort,
        "phase": phase,
    }


def _todos(context: dict[str, Any]) -> dict:
    day = context.get("day") or {}
    return {
        "todos": _todos_for(
            day.get("title", "Today's focus"), day.get("expected_outcome", "")
        )
    }


def _todos_for(title: str, outcome: str) -> list[dict]:
    focus = title[:60]
    return [
        {"title": f"Plan: write down what '{focus}' requires", "notes": "Three bullets is enough."},
        {"title": "Do the main working block", "notes": outcome or None},
        {"title": "Remove one blocker in the way", "notes": None},
        {"title": "Review the result and note what changed", "notes": None},
    ]


def _motivation(context: dict[str, Any]) -> dict:
    name = context.get("full_name") or "there"
    streak = context.get("streak", 0)
    day_index = context.get("day_index")
    total = context.get("timeframe_days")
    progress = f"Day {day_index} of {total}" if day_index and total else "Today"
    if streak and int(streak) > 1:
        streak_line = f"You are {streak} days deep — keep the chain unbroken."
    else:
        streak_line = "Starting is the hardest part, and you have already done it."
    return {"message": f"{progress}, {name}. {streak_line}"}
