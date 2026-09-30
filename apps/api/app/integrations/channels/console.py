"""Console channel.

The zero-credential fallback: reminders are logged instead of sent. This keeps
the whole pipeline exercisable before any email or WhatsApp account exists, and
it is what the test-suite asserts against.
"""

from __future__ import annotations

import hashlib
import json

from app.core.logging import get_logger
from app.integrations.channels.base import DeliveryResult, OutboundMessage

logger = get_logger(__name__)


class ConsoleSender:
    name = "console"

    @property
    def configured(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        logger.info(
            "OUTBOUND[console] to=%s subject=%s\n%s",
            message.to,
            message.subject,
            json.dumps(message.meta, default=str) if message.meta else message.body,
        )
        digest = hashlib.sha1(
            f"{message.to}|{message.subject}|{message.body}".encode("utf-8")
        ).hexdigest()[:16]
        return DeliveryResult.sent(self.name, f"console-{digest}")
