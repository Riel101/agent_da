"""The planning graph.

    intake ──▶ clarify ──▶ skeleton ──▶ plan ──▶ critique ──▶ repair ─┐
                                          ▲                          │
                                          │                          └──▶ expand
                                          │                                │
                                          │                                ▼
                                          │                            persist
                                          │                                │
                                          │                                ▼
                                          └──── review ◀────────────────────┘
                                                   │
                                                   ▼
                                                finalize
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import AgendaState
from app.core.config import settings


def route_after_intake(state: AgendaState) -> str:
    if state.get("phase") == "failed":
        return "failed"
    if state.get("clarifying_questions") and not state.get("clarifying_answers"):
        return "clarify"
    return "plan"


def route_after_critique(state: AgendaState) -> str:
    errors = [issue for issue in state.get("issues", []) if issue.get("severity") == "error"]
    passes = int(state.get("repair_passes", 0))
    if errors and passes < settings.max_repair_passes:
        return "repair"
    return "expand"


def route_after_review(state: AgendaState) -> str:
    decision = state.get("user_decision")
    if decision == "regenerate_all":
        return "plan"
    if decision in {"regenerate_day", "edit"}:
        return "critique"
    return "finalize"


async def _failed(state: AgendaState) -> dict:
    return {"phase": "failed", "error": state.get("error") or "Planning could not continue."}


def build_graph(checkpointer: Any | None = None):
    builder = StateGraph(AgendaState)

    builder.add_node("intake_validate", nodes.intake_validate)
    builder.add_node("ask_clarifications", nodes.ask_clarifications)
    builder.add_node("build_skeleton", nodes.build_skeleton)
    builder.add_node("plan", nodes.plan)
    builder.add_node("critique", nodes.critique)
    builder.add_node("repair", nodes.repair)
    builder.add_node("expand_todos", nodes.expand_todos)
    builder.add_node("persist_draft", nodes.persist_draft)
    builder.add_node("await_review", nodes.await_review)
    builder.add_node("apply_edits", nodes.apply_edits)
    builder.add_node("finalize", nodes.finalize)
    builder.add_node("failed", _failed)

    builder.add_edge(START, "intake_validate")
    builder.add_conditional_edges(
        "intake_validate",
        route_after_intake,
        {"clarify": "ask_clarifications", "plan": "build_skeleton", "failed": "failed"},
    )
    builder.add_edge("ask_clarifications", "build_skeleton")
    builder.add_edge("build_skeleton", "plan")
    builder.add_edge("plan", "critique")
    builder.add_conditional_edges(
        "critique", route_after_critique, {"repair": "repair", "expand": "expand_todos"}
    )
    builder.add_edge("repair", "critique")
    builder.add_edge("expand_todos", "persist_draft")
    builder.add_edge("persist_draft", "await_review")
    builder.add_conditional_edges(
        "await_review",
        route_after_review,
        {"plan": "plan", "critique": "apply_edits", "finalize": "finalize"},
    )
    builder.add_edge("apply_edits", "critique")
    builder.add_edge("finalize", END)
    builder.add_edge("failed", END)

    return builder.compile(checkpointer=checkpointer)


GRAPH_RECURSION_LIMIT = 100
