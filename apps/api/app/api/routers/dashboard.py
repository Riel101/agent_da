"""Dashboard and calendar endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import CalendarOut, DashboardOut
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> DashboardOut:
    return DashboardOut.model_validate(await dashboard_service.dashboard(session, user))


@router.get("/dashboard/calendar", response_model=CalendarOut)
async def calendar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    month: str | None = Query(default=None, description="YYYY-MM, defaults to the current month"),
) -> CalendarOut:
    return CalendarOut.model_validate(await dashboard_service.calendar(session, user, month))
