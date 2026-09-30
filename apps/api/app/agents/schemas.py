"""Structured-output contracts exchanged with the LLM.

Every node speaks in one of these Pydantic models; the LLM is asked for JSON
matching the schema rather than free-form prose.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TodoDraft(BaseModel):
    """One checkable action item."""

    title: str = Field(description="Imperative, under 80 characters, one sitting of work")
    notes: str | None = Field(default=None, description="Optional hint or definition of done")

    @field_validator("title")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        return cleaned[:300]


class SubAgendaPlan(BaseModel):
    """One day of the plan."""

    day_index: int = Field(description="1-based day number inside the timeframe")
    title: str = Field(description="Short headline for the day, under 100 characters")
    description: str = Field(description="What the user actually does that day")
    expected_outcome: str = Field(description="The concrete result produced by end of day")
    expected_effort_minutes: int = Field(
        default=60, ge=5, le=720, description="Realistic minutes of focused work"
    )
    phase: str | None = Field(default=None, description="Journey phase, e.g. foundation")

    @field_validator("title", "description", "expected_outcome")
    @classmethod
    def _trim(cls, value: str) -> str:
        return " ".join(value.split()).strip()


class PlanOutput(BaseModel):
    sub_agendas: list[SubAgendaPlan]


class TodoListOutput(BaseModel):
    todos: list[TodoDraft]


class CritiqueIssue(BaseModel):
    severity: Literal["error", "warning"] = "warning"
    code: str = Field(default="GENERIC", description="Short machine-readable code")
    day_index: int | None = Field(default=None, description="Offending day, if any")
    message: str
    fix: str | None = Field(default=None, description="What to change")


class CritiqueOutput(BaseModel):
    issues: list[CritiqueIssue] = Field(default_factory=list)
    reaches_goal_on_final_day: bool = True


class IntakeOutput(BaseModel):
    is_specific: bool = Field(description="True when the agenda is concrete enough to plan")
    clarifying_questions: list[str] = Field(
        default_factory=list, description="At most three questions"
    )
    agenda_type: str = Field(default="other", description="learning|fitness|shipping|writing|business|other")


class MotivationOutput(BaseModel):
    message: str = Field(description="Two short sentences of specific encouragement")


class DayRegenerationOutput(BaseModel):
    sub_agenda: SubAgendaPlan
    todos: list[TodoDraft]
