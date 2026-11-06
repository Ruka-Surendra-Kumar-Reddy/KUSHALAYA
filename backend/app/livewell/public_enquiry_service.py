"""Public website enquiries — the Parent Care Check and custom plan forms.

These arrive from an unauthenticated page, so the service is deliberately
defensive:

* every field is length-capped before it reaches the database
* a hidden honeypot field rejects the majority of bots without a challenge
* the same IP is limited per hour, so a script cannot flood the pipeline
* the response never echoes stored data back, only a reference

An enquiry becomes an ``ElderProspect`` at stage ``NEW`` so it lands in the
pipeline the ops team already works from, rather than a second inbox nobody
watches.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.elder_prospect import ElderProspect
from app.models.tenant import Tenant

#: Enquiries accepted from one IP per hour.
RATE_LIMIT_PER_HOUR = 5

#: Caps applied before anything is stored.
MAX_NAME = 100
MAX_PHONE = 50
MAX_EMAIL = 255
MAX_AREA = 500
MAX_NOTES = 4000
MAX_LIST_ITEMS = 40
MAX_LIST_ITEM = 120


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: str | None, limit: int) -> str:
    return (value or "").strip()[:limit]


#: Enquiry channels a page may claim with ?src= (qr = printed standee QR code).
SOURCE_CHANNELS = ("website", "qr", "whatsapp", "google", "referral", "direct")


def source_channel(src: str | None) -> str:
    """Allow-listed channel for the prospect's source; anything else is "website"."""
    v = (src or "").strip().lower()
    return v if v in SOURCE_CHANNELS else "website"


_INDIAN_MOBILE_RE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_PINCODE_RE = re.compile(r"^[1-8]\d{5}$")

PHONE_ERROR = "Please enter a 10-digit Indian mobile number, or an international number starting with + and the country code."
PINCODE_ERROR = "Please enter a 6-digit PIN code (for example 500081)."


def normalise_phone(raw: str | None) -> str | None:
    """Indian mobile (10 digits, optional +91/91/0) -> "+91 XXXXX XXXXX";
    any other country in E.164 -> "+<digits>". Spaces, dashes, dots and
    brackets are allowed. Blank -> None. Anything else raises ValueError."""
    text = (raw or "").strip()
    if not text:
        return None
    compact = re.sub(r"[\s\-().]", "", text)
    m = _INDIAN_MOBILE_RE.match(compact)
    if m:
        d = m.group(1)
        return f"+91 {d[:5]} {d[5:]}"
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if _E164_RE.match(compact) and not compact.startswith("+91"):
        return compact
    raise ValueError(PHONE_ERROR)


EMAIL_ERROR = "Please check the email address (for example name@gmail.com)."
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def normalise_email(raw: str | None) -> str | None:
    """Trimmed, lower-cased email. Blank -> None. Junk raises ValueError."""
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) > MAX_EMAIL or not _EMAIL_RE.match(text):
        raise ValueError(EMAIL_ERROR)
    return text.lower()


def validate_contact(phone: str | None, email: str | None) -> tuple[str | None, str | None]:
    """Server-side check for any enquiry (public form or staff-added).
    Returns the normalised (phone, email); junk -> 422 with a friendly message."""
    try:
        clean_phone = normalise_phone(phone)
        clean_email = normalise_email(email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return clean_phone, clean_email


def normalise_pincode(raw: str | None) -> str | None:
    """Indian PIN: 6 digits, first digit 1-8 (spaces allowed). Blank -> None."""
    compact = re.sub(r"\s", "", raw or "")
    if not compact:
        return None
    if not _PINCODE_RE.match(compact):
        raise ValueError(PINCODE_ERROR)
    return compact


def _clean_list(values: list[str] | None, *, limit: int = MAX_LIST_ITEMS) -> list[str]:
    out: list[str] = []
    for v in values or []:
        text = _clean(v, MAX_LIST_ITEM)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


class PublicEnquiryService:
    @staticmethod
    def _assert_not_bot(honeypot: str | None) -> None:
        """A hidden field no human fills in. Silently reject when it has a value."""
        if (honeypot or "").strip():
            # Deliberately the same shape as a success to avoid teaching bots.
            raise HTTPException(status_code=422, detail="Could not accept this enquiry.")

    @staticmethod
    def _assert_rate_limit(db: Session, *, source_ip: str | None) -> None:
        if not source_ip:
            return
        since = _utcnow() - timedelta(hours=1)
        count = (
            db.query(ElderProspect)
            .filter(
                ElderProspect.source_ip == source_ip,
                ElderProspect.created_at >= since,
            )
            .count()
        )
        if count >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail="Too many enquiries from this connection. Please try again later, "
                "or call us instead.",
            )

    @staticmethod
    def _target_tenant_id(db: Session) -> int:
        """Website enquiries belong to the first (primary) tenant."""
        tenant = db.query(Tenant).order_by(Tenant.id).first()
        if tenant is None:
            raise HTTPException(status_code=503, detail="Enquiries are not available yet.")
        return int(tenant.id)

    @staticmethod
    def _summary(
        *,
        services: list[str],
        visit_frequency: str,
        products: list[str],
        area: str,
        notes: str,
    ) -> str:
        lines: list[str] = []
        if services:
            lines.append(f"Services: {', '.join(services)}")
        if visit_frequency:
            lines.append(f"Visits wanted: {visit_frequency}")
        if products:
            lines.append(f"Products of interest: {', '.join(products)}")
        if area:
            lines.append(f"Area: {area}")
        if notes:
            lines.append("")
            lines.append(notes)
        return "\n".join(lines)[:MAX_NOTES]

    @staticmethod
    def _lead_columns(db: Session, tenant_id: int, lead: dict) -> dict:
        """UTM / referrer / referral / pincode / slot → prospect columns (FIX 107/108).

        A pincode in a served area with a manager makes that manager the owner.
        A referral code is kept only when it is genuine and from this agency.
        """
        from app.livewell import site_settings as ss
        from app.models.tenant import Tenant

        tenant = db.get(Tenant, tenant_id)
        out: dict = {
            "utm_source": _clean(lead.get("utm_source"), 100) or None,
            "utm_medium": _clean(lead.get("utm_medium"), 100) or None,
            "utm_campaign": _clean(lead.get("utm_campaign"), 150) or None,
            "referrer_url": _clean(lead.get("referrer"), 500) or None,
            "landing_page": _clean(lead.get("landing_page"), 500) or None,
        }
        code = _clean(lead.get("ref"), 32).upper()
        if code and ss.referrer_name(db, code, tenant_id):
            out["referral_code"] = code
        pin = ss.clean_pincode(lead.get("pincode"))
        if pin:
            check = ss.check_pincode(tenant, pin)
            out["pincode"] = pin
            out["area_served"] = bool(check["served"])
            if check["manager_user_id"]:
                out["owner_user_id"] = int(check["manager_user_id"])
        slot_date = _clean(lead.get("slot_date"), 10)
        window = _clean(lead.get("slot_window"), 20).lower()
        if slot_date:
            try:
                day = datetime.strptime(slot_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=422, detail="Please pick a valid date for the visit.") from None
            today = _utcnow().date()
            if day < today or day > today + timedelta(days=60):
                raise HTTPException(status_code=422, detail="Please pick a date in the next two months.")
            if window not in ss.SLOT_WINDOWS:
                window = "morning"
            out["assessment_slot"] = f"{day.isoformat()} {window}"
            price = ss.assessment_price(ss.get_settings(tenant)["assessment_price_paise"])
            if price:
                out["assessment_fee_paise"] = int(price)
        return out

    @staticmethod
    def start_assessment_payment(db: Session, row: ElderProspect) -> dict | None:
        """Razorpay order for a paid KushCare Discovery slot; None when free.

        A gateway failure never loses the enquiry — the team still calls back."""
        import logging

        if not row.assessment_slot or not row.assessment_fee_paise:
            return None
        from app.services.payments.factory import stub_in_production

        if stub_in_production():
            # No real gateway on a live server: book it as pay-later, never a fake order.
            logging.getLogger(__name__).warning("assessment_payment_stub_in_production id=%s", row.id)
            return None
        try:
            from app.services.payments.factory import get_payment_provider

            order = get_payment_provider().create_order(
                amount_minor=int(row.assessment_fee_paise),
                currency="INR",
                receipt=f"KA-{row.id:06d}",
                notes={"purpose": "assessment", "prospect_id": str(row.id)},
            )
        except Exception:
            logging.getLogger(__name__).exception("assessment_order_failed id=%s", row.id)
            return None
        row.assessment_order_id = order.order_id
        db.commit()
        return {
            "order_id": order.order_id,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "provider": order.provider,
            "public_key": order.public_key,
        }

    @staticmethod
    def mark_assessment_paid(db: Session, row: ElderProspect, *, payment_id: str | None = None) -> ElderProspect:
        """Idempotent: a second call (webhook after checkout) changes nothing."""
        if row.assessment_paid_at is None:
            row.assessment_paid_at = _utcnow().replace(tzinfo=None)
            note = f"Assessment fee paid online ({payment_id or 'Razorpay'})."
            row.notes = ((row.notes or "") + "\n\n" + note).strip()[:MAX_NOTES]
            db.commit()
            db.refresh(row)
        return row

    @staticmethod
    def settle_assessment_webhook(db: Session, event) -> dict | None:
        """Called from the wallet webhook when the order is not a wallet recharge."""
        row = (
            db.query(ElderProspect)
            .filter(ElderProspect.assessment_order_id == event.order_id)
            .first()
            if event.order_id
            else None
        )
        if row is None:
            return None
        if event.event not in {"payment.captured", "order.paid"}:
            return {"status": "ignored", "reason": f"unhandled event {event.event}"}
        if event.amount_minor is not None and int(event.amount_minor) != int(row.assessment_fee_paise or 0):
            return {"status": "ignored", "reason": "amount mismatch"}
        PublicEnquiryService.mark_assessment_paid(db, row, payment_id=event.payment_id)
        return {"status": "assessment_paid", "reference": f"KA-{row.id:06d}"}

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        phone: str | None,
        email: str | None,
        area: str | None,
        services: list[str] | None,
        visit_frequency: str | None,
        products: list[str] | None,
        notes: str | None,
        kind: str,
        honeypot: str | None = None,
        source_ip: str | None = None,
        lead: dict | None = None,
        src: str | None = None,
    ) -> ElderProspect:
        PublicEnquiryService._assert_not_bot(honeypot)

        full_name = _clean(name, MAX_NAME)
        phone_clean, email_clean = validate_contact(_clean(phone, MAX_PHONE), _clean(email, MAX_EMAIL))
        if not full_name:
            raise HTTPException(status_code=422, detail="Please tell us your name.")
        if not phone_clean and not email_clean:
            raise HTTPException(
                status_code=422,
                detail="Please leave a phone number or an email so we can reply.",
            )

        PublicEnquiryService._assert_rate_limit(db, source_ip=source_ip)

        first, _, last = full_name.partition(" ")
        tenant_id = PublicEnquiryService._target_tenant_id(db)
        lead_cols = PublicEnquiryService._lead_columns(db, tenant_id, lead or {})
        row = ElderProspect(
            tenant_id=tenant_id,
            first_name=first[:MAX_NAME] or full_name,
            last_name=last.strip()[:MAX_NAME],
            phone=phone_clean or None,
            email=email_clean or None,
            address=_clean(area, MAX_AREA) or None,
            source=f"{source_channel(src)}:{kind}"[:64],
            stage="NEW",
            status="OPEN",
            notes=PublicEnquiryService._summary(
                services=_clean_list(services),
                visit_frequency=_clean(visit_frequency, MAX_LIST_ITEM),
                products=_clean_list(products),
                area=_clean(area, MAX_AREA),
                notes=_clean(notes, MAX_NOTES),
            ),
            source_ip=source_ip,
            **lead_cols,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        PublicEnquiryService._notify_team(db, row, kind=kind)
        return row

    @staticmethod
    def _notify_team(db: Session, row: ElderProspect, *, kind: str) -> None:
        """Email admins and care managers at once (Settings → Email notifications → enquiry).
        A failed email never fails the enquiry."""
        import logging

        try:
            from app.livewell.email_notifications import agency_recipients, send

            name = f"{row.first_name} {row.last_name}".strip()
            where = (
                "KushCare Discovery form" if "care-check" in kind
                else "Custom plan form" if "plan" in kind
                else "Website chat (call-back request)" if "chat" in kind
                else kind
            )
            lines = [
                f"{name} sent an enquiry from the website ({where}). Reference KA-{row.id:06d}.",
                f"Phone: {row.phone or 'not given'}",
                f"Email: {row.email or 'not given'}",
            ]
            if row.address:
                lines.append(f"Area: {row.address}")
            if row.pincode:
                lines.append(f"PIN code: {row.pincode} ({'in our service areas' if row.area_served else 'not in our list — check'})")
            if row.assessment_slot:
                lines.append(f"Asked for an assessment visit: {row.assessment_slot}")
            if row.referral_code:
                lines.append(f"Referred by a family (code {row.referral_code})")
            elif row.source and row.source.startswith("qr:"):
                lines.append("Came from: QR code (standee)")
            elif row.utm_source:
                lines.append(f"Came from: {row.utm_source}" + (f" / {row.utm_campaign}" if row.utm_campaign else ""))
            if row.notes:
                lines.append(row.notes)
            lines.append("Please call them back today. It's on the ops Dashboard under New enquiries.")
            from app.livewell.team_alerts import alert_team

            alert_team(db, row.tenant_id, "lead_new", f"New website lead: {name}", "Please call them back today.",
                       path="/dashboard", email="none")
            send(agency_recipients(db, row.tenant_id, "enquiry"), f"New enquiry: {name}", "\n".join(lines), family=False)
        except Exception:
            logging.getLogger(__name__).exception("enquiry_notify_failed id=%s", row.id)
