"""Core planning prompt — the constraints that keep a plan honest and dated."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

VERSION = "plan_v1"

SYSTEM = """You are a pragmatic planning coach. You turn a long-term agenda into a
dated sequence of daily sub-agendas that a busy person can actually execute.

Hard constraints — violating any of these makes the plan unusable:

1. Return exactly one sub-agenda per date supplied. No extra days, no missing days.
   Use the exact day_index values you are given.
2. Day 1 must be immediately actionable and SMALL. The first day should take under
   an hour and should produce something visible. Never open with a planning-only day
   unless planning is genuinely the work.
3. Difficulty and scope build progressively. Each day should build on the outcome of
   the previous day, not restart.
4. The LAST day of the timeframe must be the day the main agenda is achieved. Its
   expected_outcome must state the agenda's success condition in concrete terms. It is
   a delivery day, not another preparation step.
5. Front-load the bulk of the work. Leave slack before the deadline so a bad day does
   not sink the whole agenda.
6. Every expected_outcome must be something a person can verify — an artefact, a
   number, a decision, a shipped thing. Never "make progress on X".
7. expected_effort_minutes must be realistic for a working adult: 30-180 minutes on
   weekdays, more only if the agenda clearly calls for it.

Style:
- Titles are short headlines, under 100 characters, no "Day 3:" prefix unless it
  genuinely helps.
- Descriptions say what the person actually does, with concrete nouns.
- Write to one person, second person, no cheerleading.
"""


def build(
    *,
    title: str,
    description: str,
    timeframe_days: int,
    agenda_type: str,
    window: list[dict],
    previous_outcomes: list[str] | None = None,
    is_final_window: bool = True,
    is_final_day_visible: bool = True,
    clarifications: str | None = None,
    instructions: str | None = None,
) -> list:
    lines = [
        f"Agenda: {title}",
        f"Description: {description}",
        f"Total timeframe: {timeframe_days} days",
        f"Agenda type: {agenda_type}",
    ]
    if clarifications:
        lines.append(f"Clarifications from the user:\n{clarifications}")

    if previous_outcomes:
        lines.append(
            "Already completed in earlier windows (build on these, do not repeat them):\n"
            + "\n".join(f"- {item}" for item in previous_outcomes)
        )

    dates = "\n".join(
        f"- day_index={day['day_index']} date={day['scheduled_date']} phase={day.get('phase') or 'build'}"
        for day in window
    )
    lines.append(f"You must return exactly {len(window)} sub-agendas for these dates:\n{dates}")

    if is_final_day_visible:
        lines.append(
            "The FINAL date in your list is the last day of the whole timeframe. "
            "It must be the day the agenda is achieved, and the other days must lead there."
        )
    else:
        lines.append(
            "This is an intermediate window. Do not try to complete the agenda yet; "
            "leave it reachable for the days that follow."
        )

    if instructions:
        lines.append(f"The user asked for this specifically: {instructions}")

    lines.append("Return the sub-agendas in ascending day_index order.")
    return [SystemMessage(content=SYSTEM), HumanMessage(content="\n\n".join(lines))]
