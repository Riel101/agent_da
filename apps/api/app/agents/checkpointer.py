"""Checkpointer lifecycle.

LangGraph persists graph state (including paused interrupts) through a
checkpointer. Production uses Postgres so a run survives a deploy; local
development and tests use the in-memory saver.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_checkpointer: Any | None = None
_pool: Any | None = None


def _postgres_dsn() -> str:
    return (
        settings.sync_database_url
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
    )


async def get_checkpointer() -> Any:
    global _checkpointer, _pool
    if _checkpointer is not None:
        return _checkpointer

    if settings.checkpointer_backend == "postgres" and not settings.is_sqlite:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            pool = AsyncConnectionPool(
                conninfo=_postgres_dsn(),
                open=False,
                max_size=10,
                kwargs={"autocommit": True, "prepare_threshold": 0},
            )
            await pool.open()
            saver = AsyncPostgresSaver(pool)
            await saver.setup()
            _pool = pool
            _checkpointer = saver
            logger.info("LangGraph checkpointer: postgres")
            return _checkpointer
        except Exception as exc:  # noqa: BLE001 - never block startup on this
            logger.error("Postgres checkpointer unavailable (%s); using in-memory", exc)

    from langgraph.checkpoint.memory import InMemorySaver

    _checkpointer = InMemorySaver()
    logger.info("LangGraph checkpointer: in-memory")
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:  # noqa: BLE001
            pass
    _pool = None
    _checkpointer = None


def reset_checkpointer() -> None:
    """Test helper: drop any cached saver."""
    global _checkpointer, _pool
    _pool = None
    _checkpointer = None
