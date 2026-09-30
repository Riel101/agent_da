"""Internal endpoints.

Called by the in-process scheduler and, as a safety net, by a Render Cron Job
with the ``X-Internal-Token`` header. Keeping them HTTP means the same jobs can
run from either trigger.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_internal_token
from app.db.session import get_db, session_scope
from app.services import materializer, reminder_service

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_token)]
)


@router.post("/dispatch")
async def dispatch(
    limit: int | None = Query(default=None, ge=1, le=500),
) -> dict:
    """Send every reminder that is due."""
    return await reminder_service.dispatch_due(limit)


@router.post("/materialize")
async def materialize() -> dict:
    """Expand upcoming to-dos for every running agenda."""
    async with session_scope() as session:
        return await materializer.materialize_agendas(session)


@router.post("/day-close")
async def day_close() -> dict:
    """Close finished days, apply missed-day penalties, refresh streaks."""
    async with session_scope() as session:
        return await materializer.close_finished_days(session)


@router.post("/weekly-rollups")
async def weekly_rollups(session: AsyncSession = Depends(get_db)) -> dict:
    created = await reminder_service.schedule_weekly_rollups(session)
    return {"scheduled": created}
