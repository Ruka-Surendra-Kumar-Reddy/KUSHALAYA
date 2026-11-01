"""Telegram bot alerts — free lab channel (BotFather token, no DLT / trial)."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.notifications.types import DeliveryResult, DeliveryStatus

logger = logging.getLogger(__name__)


def telegram_chat_ids() -> list[str]:
    raw = (settings.TELEGRAM_CHAT_ID or "").strip()
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        chat = part.strip()
        if chat and chat not in seen:
            seen.add(chat)
            out.append(chat)
    return out


def send_telegram_message(text: str, *, chat_id: str | None = None) -> DeliveryResult:
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            detail="TELEGRAM_BOT_TOKEN is not configured",
        )
    dest = (chat_id or "").strip()
    if not dest:
        ids = telegram_chat_ids()
        dest = ids[0] if ids else ""
    if not dest:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            detail="TELEGRAM_CHAT_ID is not configured",
        )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                url,
                json={"chat_id": dest, "text": text, "disable_web_page_preview": True},
            )
        data = response.json() if response.content else {}
        if not data.get("ok"):
            detail = str(data.get("description") or response.text)[:400]
            logger.warning("telegram_send_failed chat=%s detail=%s", dest, detail)
            return DeliveryResult(status=DeliveryStatus.FAILED, detail=detail)
        logger.info("telegram_sent chat=%s", dest)
        return DeliveryResult(status=DeliveryStatus.SENT)
    except Exception as exc:
        logger.exception("telegram_send_failed chat=%s", dest)
        return DeliveryResult(status=DeliveryStatus.FAILED, detail=str(exc)[:500])
