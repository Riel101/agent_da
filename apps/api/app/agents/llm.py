"""LLM access: a thin, retrying wrapper around the NVIDIA NIM endpoint.

The model is reached through the OpenAI-compatible NVIDIA API, so ``ChatNVIDIA``
is used directly. Every call asks for JSON matching a Pydantic schema, with a
repair path for providers that occasionally wrap JSON in prose or code fences.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import AgentError
from app.core.logging import get_logger

logger = get_logger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(slots=True)
class LLMResult:
    parsed: BaseModel
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    repaired: bool = False


class FakeLLM:
    """Deterministic stand-in used when no NVIDIA key is configured.

    It cannot write a genuinely tailored plan, but it produces a well-formed,
    date-anchored one so the whole pipeline (generation → review → reminders →
    points) is exercisable offline and in CI.
    """

    model = "fake/deterministic-planner"

    async def structured(
        self, schema: type[TModel], messages: list[BaseMessage], *, context: dict | None = None, **_: Any
    ) -> LLMResult:
        from app.agents import fake

        data = fake.build_response(schema, messages, context or {})
        return LLMResult(parsed=schema.model_validate(data), model=self.model, repaired=False)


def is_llm_configured() -> bool:
    return bool(settings.nvidia_api_key)


def get_llm(temperature: float | None = None) -> Any:
    if not is_llm_configured():
        return FakeLLM()

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    return ChatNVIDIA(
        model=settings.llm_model,
        nvidia_api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        temperature=settings.llm_temperature if temperature is None else temperature,
        max_completion_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


async def structured_call(
    schema: type[TModel],
    messages: list[BaseMessage],
    *,
    node: str,
    temperature: float | None = None,
    context: dict[str, Any] | None = None,
) -> LLMResult:
    """Call the model and return a validated instance of ``schema``."""
    llm = get_llm(temperature)

    if isinstance(llm, FakeLLM):
        return await llm.structured(schema, messages, context=context)

    last_error: Exception | None = None
    for attempt in range(1, settings.llm_max_retries + 1):
        try:
            return await _attempt(llm, schema, messages)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("%s: attempt %s produced unusable output: %s", node, attempt, exc)
            messages = _nudge(messages, exc)
        except Exception as exc:  # noqa: BLE001 - transient provider failures
            last_error = exc
            logger.warning("%s: attempt %s failed: %s", node, attempt, exc)
            await asyncio.sleep(min(2**attempt, 15))

    raise AgentError(
        f"The planning model could not produce a valid response for '{node}'",
        code="LLM_FAILED",
        details={"node": node, "reason": str(last_error)[:500]},
    )


async def _attempt(llm: Any, schema: type[TModel], messages: list[BaseMessage]) -> LLMResult:
    runnable = llm.with_structured_output(schema, include_raw=True)
    result = await runnable.ainvoke(messages)

    if isinstance(result, dict) and "parsed" in result:
        parsed = result.get("parsed")
        raw_message = result.get("raw")
        usage = _usage(raw_message)
        if parsed is None:
            raise ValueError("model returned no parsable output")
        if isinstance(parsed, dict):
            parsed = schema.model_validate(parsed)
        return LLMResult(parsed=parsed, model=_model_name(llm), **usage)

    if isinstance(result, BaseModel):
        return LLMResult(parsed=result, model=_model_name(llm))
    raise ValueError("unexpected structured output shape")


def _usage(raw: Any) -> dict[str, int]:
    usage = getattr(raw, "usage_metadata", None) or {}
    if isinstance(raw, dict):
        usage = raw.get("usage_metadata") or usage
    return {
        "tokens_in": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "tokens_out": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
    }


def _model_name(llm: Any) -> str:
    return getattr(llm, "model", None) or settings.llm_model


def _nudge(messages: list[BaseMessage], exc: Exception) -> list[BaseMessage]:
    from langchain_core.messages import HumanMessage

    reminder = HumanMessage(
        content=(
            "Your previous response could not be parsed. "
            f"Error: {str(exc)[:200]}. "
            "Reply with a single valid JSON object that matches the requested schema exactly. "
            "No prose, no markdown fences."
        )
    )
    return [*messages, reminder]


def extract_json(text: str) -> dict:
    """Best-effort JSON recovery from a model response."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.split("\n", 1)[-1] if "\n" in candidate else candidate
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if not match:
            raise
        return json.loads(match.group(0))
