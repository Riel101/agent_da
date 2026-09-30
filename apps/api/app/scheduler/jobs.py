"""Scheduled jobs.

Runs inside the FastAPI process (a product decision), which keeps deployment to
a single Render Web Service. The jobs are idempotent and are also exposed over
HTTP under ``/api/v1/internal/*`` so a Render Cron Job can drive them if the
in-process scheduler ever stalls during a deploy.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.services import materializer, reminder_service

logger = get_logger(__name__)


async def job_dispatch() -> dict:
    """Send reminders that are due. Also the cron safety net's target."""
    try:
        return await reminder_service.dispatch_due()
    except Exception:  # noqa: BLE001 - a failed tick must not kill the scheduler
        logger.exception("dispatch job failed")
        return {"error": "dispatch_failed"}


async def job_materialize() -> dict:
    """Expand upcoming to-dos so tomorrow's list already exists."""
    if not settings.scheduler_enabled:
        return {"skipped": True}
    try:
        async with session_scope() as session:
            return await materializer.materialize_agendas(session)
    except Exception:  # noqa: BLE001
        logger.exception("materialize job failed")
        return {"error": "materialize_failed"}


async def job_day_close() -> dict:
    """Close elapsed days, apply missed-day penalties, refresh streaks."""
    if not settings.scheduler_enabled:
        return {"skipped": True}
    try:
        async with session_scope() as session:
            closed = await materializer.close_finished_days(session)
            rollups = await reminder_service.schedule_weekly_rollups(session)
        return {**closed, "weekly_rollups": rollups}
    except Exception:  # noqa: BLE001
        logger.exception("day-close job failed")
        return {"error": "day_close_failed"}
