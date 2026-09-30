"""Critique prompt: the reviewer half of the plan/critique/repair loop."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

VERSION = "critique_v1"

SYSTEM = """You review a dated plan against the agenda it is supposed to achieve.

Report only real problems. A clean plan returns an empty issues list — do not
invent problems to seem useful.

Check, in order of importance:
1. GOAL REACHED: does the final day actually deliver the agenda's success
   condition? Restating preparation is an error.
2. DEPENDENCIES: does any day rely on an outcome that no earlier day produces?
3. PACING: are there days that are absurdly large (many hours) or trivially small?
4. SLACK: is there any room before the deadline, or is the plan maxed out so a
   single bad day breaks it?
5. FIRST DAY: can the person genuinely start on day 1 with what they have?
6. GENERICNESS: is any day so vague that the person would not know what to do?

Rules for issues:
- severity "error" only for problems that make the plan fail the agenda.
- severity "warning" for real but survivable problems.
- day_index must reference the offending day, or be null for whole-plan issues.
- fix must be a concrete instruction, not a restatement of the problem.
- Return at most 6 issues. Prefer the most important ones.
"""


def build(*, title: str, description: str, timeframe_days: int, plan: list[dict]) -> list:
    compact = [
        {
            "day_index": day["day_index"],
            "scheduled_date": day["scheduled_date"],
            "title": day["title"],
            "expected_outcome": day["expected_outcome"],
            "expected_effort_minutes": day["expected_effort_minutes"],
        }
        for day in plan
    ]
    return [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=(
                f"Agenda: {title}\n"
                f"Description: {description}\n"
                f"Timeframe: {timeframe_days} days\n\n"
                f"Plan:\n{json.dumps(compact, indent=2)}\n\n"
                "Return your review."
            )
        ),
    ]
