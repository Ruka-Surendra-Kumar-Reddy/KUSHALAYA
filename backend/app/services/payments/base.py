"""Payment provider interface — one implementation per gateway."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentOrder:
    """A gateway-side order the family app can hand to a checkout widget."""

    order_id: str
    amount_minor: int
    currency: str
    provider: str
    # Publishable key for the client SDK — never the secret.
    public_key: str = ""


@dataclass(frozen=True)
class WebhookEvent:
    """A verified inbound gateway event."""

    event: str
    order_id: str | None
    payment_id: str | None
    amount_minor: int | None
    raw: dict


class PaymentProvider:
    name = "base"

    def create_order(
        self,
        *,
        amount_minor: int,
        currency: str,
        receipt: str,
        notes: dict | None = None,
    ) -> PaymentOrder:
        raise NotImplementedError

    def verify_webhook(self, *, payload: bytes, signature: str) -> WebhookEvent:
        """Verify the signature and parse the event. Raises if not authentic."""
        raise NotImplementedError

    def verify_checkout_signature(
        self,
        *,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """Verify the client-side checkout callback.

        This is a convenience check only — it confirms the browser payload was
        not tampered with, but the wallet is credited from the webhook, which
        is the authoritative source.
        """
        raise NotImplementedError
