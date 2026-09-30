"""Channel registry.

Resolves the sender for a channel, with graceful degradation so the product
works before any messaging account exists:

    email    -> SMTP, falling back to console when SMTP is unconfigured
    whatsapp -> Twilio if configured, else Meta, else console
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.channels.base import ChannelSender, DeliveryResult, OutboundMessage
from app.integrations.channels.console import ConsoleSender
from app.integrations.channels.email import EmailSender
from app.integrations.channels.whatsapp import WhatsAppMetaSender, WhatsAppTwilioSender
from app.models.enums import ReminderChannel

logger = get_logger(__name__)

_console = ConsoleSender()
_email = EmailSender()
_twilio = WhatsAppTwilioSender()
_meta = WhatsAppMetaSender()


def whatsapp_sender() -> ChannelSender:
    preference = settings.whatsapp_provider
    if preference == "twilio":
        return _twilio
    if preference == "meta":
        return _meta
    if preference == "console":
        return _console
    # auto
    if _twilio.configured:
        return _twilio
    if _meta.configured:
        return _meta
    return _console


def email_sender() -> ChannelSender:
    return _email if _email.configured else _console


def resolve_sender(channel: ReminderChannel) -> ChannelSender:
    if channel is ReminderChannel.WHATSAPP:
        return whatsapp_sender()
    return email_sender()


async def deliver(channel: ReminderChannel, message: OutboundMessage) -> DeliveryResult:
    """Send via the preferred channel, then fall back to email when allowed."""
    sender = resolve_sender(channel)
    result = await sender.send(message)

    if result.ok or result.outcome.value == "skipped":
        return result

    if channel is ReminderChannel.WHATSAPP and settings.fallback_to_email:
        fallback_target = message.email_fallback
        if fallback_target:
            logger.info("WhatsApp failed, falling back to email for %s", fallback_target)
            fallback = OutboundMessage(
                to=fallback_target,
                subject=f"[WhatsApp fallback] {message.subject}",
                body=message.body,
                meta=message.meta,
            )
            email_result = await email_sender().send(fallback)
            if email_result.ok:
                return DeliveryResult.sent(
                    f"{result.provider}->{email_result.provider}",
                    email_result.message_id,
                    fallback=True,
                )
            return DeliveryResult.failed(
                f"{result.provider}->{email_result.provider}",
                f"{result.error}; fallback failed: {email_result.error}",
            )
    return result


def channel_status() -> dict[str, dict[str, object]]:
    """Diagnostics for /healthz and the admin view."""
    return {
        "email": {"sender": _email.name, "configured": _email.configured},
        "whatsapp": {
            "sender": whatsapp_sender().name,
            "provider_setting": settings.whatsapp_provider,
            "twilio_configured": _twilio.configured,
            "meta_configured": _meta.configured,
        },
    }
