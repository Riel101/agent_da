"""End-to-end: create an agenda, generate a plan, approve it, work the day,
and let the reminder go out.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.core.timezones import local_today
from app.services.plan_service import run_generation_now


async def _create_agenda(client, headers, *, days: int = 3, channel: str = "email", **extra):
    today = local_today("Africa/Lagos")
    payload = {
        "title": "Launch my SaaS to 100 paying users",
        "description": "Ship the product and get the first hundred customers paying.",
        "timeframe_days": days,
        "start_date": today.isoformat(),
        "reminder_channel": channel,
        "reminder_time": "00:01",
        "timezone": "Africa/Lagos",
        **extra,
    }
    response = await client.post("/api/v1/agendas", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _generate(client, headers, agenda_id: str) -> str:
    response = await client.post(f"/api/v1/agendas/{agenda_id}/generate", headers=headers)
    assert response.status_code == 202, response.text
    draft_id = response.json()["draft_id"]
    await run_generation_now(uuid.UUID(draft_id))
    return draft_id


@pytest.mark.asyncio
async def test_full_lifecycle(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=3)

    assert agenda["status"] == "draft"
    assert agenda["end_date"] > agenda["start_date"]

    await _generate(client, headers, agenda["id"])

    draft = (await client.get(f"/api/v1/agendas/{agenda['id']}/draft", headers=headers)).json()
    assert draft["status"] == "needs_review"
    assert draft["stats"]["days"] == 3
    assert len(draft["sub_agendas"]) == 3
    assert all(day["todos"] for day in draft["sub_agendas"])

    agenda_after = (await client.get(f"/api/v1/agendas/{agenda['id']}", headers=headers)).json()
    assert agenda_after["status"] == "ready"

    approval = await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)
    assert approval.status_code == 200, approval.text
    body = approval.json()
    assert body["agenda"]["status"] == "active"
    # One reminder per day: a Sunday's row is the weekly review instead of a daily.
    assert body["scheduled_reminders"] == 3

    dashboard = (await client.get("/api/v1/dashboard", headers=headers)).json()
    assert dashboard["totals"]["points_balance"] == 0
    assert len(dashboard["today"]) == 1

    block = dashboard["today"][0]
    assert block["agenda_id"] == agenda["id"]
    assert block["total"] >= 3
    assert block["done"] == 0

    # Tick off the first to-do.
    first = block["todos"][0]
    completion = await client.post(f"/api/v1/todos/{first['id']}/complete", headers=headers)
    assert completion.status_code == 200, completion.text
    result = completion.json()
    assert result["points"]["awarded"] == 10
    assert result["points"]["balance"] == 10
    assert result["day"]["done"] == 1
    assert result["day"]["complete"] is False

    # Completing it twice must not award twice.
    again = await client.post(f"/api/v1/todos/{first['id']}/complete", headers=headers)
    assert again.json()["points"]["awarded"] == 0
    assert again.json()["points"]["balance"] == 10

    # Finish the day: the day bonus lands.
    for todo in block["todos"][1:]:
        response = await client.post(f"/api/v1/todos/{todo['id']}/complete", headers=headers)
        assert response.status_code == 200
    final = response.json()
    assert final["day"]["complete"] is True
    assert "day_complete" in final["points"]["bonuses"]
    assert final["streak"]["current"] == 1

    expected = 10 * block["total"] + 25
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["points_balance"] == expected
    assert me["current_streak"] == 1

    # Un-completing reverses the task points and the day bonus.
    undo = await client.post(f"/api/v1/todos/{first['id']}/uncomplete", headers=headers)
    assert undo.status_code == 200
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["points_balance"] == expected - 10 - 25


@pytest.mark.asyncio
async def test_draft_can_be_edited_and_regenerated(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=5)
    await _generate(client, headers, agenda["id"])

    day = (
        await client.get(f"/api/v1/agendas/{agenda['id']}/days/2", headers=headers)
    ).json()
    assert day["sub_agenda"]["day_index"] == 2

    edited = await client.patch(
        f"/api/v1/agendas/{agenda['id']}/days/2",
        headers=headers,
        json={"title": "My own plan for day two", "expected_outcome": "Something I chose"},
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "My own plan for day two"
    assert edited.json()["is_user_edited"] is True

    # Regenerating agrees with the user's edit and does not clobber it.
    response = await client.post(
        f"/api/v1/agendas/{agenda['id']}/regenerate",
        headers=headers,
        json={"scope": "all"},
    )
    assert response.status_code == 202
    await run_generation_now(uuid.UUID(response.json()["draft_id"]))

    day_again = (
        await client.get(f"/api/v1/agendas/{agenda['id']}/days/2", headers=headers)
    ).json()
    assert day_again["sub_agenda"]["title"] == "My own plan for day two"


@pytest.mark.asyncio
async def test_user_can_add_and_remove_todos(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=2)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    sub_agenda_id = block["sub_agenda_id"]
    original = block["total"]

    created = await client.post(
        f"/api/v1/sub-agendas/{sub_agenda_id}/todos",
        headers=headers,
        json={"title": "Call the accountant"},
    )
    assert created.status_code == 201, created.text
    added = created.json()
    assert added["source"] == "user"

    detail = (
        await client.get(
            f"/api/v1/agendas/{agenda['id']}/days/{block['day_index']}", headers=headers
        )
    ).json()
    assert detail["sub_agenda"]["total_count"] == original + 1

    removed = await client.delete(f"/api/v1/todos/{added['id']}", headers=headers)
    assert removed.status_code == 200

    detail = (
        await client.get(
            f"/api/v1/agendas/{agenda['id']}/days/{block['day_index']}", headers=headers
        )
    ).json()
    assert detail["sub_agenda"]["total_count"] == original


@pytest.mark.asyncio
async def test_reorder_todos(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=2)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    sub_agenda_id = block["sub_agenda_id"]
    ids = [todo["id"] for todo in block["todos"]]

    response = await client.post(
        f"/api/v1/sub-agendas/{sub_agenda_id}/todos/reorder",
        headers=headers,
        json={"order": list(reversed(ids))},
    )
    assert response.status_code == 200, response.text
    assert [todo["id"] for todo in response.json()] == list(reversed(ids))


@pytest.mark.asyncio
async def test_reminder_is_dispatched_exactly_once(client, registered, monkeypatch):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=3)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    from app.integrations.channels.base import DeliveryResult
    from app.services import reminder_service

    sent: list[str] = []

    async def deliver_for_real(channel, message):
        """Stand in for a configured provider, so the test does not depend on one."""
        sent.append(message.subject)
        return DeliveryResult.sent("test", "test-message-id")

    monkeypatch.setattr(reminder_service, "deliver", deliver_for_real)

    internal = {"X-Internal-Token": "test-internal-token"}
    first = await client.post("/api/v1/internal/dispatch", headers=internal)
    assert first.status_code == 200, first.text
    assert first.json()["sent"] >= 1
    assert len(sent) >= 1
    assert "Day" in sent[0]

    # Nothing is due the second time.
    second = await client.post("/api/v1/internal/dispatch", headers=internal)
    assert second.json()["claimed"] == 0
    assert len(sent) == len(sent)


@pytest.mark.asyncio
async def test_sunday_gets_one_message_that_carries_the_days_plan(client, registered):
    """A Sunday must not send a daily *and* a rollup.

    The wizard promises "one reminder a day". The rollup is the only reminder on
    its Sunday, and it includes that day's focus and to-dos so nothing is lost.
    """
    headers = registered["headers"]
    today = local_today("Africa/Lagos")
    # Put a Sunday inside the plan whatever weekday the suite happens to run on.
    days_ahead = (7 - today.isoweekday()) % 7
    agenda = await _create_agenda(client, headers, days=days_ahead + 2)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    from sqlalchemy import select

    from app.db.session import session_scope
    from app.models import Reminder
    from app.services import reminder_service

    sunday = today + timedelta(days=days_ahead)

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Reminder).where(
                    Reminder.agenda_id == uuid.UUID(agenda["id"]),
                    Reminder.local_date == sunday,
                )
            )
        ).scalars().all()
        assert [row.kind.value for row in rows] == ["weekly_rollup"], (
            "Sunday should carry exactly one reminder"
        )
        subject, body = await reminder_service.render_rollup(session, rows[0])

    assert "Weekly review" in subject
    assert "Today —" in body, "the rollup must carry that day's plan"
    assert "Day " in body


@pytest.mark.asyncio
async def test_rollup_retires_a_superseded_sunday_daily(client, registered):
    """A Sunday daily queued before this rule existed is retired, not delivered.

    Plans approved before the fix already have a daily on every Sunday. The
    day-close rollup step has to clean those up, or they would double up.
    """
    headers = registered["headers"]
    today = local_today("Africa/Lagos")
    days_ahead = (7 - today.isoweekday()) % 7
    agenda = await _create_agenda(client, headers, days=days_ahead + 2)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    from sqlalchemy import select

    from app.db.session import session_scope
    from app.models import Reminder, ReminderKind, ReminderStatus, SubAgenda
    from app.services import reminder_service

    sunday = today + timedelta(days=days_ahead)
    agenda_id = uuid.UUID(agenda["id"])

    async with session_scope() as session:
        rollup = (
            await session.execute(
                select(Reminder).where(
                    Reminder.agenda_id == agenda_id,
                    Reminder.local_date == sunday,
                    Reminder.kind == ReminderKind.WEEKLY_ROLLUP,
                )
            )
        ).scalars().first()
        sub = (
            await session.execute(
                select(SubAgenda).where(
                    SubAgenda.agenda_id == agenda_id,
                    SubAgenda.scheduled_date == sunday,
                )
            )
        ).scalars().first()
        # Recreate the legacy row: a pending daily on the same Sunday.
        session.add(
            Reminder(
                user_id=rollup.user_id,
                agenda_id=agenda_id,
                sub_agenda_id=sub.id,
                kind=ReminderKind.DAILY,
                channel=rollup.channel,
                status=ReminderStatus.PENDING,
                scheduled_for=rollup.scheduled_for,
                local_date=sunday,
                dedupe_key=Reminder.build_dedupe_key(
                    agenda_id, sub.id, ReminderKind.DAILY, sunday
                ),
            )
        )

    # What the day-close job does every 30 minutes.
    async with session_scope() as session:
        await reminder_service.schedule_weekly_rollups(session)

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Reminder).where(
                    Reminder.agenda_id == agenda_id, Reminder.local_date == sunday
                )
            )
        ).scalars().all()

    assert [row.kind for row in rows] == [ReminderKind.WEEKLY_ROLLUP]


@pytest.mark.asyncio
async def test_unconfigured_channel_skips_instead_of_claiming_sent(client, registered):
    """No SMTP means logged-and-dropped — and the log must say so.

    This is the regression guard for the bug where the console sink reported a
    successful delivery, so the reminder outbox read ``sent`` for messages that
    nobody ever received.
    """
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=3)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    internal = {"X-Internal-Token": "test-internal-token"}
    response = await client.post("/api/v1/internal/dispatch", headers=internal)
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["sent"] == 0, stats
    assert stats["skipped"] >= 1, stats

    from sqlalchemy import select

    from app.db.session import session_scope
    from app.models import Reminder, ReminderStatus

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Reminder).where(Reminder.agenda_id == uuid.UUID(agenda["id"]))
            )
        ).scalars().all()

    skipped = [row for row in rows if row.status is ReminderStatus.SKIPPED]
    assert skipped, "nothing was recorded as skipped"
    assert any(row.status is ReminderStatus.SENT for row in rows) is False
    # A skip is terminal: it must not consume the retry budget.
    assert all(row.attempted == 1 for row in skipped)
    assert all(row.provider == "console" for row in skipped)
    assert "not sent" in (skipped[0].error or "")

    # And it does not come back for another attempt.
    again = await client.post("/api/v1/internal/dispatch", headers=internal)
    assert again.json()["claimed"] == 0


@pytest.mark.asyncio
async def test_dispatch_reports_skipped_reminders_without_failing_them(
    client, registered, monkeypatch
):
    """A sender that refuses to deliver leaves the row skipped, not failed."""
    from app.integrations.channels.base import DeliveryResult
    from app.models import ReminderStatus
    from app.services import reminder_service

    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=2)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    async def refuses(channel, message):
        return DeliveryResult.skipped("test", "provider said no")

    monkeypatch.setattr(reminder_service, "deliver", refuses)

    internal = {"X-Internal-Token": "test-internal-token"}
    stats = (await client.post("/api/v1/internal/dispatch", headers=internal)).json()
    assert stats == {"claimed": stats["claimed"], "sent": 0, "failed": 0, "skipped": stats["claimed"], "retry": 0}
    assert ReminderStatus.SKIPPED.value == "skipped"


@pytest.mark.asyncio
async def test_internal_endpoints_require_the_token(client):
    response = await client.post("/api/v1/internal/dispatch")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "BAD_INTERNAL_TOKEN"


@pytest.mark.asyncio
async def test_calendar_reflects_completed_days(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=1)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    for todo in block["todos"]:
        await client.post(f"/api/v1/todos/{todo['id']}/complete", headers=headers)

    today = local_today("Africa/Lagos")
    calendar = (
        await client.get(
            "/api/v1/dashboard/calendar",
            headers=headers,
            params={"month": f"{today.year:04d}-{today.month:02d}"},
        )
    ).json()

    entry = next(day for day in calendar["days"] if day["date"] == today.isoformat())
    assert entry["complete"] is True
    assert entry["missed"] is False


@pytest.mark.asyncio
async def test_agenda_completion_and_perfect_run_bonus(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=1)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    last = None
    for todo in block["todos"]:
        response = await client.post(f"/api/v1/todos/{todo['id']}/complete", headers=headers)
        last = response.json()

    assert last["agenda_completed"] is True
    assert "agenda_complete" in last["points"]["bonuses"]
    assert "perfect_run" in last["points"]["bonuses"]

    refreshed = (await client.get(f"/api/v1/agendas/{agenda['id']}", headers=headers)).json()
    assert refreshed["status"] == "completed"
    assert refreshed["perfect_run"] is True

    expected = 10 * block["total"] + 25 + 250 + 500
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["points_balance"] == expected


@pytest.mark.asyncio
async def test_points_summary_and_ledger(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=1)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    await client.post(f"/api/v1/todos/{block['todos'][0]['id']}/complete", headers=headers)

    ledger = (await client.get("/api/v1/users/me/points", headers=headers)).json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["reason"] == "task_completed"
    assert ledger["items"][0]["delta"] == 10

    summary = (await client.get("/api/v1/users/me/points/summary", headers=headers)).json()
    assert summary["earned_total"] == 10
    assert summary["balance"] == 10

    streak = (await client.get("/api/v1/users/me/streak", headers=headers)).json()
    assert streak["current"] == 0  # the day is not finished yet


@pytest.mark.asyncio
async def test_progress_endpoint(client, registered):
    headers = registered["headers"]
    agenda = await _create_agenda(client, headers, days=4)
    await _generate(client, headers, agenda["id"])
    await client.post(f"/api/v1/agendas/{agenda['id']}/approve", headers=headers)

    block = (await client.get("/api/v1/dashboard", headers=headers)).json()["today"][0]
    await client.post(f"/api/v1/todos/{block['todos'][0]['id']}/complete", headers=headers)

    progress = (
        await client.get(f"/api/v1/agendas/{agenda['id']}/progress", headers=headers)
    ).json()
    assert progress["total_days"] == 4
    assert progress["current_day_index"] == 1
    assert progress["done_todos"] == 1
    assert len(progress["per_day"]) == 4
    assert progress["per_day"][0]["is_today"] is True


@pytest.mark.asyncio
async def test_cross_account_access_is_denied(client, registered):
    agenda = await _create_agenda(client, registered["headers"], days=2)

    other = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "attacker@example.com",
            "password": "another-good-password",
            "timezone": "UTC",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    response = await client.get(f"/api/v1/agendas/{agenda['id']}", headers=other_headers)
    assert response.status_code == 403

    listing = (await client.get("/api/v1/agendas", headers=other_headers)).json()
    assert listing["total"] == 0
