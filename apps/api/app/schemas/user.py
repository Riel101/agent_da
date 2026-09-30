"""User and gamification response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import LedgerReason
from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    timezone: str
    phone_e164: str | None = None
    email_verified_at: datetime | None = None
    points_balance: int
    current_streak: int
    longest_streak: int
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    phone_e164: str | None = Field(default=None, max_length=20)

    @field_validator("phone_e164")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().replace(" ", "").replace("-", "")
        if not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("phone must be in E.164 format, e.g. +2348012345678")
        return cleaned


class PointsEntryOut(ORMModel):
    id: uuid.UUID
    reason: LedgerReason
    delta: int
    meta: dict | None = None
    occurred_on: date
    agenda_id: uuid.UUID | None = None
    todo_id: uuid.UUID | None = None
    created_at: datetime


class StreakOut(BaseModel):
    current: int
    longest: int
    last_complete_date: date | None = None
    # date -> True when every to-do for that day was completed.
    recent_days: dict[str, bool] = Field(default_factory=dict)


class PointsSummaryOut(BaseModel):
    balance: int
    earned_total: int
    spent_total: int
    by_reason: dict[str, int] = Field(default_factory=dict)
