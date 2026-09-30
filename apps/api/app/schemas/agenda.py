"""Agenda and draft request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from app.models.enums import AgendaStatus, DraftStatus, ReminderChannel, SubAgendaStatus
from app.schemas.common import ORMModel
from app.schemas.todo import TodoOut


class AgendaCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=1)
    timeframe_days: int = Field(ge=1, le=365)
    start_date: date | None = None
    reminder_channel: ReminderChannel = ReminderChannel.EMAIL
    reminder_time: time = time(8, 0)
    timezone: str | None = Field(default=None, max_length=64)
    phone_e164: str | None = Field(default=None, max_length=20)

    @field_validator("description")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description cannot be blank")
        return cleaned

    @field_validator("phone_e164")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().replace(" ", "").replace("-", "")
        if not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("phone must be in E.164 format, e.g. +2348012345678")
        return cleaned

    @field_serializer("reminder_time")
    def _time_to_hhmm(self, value: time) -> str:
        return value.strftime("%H:%M")


class AgendaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = None
    timeframe_days: int | None = Field(default=None, ge=1, le=365)
    start_date: date | None = None
    reminder_channel: ReminderChannel | None = None
    reminder_time: time | None = None
    timezone: str | None = Field(default=None, max_length=64)
    phone_e164: str | None = Field(default=None, max_length=20)


class AgendaOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None = None
    timeframe_days: int
    start_date: date
    end_date: date
    reminder_channel: ReminderChannel
    reminder_time: time
    timezone: str
    status: AgendaStatus
    approved_at: datetime | None = None
    completed_at: datetime | None = None
    total_points: int
    perfect_run: bool
    created_at: datetime

    @field_serializer("reminder_time")
    def _time_to_hhmm(self, value: time) -> str:
        return value.strftime("%H:%M")


class AgendaSummary(AgendaOut):
    total_todos: int = 0
    done_todos: int = 0
    progress_pct: int = 0
    missed_days: int = 0
    days_elapsed: int = 0


class SubAgendaOut(ORMModel):
    id: uuid.UUID
    agenda_id: uuid.UUID
    day_index: int
    scheduled_date: date
    title: str
    description: str | None = None
    expected_outcome: str | None = None
    expected_effort_minutes: int | None = None
    phase: str | None = None
    status: SubAgendaStatus
    is_user_edited: bool
    todos_expanded: bool
    done_count: int = 0
    total_count: int = 0
    is_complete: bool = False


class SubAgendaDraftOut(BaseModel):
    """A proposed day inside a draft, before it is persisted as a SubAgenda."""

    day_index: int
    scheduled_date: date
    title: str
    description: str | None = None
    expected_outcome: str | None = None
    expected_effort_minutes: int | None = None
    phase: str | None = None
    todos: list[dict] = Field(default_factory=list)


class DraftStats(BaseModel):
    days: int = 0
    todos: int = 0
    expanded_days: int = 0


class DraftOut(ORMModel):
    draft_id: uuid.UUID
    agenda_id: uuid.UUID
    status: DraftStatus
    revision: int
    clarifying_questions: list[str] = Field(default_factory=list)
    clarifying_answers: dict | None = None
    validation_issues: list[dict] = Field(default_factory=list)
    error: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    repair_passes: int = 0
    sub_agendas: list[SubAgendaDraftOut] = Field(default_factory=list)
    stats: DraftStats = Field(default_factory=DraftStats)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: object) -> object:
        if isinstance(data, dict):
            for key in ("clarifying_questions", "validation_issues"):
                if data.get(key) is None:
                    data[key] = []
        return data


class ClarifyingAnswersIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class RegenerateIn(BaseModel):
    scope: Literal["all", "day"] = "all"
    day_index: int | None = Field(default=None, ge=1)
    instructions: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _day_required(self) -> RegenerateIn:
        if self.scope == "day" and self.day_index is None:
            raise ValueError("day_index is required when scope='day'")
        return self


class DayUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    expected_outcome: str | None = None
    expected_effort_minutes: int | None = Field(default=None, ge=0, le=1440)


class GenerateOut(BaseModel):
    draft_id: uuid.UUID
    status: DraftStatus
    revision: int


class ApproveOut(BaseModel):
    agenda: AgendaOut
    scheduled_reminders: int
    expanded_days: int


class AgendaProgressOut(BaseModel):
    agenda_id: uuid.UUID
    status: AgendaStatus
    progress_pct: int
    total_todos: int
    done_todos: int
    total_days: int
    completed_days: int
    missed_days: int
    days_remaining: int
    points_earned: int
    current_day_index: int | None = None
    per_day: list[dict] = Field(default_factory=list)


class DayDetailOut(BaseModel):
    sub_agenda: SubAgendaOut
    todos: list[TodoOut] = Field(default_factory=list)
