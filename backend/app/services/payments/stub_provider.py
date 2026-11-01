"""Local stub gateway — no network, no real money.

Used for dev and demo tenants so the wallet flow is walkable without Razorpay
keys. Recharges started through this provider are settled by the app itself
rather than by a webhook.
"""

from __future__ import annotations

import uuid

from app.services.payments.base import PaymentOrder, PaymentProvider, WebhookEvent


class StubPaymentProvider(PaymentProvider):
    name = "stub"

    def create_order(
        self,
        *,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: dict | None = None,
    ) -> PaymentOrder:
        return PaymentOrder(
            order_id=f"order_stub_{uuid.uuid4().hex[:14]}",
            amount_minor=int(amount_minor),
            currency=currency,
            provider=self.name,
            public_key="",
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> WebhookEvent:
        raise NotImplementedError("The stub provider does not receive webhooks")

    def verify_checkout_signature(
        self,
        *,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        # Never accept a stub "payment" as real money on a production server.
        from app.services.payments.factory import is_production

        return not is_production()
