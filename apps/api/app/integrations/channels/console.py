"""Console channel.

The zero-credential sink: the rendered reminder is logged instead of sent. It
exists so the whole pipeline is exercisable before any email or WhatsApp account
exists — but it deliberately does **not** claim a delivery.

A console send is reported as ``skipped``, never ``sent``. That keeps the
reminder log honest: a row that says ``sent`` has genuinely reached a provider,
and a row that says ``skipped`` names the configuration that is missing. It is
also what makes "why is nothing arriving?" answerable from the database alone.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.integrations.channels.base import DeliveryResult, OutboundMessage

logger = get_logger(__name__)

#: The reason recorded against every console "delivery".
NOT_CONFIGURED = (
    "No delivery channel is configured, so this reminder was logged, not sent. "
    "Set SMTP_HOST (email) or Twilio/Meta credentials (WhatsApp) to deliver for real."
)


class ConsoleSender:
    name = "console"

    @property
    def configured(self) -> bool:
        """It is always *available* — it is the fallback that keeps dev usable."""
        return True

    @property
    def delivers(self) -> bool:
        """It never reaches a human, so it never reports a real delivery."""
        return False

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        logger.warning(
            "OUTBOUND[console] NOT DELIVERED to=%s subject=%s\n%s",
            message.to,
            message.subject,
            json.dumps(message.meta, default=str) if message.meta else message.body,
        )
        return DeliveryResult.skipped(self.name, NOT_CONFIGURED)
