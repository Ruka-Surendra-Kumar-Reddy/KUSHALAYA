"""Website "Buy now" on the care plans — public, no login. Logic: app/livewell/plan_purchase_service.py.

The Razorpay webhook stays on the one existing URL (/home-safety/family/wallet/webhook),
which hands plan orders to plan_purchase_service.settle_webhook.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell import plan_purchase_service as svc
from app.livewell.public_enquiry_service import normalise_pincode
from app.services.login_throttle import client_ip

router = APIRouter(prefix="/home-safety/plan-purchases", tags=["Safe Home — Website plan purchases"])

#: Coupon checks per IP per minute (stops guessing codes).
QUOTE_LIMIT = 20
QUOTE_WINDOW_SECONDS = 60
_quote_hits: dict[str, list[float]] = {}


def _assert_quote_rate(request: Request) -> None:
    now = time.monotonic()
    key = client_ip(request)
    cutoff = now - QUOTE_WINDOW_SECONDS
    hits = [t for t in _quote_hits.get(key, []) if t > cutoff]
    if len(hits) >= QUOTE_LIMIT:
        _quote_hits[key] = hits
        raise HTTPException(status_code=429, detail="Too many tries. Please wait a minute.")
    hits.append(now)
    _quote_hits[key] = hits
    if len(_quote_hits) > 5000:
        for k in [k for k, v in _quote_hits.items() if not v or v[-1] <= cutoff]:
            _quote_hits.pop(k, None)


def _ip(request: Request) -> str | None:
    ip = client_ip(request)
    return None if ip == "unknown" else ip


class QuoteIn(BaseModel):
    plan_id: str = Field(..., max_length=40)
    billing_cycle: str = Field(..., max_length=10)
    coupon_code: str | None = Field(None, max_length=40)


class PurchaseIn(QuoteIn):
    name: str = Field(..., max_length=200)
    phone: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=300)
    area: str | None = Field(None, max_length=600)
    pincode: str | None = Field(None, max_length=12)
    accept_terms: bool = False
    #: Hidden field; bots fill it, humans never see it.
    company: str | None = None
    utm_source: str | None = Field(None, max_length=200)
    utm_medium: str | None = Field(None, max_length=200)
    utm_campaign: str | None = Field(None, max_length=200)
    referrer: str | None = Field(None, max_length=1000)
    landing_page: str | None = Field(None, max_length=1000)
    ref: str | None = Field(None, max_length=40)
    # Pay-as-you-go visit only (plan_id "single-visit", billing_cycle "once").
    need: str | None = Field(None, max_length=40)
    need_note: str | None = Field(None, max_length=600)
    preferred_date: str | None = Field(None, max_length=10)
    time_of_day: str | None = Field(None, max_length=20)

    @field_validator("pincode", mode="before")
    @classmethod
    def _pincode(cls, v):
        return normalise_pincode(v) if isinstance(v, str) else v


class VerifyIn(BaseModel):
    order_id: str = Field(..., max_length=64)
    payment_id: str = Field(..., max_length=64)
    signature: str = Field(..., max_length=200)


@router.post("/quote")
def quote(data: QuoteIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Price with an optional coupon ("Apply"). Nothing is saved."""
    _assert_quote_rate(request)
    return svc.quote(db, plan_id=data.plan_id, billing_cycle=data.billing_cycle, coupon_code=data.coupon_code)


@router.post("")
def start_purchase(data: PurchaseIn, request: Request, db: Session = Depends(get_db)) -> dict:
    """Validates the plan / cycle / coupon here (never the browser's amount) and returns a
    Razorpay order — or, without a live gateway, a message and a saved lead.
    Limited per IP per hour in the service (like website enquiries)."""
    return svc.start(
        db,
        plan_id=data.plan_id,
        billing_cycle=data.billing_cycle,
        name=data.name,
        phone=data.phone,
        email=data.email,
        area=data.area,
        pincode=data.pincode,
        coupon_code=data.coupon_code,
        accept_terms=data.accept_terms,
        honeypot=data.company,
        source_ip=_ip(request),
        lead_extra={
            "utm_source": data.utm_source,
            "utm_medium": data.utm_medium,
            "utm_campaign": data.utm_campaign,
            "referrer": data.referrer,
            "landing_page": data.landing_page,
            "ref": data.ref,
        },
        need=data.need,
        need_note=data.need_note,
        preferred_date=data.preferred_date,
        time_of_day=data.time_of_day,
    )


@router.post("/{reference}/verify")
def verify(reference: str, data: VerifyIn, db: Session = Depends(get_db)) -> dict:
    """Browser checkout callback (signature checked). The webhook is the backstop."""
    return svc.verify(db, reference, order_id=data.order_id, payment_id=data.payment_id, signature=data.signature)
