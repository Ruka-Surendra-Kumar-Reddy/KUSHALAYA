"""Razorpay orders + webhook verification.

Razorpay signs webhooks as HMAC-SHA256(raw_body, webhook_secret) in the
`X-Razorpay-Signature` header, and the browser checkout callback as
HMAC-SHA256("<order_id>|<payment_id>", key_secret). Both are compared in
constant time.

The raw request body must be passed through byte-for-byte — re-serializing
parsed JSON changes the bytes and the signature will never match.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx

from app.core.config import settings
from app.core.responses import raise_bad_request
from app.services.payments.base import PaymentOrder, PaymentProvider, WebhookEvent

logger = logging.getLogger(__name__)

RAZORPAY_API = "https://api.razorpay.com/v1"
REQUEST_TIMEOUT_SECONDS = 20.0


def _signature(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class RazorpayProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self) -> None:
        self._key_id = (settings.RAZORPAY_KEY_ID or "").strip()
        self._key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
        self._webhook_secret = (settings.RAZORPAY_WEBHOOK_SECRET or "").strip()

    def _require_keys(self) -> None:
        if not self._key_id or not self._key_secret:
            raise_bad_request("Payments are not configured — contact support")

    def create_order(
        self,
        *,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: dict | None = None,
    ) -> PaymentOrder:
        self._require_keys()
        payload = {
            "amount": int(amount_minor),
            "currency": currency,
            "receipt": receipt[:40],
            "payment_capture": 1,
            "notes": notes or {},
        }
        try:
            response = httpx.post(
                f"{RAZORPAY_API}/orders",
                json=payload,
                auth=(self._key_id, self._key_secret),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError:
            logger.exception("Razorpay order request failed")
            raise_bad_request("Could not reach the payment provider — try again")

        if response.status_code in (401, 403):
            # Our credentials are wrong, not the family's fault. Most common cause
            # is regenerating the key secret in the dashboard without updating
            # RAZORPAY_KEY_SECRET here — the key id stays the same, so this is
            # easy to miss.
            logger.error(
                "Razorpay authentication failed (status=%s) for key_id=%s — check "
                "RAZORPAY_KEY_SECRET matches the current secret in the dashboard. body=%s",
                response.status_code,
                self._key_id,
                response.text[:300],
            )
            raise_bad_request(
                "Payments are temporarily unavailable. The care team has been notified."
            )

        if response.status_code >= 400:
            # Gateway errors can carry cardholder detail; keep it out of the client.
            logger.error(
                "Razorpay order rejected: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise_bad_request("Payment provider rejected the request")

        body = response.json()
        return PaymentOrder(
            order_id=str(body.get("id") or ""),
            amount_minor=int(body.get("amount") or amount_minor),
            currency=str(body.get("currency") or currency),
            provider=self.name,
            public_key=self._key_id,
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> WebhookEvent:
        if not self._webhook_secret:
            raise_bad_request("Webhook secret is not configured")
        expected = _signature(self._webhook_secret, payload)
        if not hmac.compare_digest(expected, (signature or "").strip()):
            # Never say which part failed.
            raise_bad_request("Invalid webhook signature")

        try:
            body = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise_bad_request("Malformed webhook payload")

        entity = (
            body.get("payload", {}).get("payment", {}).get("entity", {})
            if isinstance(body.get("payload"), dict)
            else {}
        )
        return WebhookEvent(
            event=str(body.get("event") or ""),
            order_id=str(entity.get("order_id") or "") or None,
            payment_id=str(entity.get("id") or "") or None,
            amount_minor=int(entity["amount"]) if entity.get("amount") is not None else None,
            raw=body,
        )

    def verify_checkout_signature(
        self,
        *,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        if not self._key_secret:
            return False
        expected = _signature(self._key_secret, f"{order_id}|{payment_id}".encode("utf-8"))
        return hmac.compare_digest(expected, (signature or "").strip())
