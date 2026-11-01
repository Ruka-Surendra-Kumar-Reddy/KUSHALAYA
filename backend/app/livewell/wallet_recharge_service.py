"""Recharge orchestration — gateway order in, verified credit out.

Flow:
    1. Family taps "Add money" → `start` creates a *pending* ledger entry and a
       gateway order. Pending entries do not move the balance.
    2. Family pays in the checkout widget.
    3. The gateway calls `/wallet/webhook` → signature verified → the matching
       pending entry is settled to success and the balance moves.

The browser callback is never trusted to credit the wallet; it only tells the
UI to start polling. A family that closes the app mid-payment still gets
credited, because the webhook is what settles.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.wallet_service import WalletService
from app.models.family_wallet import WalletTransaction
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService
from app.services.payments import get_payment_provider

logger = logging.getLogger(__name__)

# Razorpay fires several payment events; only a captured payment is money in hand.
SUCCESS_EVENTS = frozenset({"payment.captured"})
FAILURE_EVENTS = frozenset({"payment.failed"})


def _autopay(db: Session, entry: WalletTransaction) -> WalletTransaction:
    """A top-up started from "Approve & pay" pays its quote as soon as the money lands."""
    from app.livewell.commerce import pay_quote_after_topup

    pay_quote_after_topup(db, entry)
    return entry


class WalletRechargeService:
    @staticmethod
    def start(db: Session, user: User, *, amount_minor: int, quote_order_id: int | None = None) -> dict:
        minimum = int(settings.WALLET_MIN_RECHARGE_MINOR)
        maximum = int(settings.WALLET_MAX_RECHARGE_MINOR)
        if amount_minor < minimum:
            raise_bad_request(f"Minimum recharge is ₹{minimum // 100:,}")
        if amount_minor > maximum:
            raise_bad_request(f"Maximum recharge is ₹{maximum // 100:,}")

        elder = ElderPortalService.get_linked_elder(db, user)
        wallet = WalletService.get_or_create(db, elder)

        reference_type = reference_id = None
        if quote_order_id:
            from app.models.commerce import Order

            quote = db.get(Order, int(quote_order_id))
            if not quote or quote.elder_id != elder.id or quote.status != "quoted":
                raise_bad_request("This quote is no longer open")
            reference_type, reference_id = "quote_topup", str(quote.id)

        provider = get_payment_provider()
        receipt = f"wal{wallet.id}-{uuid.uuid4().hex[:10]}"
        order = provider.create_order(
            amount_minor=amount_minor,
            currency=wallet.currency,
            receipt=receipt,
            notes={"wallet_id": str(wallet.id), "elder_id": str(elder.id)},
        )

        entry = WalletService.record(
            db,
            wallet,
            kind="recharge",
            amount_minor=amount_minor,
            idempotency_key=f"recharge:{order.order_id}",
            status="pending",
            gateway=order.provider,
            gateway_order_id=order.order_id,
            note="Wallet top-up" + (f" to pay quote #{reference_id}" if reference_id else ""),
            reference_type=reference_type,
            reference_id=reference_id,
            user=user,
        )

        return {
            "transaction_id": entry.public_id,
            "order_id": order.order_id,
            "amount_minor": amount_minor,
            "currency": order.currency,
            "provider": order.provider,
            "public_key": order.public_key,
            "status": entry.status,
        }

    @staticmethod
    def handle_webhook(db: Session, *, payload: bytes, signature: str) -> dict:
        """Verify and apply a gateway webhook. Safe to receive repeatedly."""
        provider = get_payment_provider()
        try:
            event = provider.verify_webhook(payload=payload, signature=signature)
        except NotImplementedError:
            # No gateway configured — reject cleanly rather than 500ing, so a
            # stray or probing call does not look like an app crash.
            logger.warning("Webhook received while provider=%s has no webhook support", provider.name)
            raise_bad_request("Webhooks are not enabled for this payment provider")

        if not event.order_id:
            # Nothing to match against; ack so the gateway stops retrying.
            return {"status": "ignored", "reason": "no order id"}

        entry = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.gateway_order_id == event.order_id,
                WalletTransaction.kind == "recharge",
            )
            .first()
        )
        if entry is None:
            # A paid KushCare Discovery slot from the website (FIX 107)?
            from app.livewell.public_enquiry_service import PublicEnquiryService

            settled = PublicEnquiryService.settle_assessment_webhook(db, event)
            if settled is not None:
                return settled
            # A care plan bought with "Buy now" on the website (30 Oct 2026)?
            from app.livewell.plan_purchase_service import settle_webhook

            settled = settle_webhook(db, event)
            if settled is not None:
                return settled
            logger.warning("Webhook for unknown order_id=%s", event.order_id)
            return {"status": "ignored", "reason": "unknown order"}

        if entry.status != "pending":
            return {"status": "already_settled", "transaction_id": entry.public_id}

        if event.event in FAILURE_EVENTS:
            WalletService.settle_pending(db, entry, status="failed")
            return {"status": "failed", "transaction_id": entry.public_id}

        if event.event not in SUCCESS_EVENTS:
            return {"status": "ignored", "reason": f"unhandled event {event.event}"}

        # Guard against a captured amount that does not match what we recorded.
        if event.amount_minor is not None and int(event.amount_minor) != int(entry.amount_minor):
            logger.error(
                "Webhook amount mismatch order_id=%s expected=%s got=%s",
                event.order_id,
                entry.amount_minor,
                event.amount_minor,
            )
            return {"status": "ignored", "reason": "amount mismatch"}

        WalletService.settle_pending(
            db,
            entry,
            status="success",
            gateway_payment_id=event.payment_id,
        )
        _autopay(db, entry)
        return {"status": "credited", "transaction_id": entry.public_id}

    @staticmethod
    def verify_checkout(
        db: Session,
        user: User,
        *,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> WalletTransaction:
        """Settle a recharge from the browser checkout callback.

        The webhook is still the backstop — a family that closes the tab mid-payment
        gets credited by it. This path exists so the balance updates immediately
        while they are looking at the screen, instead of after webhook latency.
        Both routes call the same idempotent settle, so whichever lands second is
        a no-op rather than a second credit.
        """
        if not order_id or not payment_id or not signature:
            raise_bad_request("Missing payment details")

        provider = get_payment_provider()
        if not provider.verify_checkout_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
        ):
            logger.warning("Checkout signature rejected for order_id=%s", order_id)
            raise_bad_request("Payment could not be verified")

        # Scope the lookup to this family's own wallet so a valid signature for
        # someone else's order cannot settle it from this session.
        elder = ElderPortalService.get_linked_elder(db, user)
        wallet = WalletService.get_or_create(db, elder)
        entry = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet.id,
                WalletTransaction.gateway_order_id == order_id,
                WalletTransaction.kind == "recharge",
            )
            .first()
        )
        if entry is None:
            raise_not_found("Recharge not found")

        return _autopay(db, WalletService.settle_pending(
            db,
            entry,
            status="success",
            gateway_payment_id=payment_id,
        ))

    @staticmethod
    def settle_stub(db: Session, user: User, *, transaction_id: str) -> WalletTransaction:
        """Dev/demo only — settle a stub recharge without a real gateway."""
        provider = get_payment_provider()
        if provider.name != "stub":
            raise_bad_request("This endpoint is only available on the stub provider")

        elder = ElderPortalService.get_linked_elder(db, user)
        wallet = WalletService.get_or_create(db, elder)
        entry = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet.id,
                WalletTransaction.public_id == transaction_id,
            )
            .first()
        )
        if entry is None:
            raise_not_found("Recharge not found")
        return _autopay(db, WalletService.settle_pending(
            db,
            entry,
            status="success",
            gateway_payment_id=f"pay_stub_{uuid.uuid4().hex[:14]}",
        ))
