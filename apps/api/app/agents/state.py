"""Graph state.

Everything is a plain JSON-serialisable value so the Postgres checkpointer can
persist a paused run and resume it after a deploy.
"""

from __future__ import annotations

from typing import TypedDict


class DaySlot(TypedDict):
    day_index: int
    scheduled_date: str  # ISO date
    phase: str


class AgendaState(TypedDict, total=False):
    # ---------------------------------------------------------------- identity
    user_id: str
    agenda_id: str
    draft_id: str

    # ------------------------------------------------------------------- input
    title: str
    description: str
    timeframe_days: int
    start_date: str  # ISO date
    end_date: str
    timezone: str
    full_name: str
    streak: int
    agenda_type: str

    # ---------------------------------------------------- human-in-the-loop
    clarifying_questions: list[str]
    clarifying_answers: dict[str, str]

    # -------------------------------------------------------------- planning
    #: Deterministic, dated skeleton the planner must fill exactly.
    skeleton: list[DaySlot]
    #: Normalised day-by-day plan.
    sub_agendas: list[dict]
    #: Flat list of to-dos, each carrying its day_index.
    todos: list[dict]

    # --------------------------------------------------------------- critique
    issues: list[dict]
    repair_passes: int
    reaches_goal_on_final_day: bool

    # ---------------------------------------------------------------- control
    phase: str
    user_decision: str | None
    target_day: int | None
    instructions: str | None
    regenerated_days: list[int]
    error: str | None
    approved: bool

    # ------------------------------------------------------------ accounting
    tokens_in: int
    tokens_out: int
    model: str
    prompt_version: str
