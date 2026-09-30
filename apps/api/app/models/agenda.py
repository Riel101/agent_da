"""Agendas (long-term goals) and their generated drafts."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models._types import JsonColumn, enum_type
from app.models.enums import AgendaStatus, DraftStatus, ReminderChannel


class Agenda(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agendas"
    __table_args__ = (
        CheckConstraint("timeframe_days >= 1", name="ck_agendas_timeframe_positive"),
        CheckConstraint("end_date >= start_date", name="ck_agendas_date_order"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    timeframe_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    reminder_channel: Mapped[ReminderChannel] = mapped_column(
        enum_type(ReminderChannel), nullable=False, default=ReminderChannel.EMAIL
    )
    reminder_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    status: Mapped[AgendaStatus] = mapped_column(
        enum_type(AgendaStatus), nullable=False, default=AgendaStatus.DRAFT, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    perfect_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Scheduler bookkeeping so the periodic jobs stay idempotent.
    last_materialized_date: Mapped[date | None] = mapped_column(Date)
    last_closed_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped["User"] = relationship(back_populates="agendas")  # noqa: F821
    drafts: Mapped[list[AgendaDraft]] = relationship(
        back_populates="agenda", cascade="all, delete-orphan", order_by="AgendaDraft.revision.desc()"
    )
    sub_agendas: Mapped[list["SubAgenda"]] = relationship(  # noqa: F821
        back_populates="agenda",
        cascade="all, delete-orphan",
        order_by="SubAgenda.day_index",
    )
    todos: Mapped[list["Todo"]] = relationship(  # noqa: F821
        back_populates="agenda", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(  # noqa: F821
        back_populates="agenda", cascade="all, delete-orphan"
    )

    @property
    def is_editable(self) -> bool:
        return self.status in {AgendaStatus.DRAFT, AgendaStatus.READY, AgendaStatus.GENERATING}

    @property
    def latest_draft(self) -> AgendaDraft | None:
        return self.drafts[0] if self.drafts else None


class AgendaDraft(Base, UUIDMixin, TimestampMixin):
    """One generation run. ``id`` doubles as the LangGraph ``thread_id``."""

    __tablename__ = "agenda_drafts"

    agenda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agendas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[DraftStatus] = mapped_column(
        enum_type(DraftStatus), nullable=False, default=DraftStatus.QUEUED
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    clarifying_questions: Mapped[list | None] = mapped_column(JsonColumn)
    clarifying_answers: Mapped[dict | None] = mapped_column(JsonColumn)
    validation_issues: Mapped[list | None] = mapped_column(JsonColumn)
    raw_plan: Mapped[dict | None] = mapped_column(JsonColumn)
    stats: Mapped[dict | None] = mapped_column(JsonColumn)

    model: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_passes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    agenda: Mapped[Agenda] = relationship(back_populates="drafts")
    sub_agendas: Mapped[list["SubAgenda"]] = relationship(  # noqa: F821
        back_populates="draft", foreign_keys="SubAgenda.draft_id"
    )

    @property
    def thread_id(self) -> str:
        return str(self.id)

    @property
    def needs_input(self) -> bool:
        return self.status == DraftStatus.NEEDS_INPUT

    @property
    def needs_review(self) -> bool:
        return self.status == DraftStatus.NEEDS_REVIEW
