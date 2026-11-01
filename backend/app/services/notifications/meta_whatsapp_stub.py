"""Meta WhatsApp Cloud API — stub until production BSP credentials are configured."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services.notifications.base import WhatsAppProvider
from app.services.notifications.types import (
    DeliveryResult,
    DeliveryStatus,
    WhatsAppTemplateMessage,
)

logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v21.0"


class MetaWhatsAppStubProvider(WhatsAppProvider):
    """Validates config and logs the payload; does not call Meta in stub mode."""

    def _configured(self) -> bool:
        return bool(
            (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
            and (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
        )

    def send_template(self, to: str, message: WhatsAppTemplateMessage) -> DeliveryResult:
        if not self._configured():
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail=(
                    "WhatsApp not configured — set WHATSAPP_ACCESS_TOKEN and "
                    "WHATSAPP_PHONE_NUMBER_ID (see docs/NOTIFICATIONS.md)"
                ),
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": message.template_name,
                "language": {"code": message.language_code},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": p} for p in message.body_params
                        ],
                    }
                ]
                if message.body_params
                else [],
            },
        }

        url = f"{META_GRAPH_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        logger.info(
            "whatsapp_stub would POST %s template=%s category=%s to=%s payload=%s",
            url,
            message.template_name,
            message.category,
            to,
            payload,
        )

        return DeliveryResult(
            status=DeliveryStatus.LOGGED,
            detail=(
                f"stub: Meta Cloud API send skipped "
                f"(template={message.template_name}, category={message.category})"
            ),
        )
