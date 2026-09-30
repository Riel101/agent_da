"""Daily motivation line.

Runs once per user per day (a product decision), so it can afford to be specific
to the person's actual day rather than a generic quote.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

VERSION = "motivation_v1"

SYSTEM = """You write the opening line of a daily goal reminder.

Rules:
- Two sentences maximum. Under 220 characters total.
- Be specific to what the person is doing today. Never generic hype.
- Never use exclamation marks, never say "You got this", "crush it", "let's go",
  "journey", "grind" or "hustle".
- Reference the streak only when it is 2 or more, and only as a fact.
- Sound like a calm coach who knows the plan, not a motivational poster.
- Plain text. No markdown, no emoji unless the streak is 7 or more.
"""


def build(
    *,
    full_name: str | None,
    agenda_title: str,
    day_title: str,
    day_index: int,
    timeframe_days: int,
    streak: int,
    done_so_far: int,
    total_days: int,
) -> list:
    who = full_name or "the user"
    return [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=(
                f"Person: {who}\n"
                f"Agenda: {agenda_title}\n"
                f"Today is day {day_index} of {timeframe_days}.\n"
                f"Today's focus: {day_title}\n"
                f"Days fully completed so far: {done_so_far} of {total_days}\n"
                f"Current streak: {streak}\n\n"
                "Write the opening line."
            )
        ),
    ]
