"""To-do request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import TodoSource
from app.schemas.common import ORMModel


class TodoOut(ORMModel):
    id: uuid.UUID
    sub_agenda_id: uuid.UUID
    position: int
    title: str
    notes: str | None = None
    points: int
    is_done: bool
    completed_at: datetime | None = None
    source: TodoSource


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TodoReorder(BaseModel):
    order: list[uuid.UUID] = Field(min_length=1)

    @field_validator("order")
    @classmethod
    def _unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("order must not contain duplicates")
        return value


class CompletionPoints(BaseModel):
    awarded: int
    reason: str
    balance: int
    bonuses: list[str] = Field(default_factory=list)


class DayCompletion(BaseModel):
    complete: bool
    done: int
    total: int
    bonus_awarded: int = 0


class StreakSnapshot(BaseModel):
    current: int
    longest: int


class CompleteResponse(BaseModel):
    todo: TodoOut
    points: CompletionPoints
    day: DayCompletion
    streak: StreakSnapshot
    agenda_completed: bool = False
