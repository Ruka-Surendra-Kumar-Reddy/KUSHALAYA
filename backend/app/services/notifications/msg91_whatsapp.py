"""MSG91 WhatsApp (Meta Cloud API through MSG91 as the BSP).

Business-started WhatsApp messages must use a Meta-approved template, so
``send_text`` wraps free text in one general template
(``MSG91_WHATSAPP_TEXT_TEMPLATE``, a single ``{{1}}`` body variable).
"""

from __future__ import annotations

import logging
import re

import httpx

from app.core.config import settings
from app.services.notifications.base import WhatsAppProvider
from app.services.notifications.types import (
    DeliveryResult,
    DeliveryStatus,
    WhatsAppTemplateMessage,
)

logger = logging.getLogger(__name__)

MSG91_WA_BULK_URL = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
# Meta rejects template variables with newlines, tabs or 4+ spaces in a row.
PARAM_MAX = 900


def _auth_key() -> str:
    # Same MSG91 account as SMS: the key saved in Settings wins over .env.
    from app.services.notifications import channel_config

    cfg = channel_config.active("sms") or {}
    return (cfg.get("auth_key") or settings.MSG91_AUTH_KEY or "").strip()


def _param(value: str) -> str:
    text = re.sub(r"\s*\n+\s*", " · ", str(value or "").strip())
    text = re.sub(r"[\t ]{2,}", " ", text)
    return text[:PARAM_MAX] or "-"


def _digits(to: str) -> str:
    digits = re.sub(r"\D", "", to or "")
    return f"91{digits}" if len(digits) == 10 else digits


class Msg91WhatsAppProvider(WhatsAppProvider):
    def send_template(self, to: str, message: WhatsAppTemplateMessage) -> DeliveryResult:
        auth_key = _auth_key()
        number = _digits(settings.MSG91_WHATSAPP_NUMBER)
        if not auth_key or not number:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="MSG91 WhatsApp not configured — set MSG91_AUTH_KEY and MSG91_WHATSAPP_NUMBER",
            )
        components = {
            f"body_{i}": {"type": "text", "value": _param(p)} for i, p in enumerate(message.body_params, start=1)
        }
        # Document header (invoice PDF): WhatsApp downloads it from the public URL.
        doc_url = getattr(message, "header_document_url", "") or ""
        if doc_url:
            components["header_1"] = {
                "type": "document",
                "value": doc_url,
                "filename": getattr(message, "header_filename", "") or "document.pdf",
            }
        payload = {
            "integrated_number": number,
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "type": "template",
                "template": {
                    "name": message.template_name,
                    "language": {"code": message.language_code, "policy": "deterministic"},
                    "namespace": None,
                    "to_and_components": [{"to": [_digits(to)], "components": components}],
                },
            },
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    MSG91_WA_BULK_URL,
                    json=payload,
                    headers={"authkey": auth_key, "accept": "application/json"},
                )
            data = response.json() if response.content else {}
        except Exception as exc:
            logger.exception("msg91_whatsapp_failed to=%s template=%s", to, message.template_name)
            return DeliveryResult(status=DeliveryStatus.FAILED, detail=str(exc)[:500])
        ok = response.status_code < 400 and not data.get("hasError") and data.get("status") != "fail"
        detail = str(data.get("data") or data.get("errors") or data)[:500]
        if not ok:
            logger.warning("msg91_whatsapp_rejected to=%s template=%s body=%s", to, message.template_name, detail)
            return DeliveryResult(status=DeliveryStatus.FAILED, detail=detail)
        logger.info("msg91_whatsapp_sent to=%s template=%s", to, message.template_name)
        return DeliveryResult(status=DeliveryStatus.SENT, detail=detail)

    def send_team_text(self, to: str, body: str) -> DeliveryResult:
        template = (settings.MSG91_WHATSAPP_TEAM_TEMPLATE or "").strip()
        if not template:
            return self.send_text(to, body)
        return self.send_template(to, WhatsAppTemplateMessage(template_name=template, body_params=(body,)))

    def send_text(self, to: str, body: str) -> DeliveryResult:
        template = (settings.MSG91_WHATSAPP_TEXT_TEMPLATE or "").strip()
        if not template:
            return super().send_text(to, body)
        return self.send_template(to, WhatsAppTemplateMessage(template_name=template, body_params=(body,)))
