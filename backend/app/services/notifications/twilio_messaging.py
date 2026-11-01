"""Twilio SMS + WhatsApp (trial / sandbox friendly)."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.notifications.base import SmsProvider, WhatsAppProvider
from app.services.notifications.types import (
    DeliveryResult,
    DeliveryStatus,
    WhatsAppTemplateMessage,
    normalize_phone,
)

logger = logging.getLogger(__name__)


def to_e164(phone: str | None) -> str | None:
    digits = normalize_phone(phone)
    if not digits:
        return None
    return digits if digits.startswith("+") else f"+{digits}"


def _whatsapp_addr(phone: str) -> str:
    raw = (phone or "").strip()
    if raw.lower().startswith("whatsapp:"):
        rest = raw.split(":", 1)[1]
        e164 = to_e164(rest) or rest
        return f"whatsapp:{e164}"
    e164 = to_e164(raw) or raw
    return f"whatsapp:{e164}"


def send_twilio_message(*, frm: str, to: str, body: str) -> DeliveryResult:
    sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
    token = (settings.TWILIO_AUTH_TOKEN or "").strip()
    if not sid or not token:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            detail="TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not configured",
        )
    if not frm or not to:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            detail="Twilio From / To number is missing",
        )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                url,
                data={"From": frm, "To": to, "Body": body},
                auth=(sid, token),
            )
        if response.status_code >= 400:
            detail = (response.text or "")[:400]
            logger.warning("twilio_message_failed to=%s status=%s detail=%s", to, response.status_code, detail)
            return DeliveryResult(status=DeliveryStatus.FAILED, detail=detail)
        data = response.json() if response.content else {}
        status = str(data.get("status") or "queued")
        logger.info("twilio_message_sent to=%s sid=%s status=%s", to, data.get("sid"), status)
        return DeliveryResult(status=DeliveryStatus.SENT, detail=status)
    except Exception as exc:
        logger.exception("twilio_message_failed to=%s", to)
        return DeliveryResult(status=DeliveryStatus.FAILED, detail=str(exc)[:500])


class TwilioSmsProvider(SmsProvider):
    def send(self, to: str, body: str) -> DeliveryResult:
        dest = to_e164(to)
        frm = (settings.TWILIO_SMS_FROM or "").strip()
        if not dest:
            return DeliveryResult(status=DeliveryStatus.FAILED, detail="Invalid SMS destination")
        if not frm:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="TWILIO_SMS_FROM is not configured",
            )
        return send_twilio_message(frm=frm, to=dest, body=body)


class TwilioWhatsAppProvider(WhatsAppProvider):
    def send_text(self, to: str, body: str) -> DeliveryResult:
        frm = (settings.TWILIO_WHATSAPP_FROM or "").strip()
        if not frm:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="TWILIO_WHATSAPP_FROM is not configured",
            )
        return send_twilio_message(frm=_whatsapp_addr(frm), to=_whatsapp_addr(to), body=body)

    def send_template(self, to: str, message: WhatsAppTemplateMessage) -> DeliveryResult:
        parts = [message.template_name]
        if message.body_params:
            parts.extend(str(p) for p in message.body_params)
        return self.send_text(to, "\n".join(parts))
