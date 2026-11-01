"""Family wallet request/response shapes.

Amounts cross the wire as integer minor units (`*_minor`, paise) plus a
preformatted display string, so no client ever does money arithmetic in
floating point.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WalletBalanceResponse(BaseModel):
    elder_id: int
    balance_minor: int
    balance_display: str
    currency: str = "INR"
    status: str = "active"
    min_recharge_minor: int
    max_recharge_minor: int


class WalletTransactionResponse(BaseModel):
    id: str
    kind: str
    amount_minor: int
    amount_display: str
    balance_after_minor: int | None = None
    currency: str = "INR"
    status: str
    reference_type: str | None = None
    reference_id: str | None = None
    note: str | None = None
    created_at: datetime | None = None


class WalletRechargeCreate(BaseModel):
    amount_minor: int = Field(gt=0, description="Top-up amount in paise")
    # Set when the top-up is for "Approve & pay" — the quote is paid once the money lands.
    quote_order_id: int | None = None


class WalletRechargeResponse(BaseModel):
    transaction_id: str
    order_id: str
    amount_minor: int
    currency: str
    provider: str
    public_key: str = ""
    status: str


class WalletRechargeSettleRequest(BaseModel):
    """Stub-provider settlement (dev/demo only)."""

    transaction_id: str


class WalletRechargeVerifyRequest(BaseModel):
    """The three fields Razorpay Checkout hands back on success."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ServiceRequestPayRequest(BaseModel):
    """Family approving a staff-quoted price, paid from the wallet."""

    request_id: str
