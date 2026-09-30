"""To-do expansion prompt."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

VERSION = "todos_v1"

SYSTEM = """You break one day of a plan into the concrete actions that complete it.

Rules:
- Produce between 3 and 6 items. Fewer only if the day genuinely needs fewer.
- Each item is imperative, starts with a verb, and is at most 80 characters.
- Each item must be finishable in one sitting. Split anything bigger.
- No duplicates, and no item that merely restates the day's title.
- Order them the way the person should actually do them.
- notes is optional; use it only to add a definition of done or a pointer.
- Never include "tick off", "mark complete", "reflect on" or similar filler.
"""


def build(
    *,
    agenda_title: str,
    day_title: str,
    day_description: str,
    expected_outcome: str,
    day_index: int,
    timeframe_days: int,
    previous_context: str | None = None,
    todo_min: int = 3,
    todo_max: int = 6,
) -> list:
    body = [
        f"Agenda: {agenda_title}",
        f"This is day {day_index} of {timeframe_days}.",
        f"Day title: {day_title}",
        f"Day description: {day_description}",
        f"Expected outcome by end of day: {expected_outcome}",
    ]
    if previous_context:
        body.append(f"Context on how the previous day actually went: {previous_context}")
    body.append(f"Return between {todo_min} and {todo_max} to-dos.")
    return [SystemMessage(content=SYSTEM), HumanMessage(content="\n\n".join(body))]
