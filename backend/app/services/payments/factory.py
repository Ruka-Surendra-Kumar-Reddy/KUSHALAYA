"""Resolve the configured payment provider."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services.payments.base import PaymentProvider
from app.services.payments.razorpay_provider import RazorpayProvider
from app.services.payments.stub_provider import StubPaymentProvider

logger = logging.getLogger(__name__)


def is_production() -> bool:
    return (settings.ENVIRONMENT or "").strip().lower() in {"production", "prod"}


def stub_in_production() -> bool:
    """True when production would fall back to the stub (no real gateway)."""
    return is_production() and (settings.PAYMENTS_PROVIDER or "stub").strip().lower() != "razorpay"


def get_payment_provider() -> PaymentProvider:
    name = (settings.PAYMENTS_PROVIDER or "stub").strip().lower()
    if name == "razorpay":
        return RazorpayProvider()
    if is_production():
        logger.warning(
            "Wallet is running on the stub payment provider in production — "
            "set PAYMENTS_PROVIDER=razorpay with live keys."
        )
    return StubPaymentProvider()
