"""WhatsApp delivery.

Two providers are supported because the account may not exist yet:

* **Twilio** — ``POST /Accounts/{sid}/Messages.json``. Free-form bodies are only
  allowed inside a 24-hour user-initiated window, so a pre-approved
  ``ContentSid`` template is used when configured.
* **Meta WhatsApp Cloud API** — ``POST /{phone_number_id}/messages``. Also needs
  an approved template outside the customer-service window.

Both use plain HTTP via ``httpx`` so no vendor SDK is required.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.channels.base import DeliveryResult, OutboundMessage

logger = get_logger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class WhatsAppTwilioSender:
    name = "twilio-whatsapp"

    @property
    def configured(self) -> bool:
        return bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_whatsapp_from
        )

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        if not self.configured:
            return DeliveryResult.skipped(self.name, "Twilio credentials are missing")

        sender = settings.twilio_whatsapp_from
        if not sender.startswith("whatsapp:"):
            sender = f"whatsapp:{sender}"
        recipient = message.to if message.to.startswith("whatsapp:") else f"whatsapp:{message.to}"

        data: dict[str, str] = {"To": recipient, "From": sender}
        if settings.twilio_content_sid:
            data["ContentSid"] = settings.twilio_content_sid
            data["ContentVariables"] = _template_variables(message)
        else:
            data["Body"] = message.body

        url = TWILIO_API.format(sid=settings.twilio_account_sid)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                )
        except httpx.HTTPError as exc:
            return DeliveryResult.failed(self.name, f"network error: {exc}")

        if response.status_code >= 400:
            return DeliveryResult.failed(self.name, _short(response))

        return DeliveryResult.sent(self.name, response.json().get("sid"))


class WhatsAppMetaSender:
    name = "meta-whatsapp"

    @property
    def configured(self) -> bool:
        return bool(settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id)

    async def send(self, message: OutboundMessage) -> DeliveryResult:
        if not self.configured:
            return DeliveryResult.skipped(self.name, "Meta WhatsApp credentials are missing")

        url = (
            f"https://graph.facebook.com/{settings.meta_whatsapp_api_version}"
            f"/{settings.meta_whatsapp_phone_number_id}/messages"
        )
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.to.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": message.body},
        }
        headers = {
            "Authorization": f"Bearer {settings.meta_whatsapp_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            return DeliveryResult.failed(self.name, f"network error: {exc}")

        if response.status_code >= 400:
            return DeliveryResult.failed(self.name, _short(response))

        payload = response.json()
        message_id = None
        if isinstance(payload.get("messages"), list) and payload["messages"]:
            message_id = payload["messages"][0].get("id")
        return DeliveryResult.sent(self.name, message_id)


def _template_variables(message: OutboundMessage) -> str:
    """Twilio template variables as a JSON object of string values."""
    import json

    variables = {
        "1": message.subject,
        "2": message.body,
    }
    variables.update({str(key): str(value) for key, value in (message.meta or {}).items()})
    return json.dumps(variables)


def _short(response: httpx.Response) -> str:
    return f"HTTP {response.status_code}: {response.text[:300]}"
