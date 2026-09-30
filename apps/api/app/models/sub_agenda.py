"""Daily sub-agendas and their to-do items."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models._types import enum_type
from app.models.enums import SubAgendaStatus, TodoSource


class SubAgenda(Base, UUIDMixin, TimestampMixin):
    """The milestone for one day of an agenda."""

    __tablename__ = "sub_agendas"
    __table_args__ = (
        UniqueConstraint("agenda_id", "day_index", name="uq_sub_agendas_agenda_day"),
        UniqueConstraint("agenda_id", "scheduled_date", name="uq_sub_agendas_agenda_date"),
    )

    agenda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agendas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agenda_drafts.id", ondelete="SET NULL")
    )

    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    expected_effort_minutes: Mapped[int | None] = mapped_column(Integer)
    phase: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[SubAgendaStatus] = mapped_column(
        enum_type(SubAgendaStatus), nullable=False, default=SubAgendaStatus.PLANNED
    )
    is_user_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    todos_expanded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Number of times this day has become fully complete; keeps bonus rows idempotent.
    completion_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    agenda: Mapped["Agenda"] = relationship(back_populates="sub_agendas", lazy="selectin")  # noqa: F821
    draft: Mapped["AgendaDraft | None"] = relationship(  # noqa: F821
        back_populates="sub_agendas", foreign_keys=[draft_id]
    )
    todos: Mapped[list[Todo]] = relationship(
        back_populates="sub_agenda",
        cascade="all, delete-orphan",
        order_by="Todo.position",
        lazy="selectin",
    )

    @property
    def done_count(self) -> int:
        return sum(1 for todo in self.todos if todo.is_done)

    @property
    def total_count(self) -> int:
        return len(self.todos)

    @property
    def is_complete(self) -> bool:
        return self.total_count > 0 and self.done_count == self.total_count


class Todo(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "todos"
    __table_args__ = (UniqueConstraint("sub_agenda_id", "position", name="uq_todos_day_position"),)

    sub_agenda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sub_agendas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised for fast dashboard queries.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agenda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agendas.id", ondelete="CASCADE"), nullable=False, index=True
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[TodoSource] = mapped_column(
        enum_type(TodoSource), nullable=False, default=TodoSource.AGENT
    )
    # Increments on every completion; used to build idempotency keys for the ledger.
    completion_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sub_agenda: Mapped[SubAgenda] = relationship(back_populates="todos")
    agenda: Mapped["Agenda"] = relationship(back_populates="todos")  # noqa: F821
