"""Test configuration.

Environment is configured *before* the application is imported so the cached
settings singleton picks it up. Tests run against a file-backed SQLite database
(a real file, not ``:memory:``, so concurrent sessions do not fight over a single
connection) with the scheduler off and no LLM credentials — the deterministic
offline planner is used instead.
"""

from __future__ import annotations

import os
import pathlib

TEST_DB = pathlib.Path("/tmp/opencode/agent_da_test.db")
TEST_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["INTERNAL_TOKEN"] = "test-internal-token"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-do-not-use"
os.environ["NVIDIA_API_KEY"] = ""
os.environ["MOTIVATION_ENABLED"] = "true"
os.environ["SMTP_HOST"] = ""
os.environ["WHATSAPP_PROVIDER"] = "console"
os.environ["AGENT_AUTOSTART"] = "false"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    import app.models  # noqa: F401
    from app.db.base import Base
    from app.db.session import dispose_engine, get_engine

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


@pytest_asyncio.fixture(autouse=True)
async def _clean_state(_schema):
    """Truncate every table and reset process-local state between tests."""
    from sqlalchemy import delete

    import app.models as models
    from app.agents.checkpointer import reset_checkpointer
    from app.agents.runner import runner
    from app.core import ratelimit
    from app.db.session import session_scope

    async with session_scope() as session:
        for table in (
            models.Reminder,
            models.PointsLedgerEntry,
            models.Todo,
            models.SubAgenda,
            models.AgendaDraft,
            models.Agenda,
            models.RefreshToken,
            models.User,
        ):
            await session.execute(delete(table))

    ratelimit.reset()
    runner.reset()
    reset_checkpointer()
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest_asyncio.fixture
async def registered(client):
    """A signed-up user plus the auth headers to act as them."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "ada@example.com",
            "password": "correct-horse-battery",
            "full_name": "Ada",
            "timezone": "Africa/Lagos",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {
        "user": payload["user"],
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        "refresh_token": payload["refresh_token"],
    }
