import logging

import httpx

from app.core.config import settings
from app.services.notifications.base import SmsProvider
from app.services.notifications.types import DeliveryResult, DeliveryStatus

logger = logging.getLogger(__name__)

MSG91_SEND_URL = "https://control.msg91.com/api/sendhttp.php"


class Msg91SmsProvider(SmsProvider):
    """MSG91 transactional SMS (India). Configure DLT sender + template in MSG91 console."""

    def __init__(self, cfg: dict | None = None):
        # cfg comes from Settings → Email & SMS (channel_config); otherwise .env.
        cfg = cfg or {}
        self.auth_key = cfg.get("auth_key") or settings.MSG91_AUTH_KEY
        self.sender_id = cfg.get("sender_id") or settings.MSG91_SENDER_ID
        self.route = cfg.get("route") or settings.MSG91_ROUTE
        self.template_id = cfg.get("template_id") or settings.MSG91_TEMPLATE_ID

    def send(self, to: str, body: str) -> DeliveryResult:
        if not self.auth_key:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="MSG91_AUTH_KEY is not configured",
            )
        if not self.sender_id:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="MSG91_SENDER_ID is not configured",
            )

        params = {
            "authkey": self.auth_key,
            "mobiles": to,
            "message": body,
            "sender": self.sender_id,
            "route": self.route,
            "country": "91",
        }
        if self.template_id:
            params["DLT_TE_ID"] = self.template_id

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(MSG91_SEND_URL, params=params)
            response.raise_for_status()
            text = (response.text or "").strip()
            if text.isdigit() and len(text) >= 20:
                logger.info("msg91_sms_sent to=%s request_id=%s", to, text)
                return DeliveryResult(status=DeliveryStatus.SENT, detail=text)
            logger.warning("msg91_sms_response to=%s body=%s", to, text[:200])
            return DeliveryResult(
                status=DeliveryStatus.SENT,
                detail=text[:500] or None,
            )
        except Exception as exc:
            logger.exception("msg91_sms_failed to=%s", to)
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail=str(exc)[:500],
            )
