"""Dashboard response models — one round-trip for the home screen."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import AgendaStatus
from app.schemas.todo import TodoOut


class TodayBlock(BaseModel):
    agenda_id: uuid.UUID
    agenda_title: str
    sub_agenda_id: uuid.UUID
    day_index: int
    title: str
    description: str | None = None
    expected_outcome: str | None = None
    todos: list[TodoOut] = Field(default_factory=list)
    done: int = 0
    total: int = 0


class AgendaCard(BaseModel):
    id: uuid.UUID
    title: str
    status: AgendaStatus
    start_date: date
    end_date: date
    progress_pct: int
    current_day_index: int | None = None
    reminder_channel: str
    reminder_time: str


class DashboardTotals(BaseModel):
    points_balance: int
    current_streak: int
    longest_streak: int


class DashboardOut(BaseModel):
    local_date: date
    timezone: str
    totals: DashboardTotals
    today: list[TodayBlock] = Field(default_factory=list)
    agendas: list[AgendaCard] = Field(default_factory=list)


class CalendarDay(BaseModel):
    date: date
    total: int = 0
    done: int = 0
    complete: bool = False
    missed: bool = False
    is_future: bool = False


class CalendarOut(BaseModel):
    month: str
    days: list[CalendarDay] = Field(default_factory=list)
