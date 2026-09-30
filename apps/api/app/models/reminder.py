"""Reminder outbox + delivery log.

One row per (agenda, sub-agenda, kind, local date). ``dedupe_key`` carries the
uniqueness so ``NULL`` sub-agendas (weekly rollups) are still deduplicated.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models._types import enum_type
from app.models.enums import ReminderChannel, ReminderKind, ReminderStatus


class Reminder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_reminders_dedupe"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agenda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agendas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sub_agenda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sub_agendas.id", ondelete="CASCADE")
    )

    kind: Mapped[ReminderKind] = mapped_column(
        enum_type(ReminderKind), nullable=False, default=ReminderKind.DAILY
    )
    channel: Mapped[ReminderChannel] = mapped_column(enum_type(ReminderChannel), nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(
        enum_type(ReminderStatus), nullable=False, default=ReminderStatus.PENDING, index=True
    )

    # UTC instant the reminder should go out, derived from the user's local time.
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)

    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    body_preview: Mapped[str | None] = mapped_column(Text)
    body_subject: Mapped[str | None] = mapped_column(String(300))

    agenda: Mapped["Agenda"] = relationship(back_populates="reminders")  # noqa: F821
    sub_agenda: Mapped["SubAgenda | None"] = relationship()  # noqa: F821

    @staticmethod
    def build_dedupe_key(
        agenda_id: uuid.UUID,
        sub_agenda_id: uuid.UUID | None,
        kind: ReminderKind,
        local_date: date,
    ) -> str:
        return f"{agenda_id}:{sub_agenda_id or 'none'}:{kind.value}:{local_date.isoformat()}"
