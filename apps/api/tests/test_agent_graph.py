"""Graph invariants.

These run the real graph (with the deterministic offline planner) and assert the
promises the product makes: the plan is dated, it is exactly ``timeframe_days``
long, the final day delivers the agenda, and a vague goal triggers questions
instead of a guess.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agents.runner import runner

START = date(2026, 3, 1)


def base_state(days: int, **overrides) -> dict:
    state = {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "agenda_id": "00000000-0000-0000-0000-000000000002",
        "draft_id": "00000000-0000-0000-0000-000000000003",
        "title": "Launch my SaaS to 100 paying users",
        "description": "Ship the product and get the first hundred customers paying.",
        "timeframe_days": days,
        "start_date": START.isoformat(),
        "end_date": (START + timedelta(days=days - 1)).isoformat(),
        "timezone": "UTC",
        "full_name": "Ada",
        "streak": 0,
        "repair_passes": 0,
        "phase": "intake",
        "sub_agendas": [],
        "todos": [],
        "issues": [],
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [1, 3, 30, 45])
async def test_plan_is_exactly_dated_and_ends_on_the_goal(days):
    outcome = await runner.start(f"thread-{days}", base_state(days))

    assert outcome.interrupted, "the graph should pause for human review"
    assert outcome.kind == "review"

    plan = outcome.state["sub_agendas"]
    assert len(plan) == days, "the plan must have exactly one day per day of the timeframe"

    for position, day in enumerate(plan, start=1):
        assert day["day_index"] == position
        assert day["scheduled_date"] == (START + timedelta(days=position - 1)).isoformat()
        assert day["title"]
        assert day["description"]
        assert day["expected_outcome"]

    final = plan[-1]
    assert final["scheduled_date"] == (START + timedelta(days=days - 1)).isoformat()
    assert "saas" in final["expected_outcome"].lower()


@pytest.mark.asyncio
async def test_long_timeframe_is_chunked_without_losing_days():
    outcome = await runner.start("thread-long", base_state(60))
    plan = outcome.state["sub_agendas"]
    assert len(plan) == 60
    assert [day["day_index"] for day in plan] == list(range(1, 61))


@pytest.mark.asyncio
async def test_first_days_are_expanded_into_todos():
    outcome = await runner.start("thread-todos", base_state(30))
    todos = outcome.state["todos"]

    expanded_days = sorted({int(entry["day_index"]) for entry in todos})
    assert expanded_days == [1, 2, 3], "only the preview window is expanded up front"

    for entry in todos:
        assert entry["title"]
        assert entry["position"] >= 0

    per_day: dict[int, int] = {}
    for entry in todos:
        per_day[int(entry["day_index"])] = per_day.get(int(entry["day_index"]), 0) + 1
    assert all(3 <= count <= 6 for count in per_day.values())


@pytest.mark.asyncio
async def test_short_timeframe_expands_every_day():
    outcome = await runner.start("thread-short", base_state(2))
    expanded = {int(entry["day_index"]) for entry in outcome.state["todos"]}
    assert expanded == {1, 2}


@pytest.mark.asyncio
async def test_vague_agenda_asks_questions_instead_of_guessing():
    state = base_state(
        14,
        title="Be better",
        description="Improve myself",
    )
    outcome = await runner.start("thread-vague", state)

    assert outcome.interrupted
    assert outcome.kind == "clarifications"
    questions = outcome.payload["questions"]
    assert 1 <= len(questions) <= 3


@pytest.mark.asyncio
async def test_answers_resume_the_graph_into_a_plan():
    state = base_state(14, title="Be better", description="Improve myself")
    first = await runner.start("thread-vague-2", state)
    assert first.kind == "clarifications"

    resumed = await runner.resume(
        "thread-vague-2",
        {"answers": {question: "Become a certified scuba diver" for question in first.payload["questions"]}},
    )
    assert resumed.kind == "review"
    assert len(resumed.state["sub_agendas"]) == 14


@pytest.mark.asyncio
async def test_timeframe_beyond_the_cap_fails_cleanly():
    outcome = await runner.start("thread-too-long", base_state(400))
    assert outcome.failed
    assert "Timeframe" in (outcome.error or "")


@pytest.mark.asyncio
async def test_regenerating_one_day_keeps_the_plan_shape():
    state = base_state(10)
    first = await runner.start("thread-regen", state)
    original = first.state["sub_agendas"]

    resumed = await runner.resume(
        "thread-regen",
        {"decision": "regenerate_day", "day_index": 4, "instructions": "make it smaller"},
    )
    assert resumed.kind == "review"

    revised = resumed.state["sub_agendas"]
    assert len(revised) == 10
    assert [day["scheduled_date"] for day in revised] == [
        day["scheduled_date"] for day in original
    ]
    # Every other day is untouched.
    for before, after in zip(original, revised):
        if before["day_index"] != 4:
            assert before == after


@pytest.mark.asyncio
async def test_approval_ends_the_graph():
    await runner.start("thread-approve", base_state(5))
    final = await runner.resume("thread-approve", {"decision": "approve"})

    assert not final.interrupted
    assert final.state["approved"] is True
    assert final.state["phase"] == "done"
