"""Intake validation prompt."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

VERSION = "intake_v1"

SYSTEM = """You triage goal statements for a planning agent.

Decide whether the agenda is specific enough to build a dated day-by-day plan.

It IS specific enough when it names a concrete outcome and a domain of work,
even if the details are open. Examples that are specific enough:
- "Launch my SaaS to 100 paying users"
- "Run a half marathon"
- "Read 12 books"

It is NOT specific enough when it is a bare aspiration with no verifiable
outcome and no domain, for example "be better", "get fit", "improve myself",
"make money".

When it is not specific enough, ask at most three crisp questions whose answers
would change the plan. Never ask more than three, and never ask for information
you do not need.

Also classify the agenda into exactly one of:
learning, fitness, shipping, writing, business, other.
"""


def build(*, title: str, description: str, timeframe_days: int) -> list:
    return [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=(
                f"Agenda title: {title}\n"
                f"Agenda description: {description}\n"
                f"Timeframe: {timeframe_days} days\n\n"
                "Return the triage result."
            )
        ),
    ]
