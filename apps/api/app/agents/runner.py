"""Runs the planning graph.

The graph is compiled once and shared. Every run is keyed by
``thread_id = agenda_drafts.id`` so an interrupted run can be resumed from the
checkpoint — even after a redeploy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

from app.agents.checkpointer import get_checkpointer
from app.agents.graph import GRAPH_RECURSION_LIMIT, build_graph
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class GraphOutcome:
    interrupted: bool
    kind: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.state.get("phase") == "failed"

    @property
    def error(self) -> str | None:
        return self.state.get("error")


class AgendaAgentRunner:
    def __init__(self) -> None:
        self._graph: Any | None = None
        self._lock = asyncio.Lock()

    async def graph(self) -> Any:
        if self._graph is None:
            async with self._lock:
                if self._graph is None:
                    checkpointer = await get_checkpointer()
                    self._graph = build_graph(checkpointer)
        return self._graph

    def reset(self) -> None:
        """Test helper."""
        self._graph = None

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

    async def start(self, thread_id: str, state: dict[str, Any]) -> GraphOutcome:
        graph = await self.graph()
        config = self._config(thread_id)
        result = await graph.ainvoke(state, config)
        return await self._outcome(graph, config, result)

    async def resume(self, thread_id: str, payload: dict[str, Any]) -> GraphOutcome:
        graph = await self.graph()
        config = self._config(thread_id)
        result = await graph.ainvoke(Command(resume=payload), config)
        return await self._outcome(graph, config, result)

    async def _outcome(self, graph: Any, config: dict, result: Any) -> GraphOutcome:
        snapshot = await graph.aget_state(config)
        values = dict(snapshot.values or {})

        interrupts: list[Any] = []
        for task in snapshot.tasks or ():
            interrupts.extend(getattr(task, "interrupts", ()) or ())

        if interrupts:
            raw = getattr(interrupts[0], "value", interrupts[0])
            payload = dict(raw) if isinstance(raw, dict) else {"value": raw}
            return GraphOutcome(
                interrupted=True,
                kind=str(payload.get("kind") or "review"),
                state=values,
                payload=payload,
            )

        if not values and isinstance(result, dict):
            values = dict(result)
        return GraphOutcome(interrupted=False, state=values)


runner = AgendaAgentRunner()
