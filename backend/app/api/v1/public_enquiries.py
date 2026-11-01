"""Public website enquiry intake — no authentication.

Mounted under the Safe Home prefix so nginx already routes it. Every enquiry
lands in the prospect pipeline as a NEW elder prospect.
"""

import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell.public_enquiry_service import PublicEnquiryService, normalise_phone, normalise_pincode
from app.livewell.visit_service import _visits_raw
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.services.login_throttle import client_ip

router = APIRouter(prefix="/home-safety/enquiries", tags=["Safe Home — Public enquiries"])


class PublicEnquiryRequest(BaseModel):
    name: str = Field(..., max_length=200)
    phone: str | None = Field(None, max_length=60)
    email: EmailStr | None = Field(None, max_length=300)
    area: str | None = Field(None, max_length=600)
    services: list[str] | None = None
    visit_frequency: str | None = Field(None, max_length=200)
    products: list[str] | None = None
    notes: str | None = Field(None, max_length=5000)
    #: KushCare Discovery: who the help is for (Parent, Spouse, Myself…).
    for_whom: str | None = Field(None, max_length=40)
    #: "care-check" or "custom-plan" — where the enquiry came from.
    kind: str = Field("care-check", max_length=40)
    #: Hidden field; bots fill it, humans never see it.
    company: str | None = None
    # --- Lead tracking (FIX 107/108) ---
    pincode: str | None = Field(None, max_length=12)
    utm_source: str | None = Field(None, max_length=200)
    utm_medium: str | None = Field(None, max_length=200)
    utm_campaign: str | None = Field(None, max_length=200)
    referrer: str | None = Field(None, max_length=1000)
    landing_page: str | None = Field(None, max_length=1000)
    #: Where the visitor came from (?src=qr on standees); unknown values → "website".
    src: str | None = Field(None, max_length=40)
    #: Referral code from a family's /r/<code> link.
    ref: str | None = Field(None, max_length=40)
    #: KushCare Discovery slot: "YYYY-MM-DD" + morning / afternoon / evening.
    slot_date: str | None = Field(None, max_length=10)
    slot_window: str | None = Field(None, max_length=20)

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, v):
        # Indian mobile (+91/0 optional) or an international E.164 number.
        return normalise_phone(v) if isinstance(v, str) else v

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            if "@" not in v or "." not in v.rsplit("@", 1)[-1]:
                raise ValueError("Please check the email address (for example name@gmail.com).")
        return v

    @field_validator("pincode", mode="before")
    @classmethod
    def _pincode(cls, v):
        return normalise_pincode(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def _custom_plan_needs_a_choice(self):
        if self.kind == "custom-plan":
            chosen = [x for x in (self.services or []) + (self.products or []) if str(x).strip()]
            if not chosen and not (self.visit_frequency or "").strip():
                raise ValueError("Please pick at least one service, visit frequency or product for your custom plan.")
        return self


class PublicEnquiryResponse(BaseModel):
    ok: bool
    reference: str
    #: "We serve your area" / "We'll call to check" when a PIN code was given.
    area_message: str | None = None
    area_served: bool | None = None
    #: Razorpay order when the assessment has a price; null when free.
    payment: dict | None = None
    #: Set when a priced slot could not be paid online (pay at the visit instead).
    payment_message: str | None = None


def _client_ip(request: Request) -> str | None:
    """Real client address; only the local nginx may supply it (spoof-proof)."""
    ip = client_ip(request)
    return None if ip == "unknown" else ip


@router.post("", response_model=PublicEnquiryResponse, response_model_exclude_none=True)
def create_public_enquiry(
    data: PublicEnquiryRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    row = PublicEnquiryService.create(
        db,
        name=data.name,
        phone=data.phone,
        email=data.email,
        area=data.area,
        services=data.services,
        visit_frequency=data.visit_frequency,
        products=data.products,
        notes=(f"For: {data.for_whom.strip()[:40]}\n" if data.for_whom and data.for_whom.strip() else "") + (data.notes or ""),
        kind=data.kind,
        honeypot=data.company,
        source_ip=_client_ip(request),
        lead={
            "pincode": data.pincode,
            "utm_source": data.utm_source,
            "utm_medium": data.utm_medium,
            "utm_campaign": data.utm_campaign,
            "referrer": data.referrer,
            "landing_page": data.landing_page,
            "ref": data.ref,
            "slot_date": data.slot_date,
            "slot_window": data.slot_window,
        },
        src=data.src,
    )
    payment = PublicEnquiryService.start_assessment_payment(db, row)
    # Only a reference goes back — never the stored record.
    return PublicEnquiryResponse(
        ok=True,
        reference=f"KA-{row.id:06d}",
        area_served=row.area_served,
        area_message=(
            None
            if row.area_served is None
            else "We serve your area." if row.area_served else "We'll call to check we can reach your area."
        ),
        payment=payment,
        payment_message=(
            "Online payment isn't available right now. Your slot is booked — "
            "you can pay at the visit and we'll confirm by phone."
            if payment is None and row.assessment_slot and row.assessment_fee_paise else None
        ),
    )


# --- Website settings the public pages read (FIX 107/108) ---------------------


def _site_tenant(db: Session):
    from app.models.tenant import Tenant

    return db.query(Tenant).order_by(Tenant.id).first()


@router.get("/site")
def public_site_config(db: Session = Depends(get_db)) -> dict:
    """WhatsApp number, assessment price label, trial banner, real testimonials,
    company details. Nothing private: no pincode lists, no user ids."""
    from app.livewell.site_settings import public_config

    return public_config(_site_tenant(db))


#: Light in-memory limit on the public PIN checker (per process, per IP).
PINCODE_CHECK_LIMIT = 30
PINCODE_CHECK_WINDOW_SECONDS = 60
_pincode_hits: dict[str, list[float]] = {}


def _assert_pincode_rate(request: Request) -> None:
    from fastapi import HTTPException

    now = time.monotonic()
    key = client_ip(request)
    cutoff = now - PINCODE_CHECK_WINDOW_SECONDS
    hits = [t for t in _pincode_hits.get(key, []) if t > cutoff]
    if len(hits) >= PINCODE_CHECK_LIMIT:
        _pincode_hits[key] = hits
        raise HTTPException(status_code=429, detail="Too many checks. Please try again in a minute.")
    hits.append(now)
    _pincode_hits[key] = hits
    if len(_pincode_hits) > 5000:  # keep memory bounded
        for k in [k for k, v in _pincode_hits.items() if not v or v[-1] <= cutoff]:
            _pincode_hits.pop(k, None)


@router.get("/pincode/{pincode}")
def public_pincode_check(pincode: str, request: Request, db: Session = Depends(get_db)) -> dict:
    from app.livewell.site_settings import check_pincode

    _assert_pincode_rate(request)

    result = check_pincode(_site_tenant(db), pincode[:12])
    result.pop("manager_user_id", None)
    return result


class AssessmentPaymentVerify(BaseModel):
    order_id: str = Field(..., max_length=64)
    payment_id: str = Field(..., max_length=64)
    signature: str = Field(..., max_length=200)


@router.post("/{reference}/payment")
def verify_assessment_payment(reference: str, body: AssessmentPaymentVerify, db: Session = Depends(get_db)) -> dict:
    """Browser checkout callback for a paid assessment slot. The webhook is the backstop."""
    from fastapi import HTTPException

    from app.models.elder_prospect import ElderProspect
    from app.services.payments.factory import get_payment_provider

    from app.services.payments.factory import stub_in_production

    digits = "".join(ch for ch in reference if ch.isdigit())
    # References are KA-NNNNNN; a huge number would overflow the integer key.
    if not digits or len(digits) > 9:
        raise HTTPException(status_code=404, detail="Booking not found")
    row = db.get(ElderProspect, int(digits))
    if row is None or not row.assessment_order_id or row.assessment_order_id != body.order_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    provider = get_payment_provider()
    if stub_in_production():  # a stub "payment" is never real money
        raise HTTPException(status_code=400, detail="Payment could not be verified")
    if not provider.verify_checkout_signature(
        order_id=body.order_id, payment_id=body.payment_id, signature=body.signature
    ):
        raise HTTPException(status_code=400, detail="Payment could not be verified")
    PublicEnquiryService.mark_assessment_paid(db, row, payment_id=body.payment_id)
    return {"ok": True, "reference": f"KA-{row.id:06d}", "paid": True}


# --- Public counters for the marketing site -------------------------------

class PublicStatsResponse(BaseModel):
    families: int
    visits: int
    assessments: int
    #: Partners live in per-tenant stored config, not a table; the site keeps
    #: its own figure when this is null.
    partners: int | None = None


_STATS_TTL_SECONDS = 300
_stats_cache: dict[str, object] = {"at": 0.0, "value": None}


@router.get("/stats", response_model=PublicStatsResponse)
def public_stats(db: Session = Depends(get_db)) -> PublicStatsResponse:
    """Aggregate counts shown on www — no tenant data, no names, cached 5 min.

    Only totals leave this endpoint, and they are rounded down to the nearest
    5 so the public figure never reveals a single new sign-up.
    """
    now = time.time()
    cached = _stats_cache["value"]
    if cached is not None and now - float(_stats_cache["at"]) < _STATS_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    def floor5(n: int) -> int:
        return (n // 5) * 5

    def safe(fn) -> int:
        # A public page must never 500 because one table is missing or a row
        # is malformed — a failed count is reported as 0 and the site falls
        # back to its static promises (it only shows live numbers >= 25).
        try:
            return int(fn() or 0)
        except Exception:  # noqa: BLE001
            db.rollback()
            return 0

    # Only the tenant the public site belongs to — never other agencies on the VM.
    site = _site_tenant(db)
    tenant_id = site.id if site is not None else -1

    def count_visits() -> int:
        # Safe Home visits are stored on each elder (custom_attributes.safe_home.visits).
        total = 0
        for elder in db.query(Elder).filter(Elder.status == "ACTIVE", Elder.tenant_id == tenant_id).all():
            total += len(_visits_raw(elder))
        return total

    families = safe(
        lambda: db.scalar(
            select(func.count()).select_from(Elder).where(Elder.status == "ACTIVE", Elder.tenant_id == tenant_id)
        )
    )
    visits = safe(count_visits)
    assessments = safe(
        lambda: db.scalar(
            select(func.count())
            .select_from(HomeSafetyAssessmentRecord)
            .where(HomeSafetyAssessmentRecord.tenant_id == tenant_id)
        )
    )
    value = PublicStatsResponse(
        families=floor5(int(families)),
        visits=floor5(int(visits)),
        assessments=floor5(int(assessments)),
        partners=None,
    )
    _stats_cache["at"] = now
    _stats_cache["value"] = value
    return value
