"""Delivery channel contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.models.enums import ChannelOutcome


@dataclass(slots=True)
class OutboundMessage:
    """A rendered message ready for a channel."""

    to: str
    subject: str
    body: str
    #: Fallback address (email) used when the preferred channel cannot deliver.
    email_fallback: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DeliveryResult:
    outcome: ChannelOutcome
    provider: str
    message_id: str | None = None
    error: str | None = None
    fallback_used: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome is ChannelOutcome.SENT

    @classmethod
    def sent(cls, provider: str, message_id: str | None, *, fallback: bool = False) -> DeliveryResult:
        return cls(ChannelOutcome.SENT, provider, message_id, fallback_used=fallback)

    @classmethod
    def failed(cls, provider: str, error: str) -> DeliveryResult:
        return cls(ChannelOutcome.FAILED, provider, error=error)

    @classmethod
    def skipped(cls, provider: str, reason: str) -> DeliveryResult:
        return cls(ChannelOutcome.SKIPPED, provider, error=reason)


@runtime_checkable
class ChannelSender(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def send(self, message: OutboundMessage) -> DeliveryResult: ...
