"""User profile, points ledger and streak endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import PointsLedgerEntry, User
from app.schemas.common import Page
from app.schemas.user import PointsEntryOut, PointsSummaryOut, StreakOut, UserOut, UserUpdate
from app.services import points_service, streak_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    await user_service.update_user(
        session,
        user,
        full_name=payload.full_name,
        timezone=payload.timezone,
        phone_e164=payload.phone_e164,
    )
    return UserOut.model_validate(user)


@router.get("/me/points", response_model=Page[PointsEntryOut])
async def points_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    agenda_id: uuid.UUID | None = None,
) -> Page[PointsEntryOut]:
    conditions = [PointsLedgerEntry.user_id == user.id]
    if from_date is not None:
        conditions.append(PointsLedgerEntry.occurred_on >= from_date)
    if to_date is not None:
        conditions.append(PointsLedgerEntry.occurred_on <= to_date)
    if agenda_id:
        conditions.append(PointsLedgerEntry.agenda_id == agenda_id)

    total = await session.scalar(
        select(func.count(PointsLedgerEntry.id)).where(*conditions)
    )
    rows = (
        await session.execute(
            select(PointsLedgerEntry)
            .where(*conditions)
            .order_by(PointsLedgerEntry.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    return Page[PointsEntryOut](
        items=[PointsEntryOut.model_validate(row) for row in rows],
        page=page,
        limit=limit,
        total=int(total or 0),
    )


@router.get("/me/points/summary", response_model=PointsSummaryOut)
async def points_summary(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> PointsSummaryOut:
    return PointsSummaryOut.model_validate(await points_service.summary(session, user.id))


@router.get("/me/streak", response_model=StreakOut)
async def streak(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> StreakOut:
    return StreakOut.model_validate(await streak_service.user_streak_snapshot(session, user))
