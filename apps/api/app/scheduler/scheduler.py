"""APScheduler wiring."""

from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logging import get_logger
from app.scheduler.jobs import job_day_close, job_dispatch, job_materialize

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None
_started_at: datetime | None = None
_last_dispatch: datetime | None = None


def start_scheduler() -> AsyncIOScheduler | None:
    """Start the background scheduler. No-op when disabled."""
    global _scheduler, _started_at
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled by configuration")
        return None
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        job_dispatch,
        IntervalTrigger(seconds=settings.dispatch_interval_seconds),
        id="dispatch_reminders",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        job_materialize,
        IntervalTrigger(minutes=settings.materialize_interval_minutes),
        id="materialize_todos",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        job_day_close,
        IntervalTrigger(minutes=settings.day_close_interval_minutes),
        id="close_days",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    _started_at = datetime.now(UTC)
    logger.info(
        "scheduler started (dispatch every %ss, materialize every %sm, day-close every %sm)",
        settings.dispatch_interval_seconds,
        settings.materialize_interval_minutes,
        settings.day_close_interval_minutes,
    )
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
        logger.info("scheduler stopped")


def scheduler_state() -> dict:
    if _scheduler is None:
        return {"running": False, "enabled": settings.scheduler_enabled}
    jobs = [
        {
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in _scheduler.get_jobs()
    ]
    return {
        "running": _scheduler.running,
        "enabled": settings.scheduler_enabled,
        "started_at": _started_at.isoformat() if _started_at else None,
        "jobs": jobs,
    }
