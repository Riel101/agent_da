"""Email delivery over SMTP.

Works with any provider that speaks SMTP (Resend, SendGrid, Mailgun, Postmark,
or a plain Gmail app password) so no vendor SDK is required.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.channels.base import DeliveryResult, OutboundMessage

logger = get_logger(__name__)


class EmailSender:
    name = "smtp"

    @property
    def configured(self) -> bool:
        return bool(settings.smtp_host)

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        if not self.configured:
            logger.warning("SMTP not configured; email to %s dropped", message.to)
            return DeliveryResult.skipped(self.name, "SMTP is not configured")

        try:
            message_id = await asyncio.to_thread(self._send_sync, message)
        except Exception as exc:  # noqa: BLE001 - surfaced to the reminder log
            logger.warning("SMTP send to %s failed: %s", message.to, exc)
            return DeliveryResult.failed(self.name, str(exc))

        return DeliveryResult.sent(self.name, message_id)

    def _send_sync(self, message: OutboundMessage) -> str:
        payload = EmailMessage()
        payload["From"] = settings.smtp_from
        payload["To"] = message.to
        payload["Subject"] = message.subject
        payload["Date"] = formatdate(localtime=True)
        message_id = make_msgid(domain="agentda.local")
        payload["Message-ID"] = message_id
        payload.set_content(message.body)

        context = ssl.create_default_context()
        timeout = settings.smtp_timeout_seconds

        if settings.smtp_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout, context=context
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)

        try:
            client.ehlo()
            if settings.smtp_starttls and not settings.smtp_ssl:
                client.starttls(context=context)
                client.ehlo()
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(payload)
        finally:
            try:
                client.quit()
            except smtplib.SMTPException:  # pragma: no cover - best effort
                client.close()

        return message_id
