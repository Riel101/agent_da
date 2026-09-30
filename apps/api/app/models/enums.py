"""Domain enumerations.

Stored as ``VARCHAR`` with a CHECK constraint (``native_enum=False``) so the same
models work on Postgres in production and SQLite locally.
"""

from __future__ import annotations

from enum import StrEnum


class ReminderChannel(StrEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class AgendaStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class SubAgendaStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    MISSED = "missed"


class TodoSource(StrEnum):
    AGENT = "agent"
    USER = "user"


class LedgerReason(StrEnum):
    TASK_COMPLETED = "task_completed"
    TASK_UNCOMPLETED = "task_uncompleted"
    DAY_COMPLETE = "day_complete"
    DAY_MISSED = "day_missed"
    STREAK_BONUS = "streak_bonus"
    AGENDA_COMPLETE = "agenda_complete"
    PERFECT_RUN = "perfect_run"
    ADJUSTMENT = "adjustment"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReminderKind(StrEnum):
    DAILY = "daily"
    WEEKLY_ROLLUP = "weekly_rollup"


class DraftStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    FAILED = "failed"


class ChannelOutcome(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
