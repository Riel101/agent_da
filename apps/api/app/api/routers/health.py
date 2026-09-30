"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.integrations.channels.registry import channel_status
from app.services.reminder_service import pending_count

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness. Deliberately dependency-free so Render can poll it cheaply."""
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_db)) -> dict:
    """Readiness: database reachable, plus channel and queue diagnostics."""
    try:
        await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # noqa: BLE001
        database = f"error: {exc}"

    pending = 0
    if database == "ok":
        try:
            pending = await pending_count(session)
        except Exception:  # noqa: BLE001
            pending = -1

    from app.scheduler.scheduler import scheduler_state

    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "scheduler": scheduler_state(),
        "pending_reminders": pending,
        "channels": channel_status(),
    }
