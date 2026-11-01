"""Website "Buy now" on the care plans (Bharani, 30 Oct 2026).

Flow, all unauthenticated and rate limited like website enquiries:

1. ``quote``  — the price of a plan + cycle with an optional coupon (PAYNOW3 / PAYNOW5).
2. ``start``  — validates everything server-side (never the browser's amounts), creates
   or reuses the website lead (source ``website:buy-now``) and a Razorpay order for the
   final amount in paise. With the stub gateway on a live server nothing pretends to
   take money: the lead is kept and the team calls back.
3. ``verify`` (browser checkout callback) and the Razorpay webhook (``payment.captured``)
   both call ``mark_paid``, which runs exactly once per purchase: the lead becomes a
   client, a CustomerPlan is added already paid but still "pending_approval" (admins
   get the usual "Plan to approve" email), the coupon is counted once, the lead moves
   to Won with a history note, and the customer gets a receipt email.

Pay as you go (31 Oct 2026): the same flow sells one "Single priority visit"
(plan_id ``single-visit``, billing_cycle ``once``; ₹3,400 + ₹100 registration from
``care_plan_catalog.SINGLE_VISIT``). Once paid it adds no CustomerPlan: the client gets a
paid service request (what they need, preferred date / time of day) that ops schedules
from Visits -> Requests, and staff following "request" are emailed.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.pipeline_constants import ACTIVITY_NOTE, ACTIVITY_STAGE_CHANGE, PROSPECT_STATUS_WON
from app.livewell import sales_pipeline as sp
from app.livewell.public_enquiry_service import MAX_NOTES, PublicEnquiryService, _clean, validate_contact
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.plan_purchase import PlanPurchase
from app.models.user import User

logger = logging.getLogger(__name__)

#: Checkouts started from one IP per hour (each retry is one).
PURCHASE_LIMIT_PER_HOUR = 10
#: Razorpay will not take an order below ₹1.
MIN_ONLINE_PAISE = 100
SOURCE = "website:buy-now"
BY_WEBSITE = "The website (Buy now, paid online)"
COMING_SOON = "Online payment is coming soon — we'll call you to complete it."
GATEWAY_DOWN = "We couldn't start the online payment just now. Your request is saved — we'll call you to complete it."
SUCCESS_EVENTS = {"payment.captured", "order.paid"}

# --- Pay-as-you-go visit -------------------------------------------------------------
VISIT_PLAN_ID = "single-visit"
VISIT_CYCLE = "once"
SOURCE_VISIT = "website:buy-now-visit"
#: "What do you need?" -> the family service request type it becomes.
VISIT_NEEDS = {
    "care_visit": "Caregiver / attendant visit",
    "physiotherapy": "Physiotherapy session",
    "discharge_help": "Hospital-discharge & recovery help",
    "safety_recheck": "Home safety re-check",
    "other": "Something else",
}
#: Time of day -> the IST hour the request "prefers" (ops still picks the real time).
TIME_SLOTS = {"morning": ("Morning", 9), "afternoon": ("Afternoon", 13), "evening": ("Evening", 17)}
VISIT_BOOK_AHEAD_DAYS = 90
IST = timezone(timedelta(hours=5, minutes=30))


def is_visit(plan_id: str | None) -> bool:
    return (plan_id or "").strip() == VISIT_PLAN_ID


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reference(p: PlanPurchase) -> str:
    return f"KP-{p.id:06d}"


def _rupees(paise: int) -> str:
    """₹1,21,250 (Indian grouping); paise shown only when there are any."""
    rupees, p = divmod(int(paise), 100)
    digits = str(rupees)
    head, tail = digits[:-3], digits[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    text = f"{head},{tail}" if head else tail
    return f"₹{text}" + (f".{p:02d}" if p else "")


def _cycle_word(cycle: str) -> str:
    return {"yearly": "yearly", "once": "one visit"}.get(cycle, "monthly")


def _public_price(priced: dict) -> dict:
    out = {k: priced[k] for k in ("plan_id", "plan_name", "billing_cycle", "list_paise", "discount_paise", "amount_paise", "coupon_code")}
    if "visit_paise" in priced:
        out["visit_paise"] = priced["visit_paise"]
        out["registration_paise"] = priced["registration_paise"]
    return out


def price(db: Session, tenant_id: int, plan_id: str | None, cycle: str | None, coupon_code: str | None) -> dict:
    """A plan (sales_pipeline.price_plan) or the single visit: visit + registration, then
    the same coupon rules, on the total. Integer paise; 422/400 with a plain reason."""
    if not is_visit(plan_id):
        return sp.price_plan(db, tenant_id, plan_id, cycle, coupon_code)
    if cycle != VISIT_CYCLE:
        raise HTTPException(status_code=422, detail="Pick a valid option.")
    v = sp.catalog.SINGLE_VISIT
    list_paise = int(v["price_paise"]) + int(v["registration_paise"])
    code = (coupon_code or "").strip().upper()[:40]
    discount = 0
    if code:
        from app.livewell.commerce import _valid_coupon

        c = _valid_coupon(db, tenant_id, code)
        discount = sp.coupon_discount_paise(list_paise, c.kind, c.value)
        code = c.code
    return {
        "plan_id": v["id"],
        "plan_name": v["name"],
        "billing_cycle": VISIT_CYCLE,
        "visit_paise": int(v["price_paise"]),
        "registration_paise": int(v["registration_paise"]),
        "list_paise": list_paise,
        "discount_paise": discount,
        "amount_paise": list_paise - discount,
        "coupon_code": code or None,
    }


def quote(db: Session, *, plan_id: str, billing_cycle: str, coupon_code: str | None) -> dict:
    tenant_id = PublicEnquiryService._target_tenant_id(db)
    return _public_price(price(db, tenant_id, plan_id, billing_cycle, coupon_code))


def _ist_today() -> date:
    return datetime.now(IST).date()


def visit_details(need: str | None, note: str | None, preferred_date: str | None, time_of_day: str | None) -> dict:
    """The visit form, checked: a known need (a note for "Something else"), a date from
    tomorrow (IST) up to VISIT_BOOK_AHEAD_DAYS ahead, morning / afternoon / evening."""
    need = (need or "").strip()
    if need not in VISIT_NEEDS:
        raise HTTPException(status_code=422, detail="Please tell us what you need.")
    note = " ".join(_clean(note, 300).split())
    if need == "other" and not note:
        raise HTTPException(status_code=422, detail="Please add a short note about what you need.")
    day = None
    if (preferred_date or "").strip():
        try:
            day = date.fromisoformat(preferred_date.strip()[:10])
        except ValueError:
            raise HTTPException(status_code=422, detail="Please pick a valid date.") from None
        today = _ist_today()
        if day <= today:
            raise HTTPException(status_code=422, detail="Please pick a date from tomorrow.")
        if day > today + timedelta(days=VISIT_BOOK_AHEAD_DAYS):
            raise HTTPException(status_code=422, detail=f"Please pick a date within {VISIT_BOOK_AHEAD_DAYS} days.")
    slot = (time_of_day or "").strip().lower() or None
    if slot is not None and slot not in TIME_SLOTS:
        raise HTTPException(status_code=422, detail="Please pick morning, afternoon or evening.")
    return {"need": need, "note": note, "preferred_date": day.isoformat() if day else None, "time_of_day": slot}


def _day_text(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b %Y')}"


def _visit_when(d: dict) -> str:
    """"Tue 3 Nov 2026, morning" / "Morning" / "" (any time)."""
    parts = [_day_text(d["preferred_date"])] if d.get("preferred_date") else []
    if d.get("time_of_day") in TIME_SLOTS:
        label = TIME_SLOTS[d["time_of_day"]][0]
        parts.append(label.lower() if parts else label)
    return ", ".join(parts)


def _visit_preferred_at(d: dict) -> datetime | None:
    """Date + time of day -> the request's preferred time (UTC). A date alone stays in the note."""
    if not d.get("preferred_date") or d.get("time_of_day") not in TIME_SLOTS:
        return None
    hour = TIME_SLOTS[d["time_of_day"]][1]
    return datetime.combine(date.fromisoformat(d["preferred_date"]), time(hour), tzinfo=IST).astimezone(timezone.utc)


def _what(priced: dict, details: dict | None) -> str:
    if is_visit(priced["plan_id"]):
        need = VISIT_NEEDS.get((details or {}).get("need") or "", "visit")
        what = f"{priced['plan_name']} — {need} ({_rupees(priced['amount_paise'])}"
    else:
        what = f"{priced['plan_name']} ({_cycle_word(priced['billing_cycle'])}, {_rupees(priced['amount_paise'])}"
    return what + (f" after coupon {priced['coupon_code']})" if priced["coupon_code"] else ")")


def _assert_rate_limit(db: Session, source_ip: str | None) -> None:
    if not source_ip:
        return
    since = _now() - timedelta(hours=1)
    n = db.query(PlanPurchase).filter(PlanPurchase.source_ip == source_ip, PlanPurchase.created_at >= since).count()
    if n >= PURCHASE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many attempts from this connection. Please try again later, or call us.")


def _note(db: Session, lead: ElderProspect, text: str, source: str = SOURCE) -> None:
    db.add(PipelineActivity(
        tenant_id=lead.tenant_id, elder_prospect_id=lead.id, activity_type=ACTIVITY_NOTE,
        body=text[:2000], metadata_={"source": source}, created_by_user_id=None,
    ))


def _lead(db: Session, tenant_id: int, *, name: str, phone: str, email: str | None, area: str | None,
          pincode: str | None, source_ip: str | None, lead_extra: dict, source: str = SOURCE) -> ElderProspect:
    """The newest open-or-won lead with this mobile number, or a new website lead."""
    row = (
        db.query(ElderProspect)
        .filter(ElderProspect.tenant_id == tenant_id, ElderProspect.phone == phone, ElderProspect.status != "LOST")
        .order_by(ElderProspect.id.desc())
        .first()
    )
    if row is not None:
        if email and not row.email:
            row.email = email
        return row
    first, _, last = name.partition(" ")
    cols = PublicEnquiryService._lead_columns(db, tenant_id, {**lead_extra, "pincode": pincode})
    row = ElderProspect(
        tenant_id=tenant_id,
        first_name=first[:100] or name,
        last_name=last.strip()[:100],
        phone=phone,
        email=email,
        address=area or None,
        source=source,
        stage="NEW",
        status="OPEN",
        notes="",
        source_ip=source_ip,
        **cols,
    )
    db.add(row)
    db.flush()
    return row


def start(
    db: Session,
    *,
    plan_id: str,
    billing_cycle: str,
    name: str,
    phone: str | None,
    email: str | None,
    area: str | None = None,
    pincode: str | None = None,
    coupon_code: str | None = None,
    accept_terms: bool = False,
    honeypot: str | None = None,
    source_ip: str | None = None,
    lead_extra: dict | None = None,
    need: str | None = None,
    need_note: str | None = None,
    preferred_date: str | None = None,
    time_of_day: str | None = None,
) -> dict:
    PublicEnquiryService._assert_not_bot(honeypot)
    full_name = " ".join(_clean(name, 100).split())
    phone_clean, email_clean = validate_contact(_clean(phone, 50), _clean(email, 255))
    if not full_name:
        raise HTTPException(status_code=422, detail="Please tell us your name.")
    if not phone_clean:
        raise HTTPException(status_code=422, detail="Please enter your mobile number.")
    if not email_clean:
        raise HTTPException(status_code=422, detail="Please enter your email for the receipt.")
    if not accept_terms:
        raise HTTPException(status_code=422, detail="Please accept the terms to continue.")
    visit = is_visit(plan_id)
    details = visit_details(need, need_note, preferred_date, time_of_day) if visit else None
    source = SOURCE_VISIT if visit else SOURCE
    tenant_id = PublicEnquiryService._target_tenant_id(db)
    priced = price(db, tenant_id, plan_id, billing_cycle, coupon_code)  # 422/400 before anything is saved
    if priced["amount_paise"] < MIN_ONLINE_PAISE:
        raise HTTPException(status_code=422, detail="This coupon can't be used for online payment. Please call us.")
    _assert_rate_limit(db, source_ip)

    lead = _lead(db, tenant_id, name=full_name, phone=phone_clean, email=email_clean,
                 area=_clean(area, 500) or None, pincode=pincode, source_ip=source_ip, lead_extra=lead_extra or {},
                 source=source)
    what = _what(priced, details)
    if details:
        when = _visit_when(details)
        what += (f", preferred {when}" if when else "") + (f". Note: {details['note']}" if details["note"] else "")
    purchase = PlanPurchase(
        tenant_id=tenant_id, prospect_id=lead.id, plan_id=priced["plan_id"], billing_cycle=priced["billing_cycle"],
        list_paise=priced["list_paise"], discount_paise=priced["discount_paise"], amount_paise=priced["amount_paise"],
        coupon_code=priced["coupon_code"], status="created", source_ip=source_ip, details=details,
    )
    db.add(purchase)
    db.flush()
    out = {"ok": True, "reference": reference(purchase), "price": _public_price(priced), "payment": None}

    from app.services.payments.factory import get_payment_provider, stub_in_production

    order = None
    if stub_in_production():
        # No real gateway on a live server: never a fake order. Keep the lead, call back.
        logger.warning("plan_purchase_stub_in_production purchase=%s", purchase.id)
        out["payment_message"] = COMING_SOON
    else:
        try:
            order = get_payment_provider().create_order(
                amount_minor=int(purchase.amount_paise),
                currency="INR",
                receipt=reference(purchase),
                notes={
                    "purpose": "visit" if visit else "plan",
                    "plan": purchase.plan_id,
                    "cycle": purchase.billing_cycle,
                    "prospect_id": str(lead.id),
                    "purchase": reference(purchase),
                    "coupon": purchase.coupon_code or "",
                },
            )
        except Exception:  # noqa: BLE001 — a gateway failure never loses the lead
            logger.exception("plan_purchase_order_failed purchase=%s", purchase.id)
            out["payment_message"] = GATEWAY_DOWN
    if order is not None:
        purchase.gateway = order.provider
        purchase.gateway_order_id = order.order_id
        out["payment"] = {
            "order_id": order.order_id,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "provider": order.provider,
            "public_key": order.public_key,
        }
        _note(db, lead, f"Started Buy now on the website: {what}. Ref {reference(purchase)}.", source)
    else:
        _note(db, lead, f"Wanted to buy {what} online, but online payment wasn't available. Call to complete it. Ref {reference(purchase)}.", source)
    lead.updated_at = _now()
    db.commit()
    if order is None:
        PublicEnquiryService._notify_team(db, lead, kind=f"Buy now: {what} — online payment unavailable, please call")
    return out


def _purchase_for(db: Session, ref: str) -> PlanPurchase | None:
    digits = "".join(ch for ch in (ref or "") if ch.isdigit())
    if not digits or len(digits) > 9:
        return None
    return db.get(PlanPurchase, int(digits))


def verify(db: Session, ref: str, *, order_id: str, payment_id: str, signature: str) -> dict:
    """Browser checkout callback. The webhook is the backstop; both are idempotent."""
    from app.services.payments.factory import get_payment_provider, stub_in_production

    p = _purchase_for(db, ref)
    if p is None or not p.gateway_order_id or p.gateway_order_id != order_id:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if stub_in_production():  # a stub "payment" is never real money
        raise HTTPException(status_code=400, detail="Payment could not be verified")
    if not get_payment_provider().verify_checkout_signature(order_id=order_id, payment_id=payment_id, signature=signature):
        raise HTTPException(status_code=400, detail="Payment could not be verified")
    mark_paid(db, p, payment_id=payment_id)
    return {"ok": True, "reference": reference(p), "paid": True}


def settle_webhook(db: Session, event) -> dict | None:
    """Called from the Razorpay webhook when the order is not a wallet recharge. None = not ours."""
    p = (
        db.query(PlanPurchase).filter(PlanPurchase.gateway_order_id == event.order_id).first()
        if event.order_id else None
    )
    if p is None:
        return None
    if event.event not in SUCCESS_EVENTS:
        return {"status": "ignored", "reason": f"unhandled event {event.event}"}
    if event.amount_minor is not None and int(event.amount_minor) != int(p.amount_paise):
        logger.error("plan_purchase_amount_mismatch purchase=%s expected=%s got=%s", p.id, p.amount_paise, event.amount_minor)
        return {"status": "ignored", "reason": "amount mismatch"}
    mark_paid(db, p, payment_id=event.payment_id)
    return {"status": "plan_paid", "reference": reference(p)}


def _system_user(db: Session, tenant_id: int) -> User:
    """Website sales are recorded as the agency's first admin (needed to create the client)."""
    for roles in (("TENANT_ADMIN",), ("SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN")):
        u = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.role.in_(roles), User.status == "ACTIVE")
            .order_by(User.id)
            .first()
        )
        if u is not None:
            return u
    raise HTTPException(status_code=503, detail="Purchase could not be recorded — no admin account")


def mark_paid(db: Session, p: PlanPurchase, *, payment_id: str | None) -> PlanPurchase:
    """Exactly once per purchase: the status flip is a conditional UPDATE, so a checkout
    callback and a webhook racing each other can't both create a plan (or visit request)."""
    paid_at = _now()
    res = db.execute(
        update(PlanPurchase)
        .where(PlanPurchase.id == p.id, PlanPurchase.status == "created")
        .values(status="paid", paid_at=paid_at, gateway_payment_id=(payment_id or None))
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:  # already paid (nothing was changed)
        db.refresh(p)
        return p
    visit = is_visit(p.plan_id)
    request = None
    try:
        lead = db.get(ElderProspect, p.prospect_id) if p.prospect_id else None
        if lead is None:
            raise HTTPException(status_code=409, detail="The lead for this purchase is missing")
        user = _system_user(db, p.tenant_id)
        elder = sp._won_elder(db, user, lead, None)
        paid_note = f"Ref {reference(p)}, Razorpay {payment_id or p.gateway_order_id}"
        if visit:
            details = p.details or {}
            need = VISIT_NEEDS.get(details.get("need") or "", "Visit")
            name = sp.catalog.SINGLE_VISIT["name"]
            request = _paid_visit_request(db, p, elder, details, payment_id=payment_id)
            p.service_request_id = request["id"]
            text = f"Paid {_rupees(p.amount_paise)} online for a {name} ({need})"
            meta = {"service_request_id": request["id"], "need": details.get("need")}
            tail = "Visit waits in Visits → Requests to be scheduled."
        else:
            row = sp.create_plan(
                db, user, elder,
                plan_id=p.plan_id, billing_cycle=p.billing_cycle, prospect_id=lead.id,
                priced={"amount_paise": p.amount_paise, "discount_paise": p.discount_paise, "coupon_code": p.coupon_code},
                paid={
                    "mode": "razorpay",
                    "at": paid_at,
                    "note": f"Paid online on the website ({reference(p)}; Razorpay order {p.gateway_order_id}, payment {payment_id or '—'}).",
                },
                by=BY_WEBSITE,
            )
            p.customer_plan_id = row.id
            name = (sp.catalog.plan(row.plan_id) or {}).get("name", row.plan_id)
            text = f"Paid {_rupees(p.amount_paise)} online for {name} ({_cycle_word(p.billing_cycle)})"
            meta = {"customer_plan_id": row.id}
            tail = "Plan waits for admin approval."
        lead.converted_elder_id = elder.id
        if p.coupon_code:
            text += f" with coupon {p.coupon_code} (−{_rupees(p.discount_paise)})"
        text += f". {paid_note}. {tail}"
        source = SOURCE_VISIT if visit else SOURCE
        current = sp.board_stage(lead)
        if current != "WON":
            lead.stage = "WON"
            lead.status = PROSPECT_STATUS_WON
            lead.lost_reason = None
            db.add(PipelineActivity(
                tenant_id=lead.tenant_id, elder_prospect_id=lead.id, activity_type=ACTIVITY_STAGE_CHANGE,
                body=f"{sp.STAGE_LABELS.get(current, current)} → Won: {text}"[:2100],
                metadata_={"from": current, "to": "WON", "comment": text, "elder_id": elder.id,
                           **meta, "plan_id": p.plan_id, "billing_cycle": p.billing_cycle,
                           "amount_paise": p.amount_paise, "coupon_code": p.coupon_code,
                           "discount_paise": p.discount_paise, "source": source},
                created_by_user_id=None,
            ))
        else:
            _note(db, lead, text, source)
        lead.notes = ((lead.notes or "") + "\n\n" + text).strip()[:MAX_NOTES]
        lead.updated_at = _now()
        db.commit()
    except Exception:
        db.rollback()  # the status flip rolls back too, so a retry (webhook) can finish it
        logger.exception("plan_purchase_mark_paid_failed purchase=%s", p.id)
        raise
    db.refresh(p)
    if request is not None:
        _email_staff_visit(db, p, elder, request)
    _email_receipt(db, p, lead, name)
    return p


def _paid_visit_request(db: Session, p: PlanPurchase, elder, details: dict, *, payment_id: str | None) -> dict:
    """The paid visit as a family service request (ops Visits -> Requests), coupon counted once."""
    from app.livewell.family_service_requests import add_paid_online_request

    when = _visit_when(details)
    bits = [f"Paid {_rupees(p.amount_paise)} online ({reference(p)}; Razorpay order {p.gateway_order_id}, payment {payment_id or '—'})"]
    if p.coupon_code:
        bits.append(f"coupon {p.coupon_code} −{_rupees(p.discount_paise)}")
    if when:
        bits.append(f"prefers {when}")
    notes = "; ".join(bits) + "."
    if details.get("note"):
        notes = f"{details['note']} — {notes}"
    sp.use_coupon(db, p.tenant_id, p.coupon_code, strict=False)  # money already taken: count it even when full
    return add_paid_online_request(
        db, elder,
        service_type=details.get("need") or "other",
        notes=notes,
        preferred_at=_visit_preferred_at(details),
        amount_minor=int(p.amount_paise),
        reference=reference(p),
        created_by="Website — paid online",
    )


def _email_staff_visit(db: Session, p: PlanPurchase, elder, request: dict) -> None:
    try:
        from app.livewell.email_notifications import email_staff

        email_staff(
            db, elder, "request",
            f"Paid visit to schedule: {request['service_label']}",
            f"{elder.first_name} {elder.last_name}".strip()
            + f" paid {_rupees(p.amount_paise)} online for a single priority visit ({request['service_label']}).\n"
            + f"{request['notes']}\nSchedule it from Visits → Requests.",
            path="/kushalaya/visits?tab=requests",
        )
    except Exception:  # noqa: BLE001 — a failed email never undoes a payment
        logger.exception("plan_purchase_visit_staff_email_failed purchase=%s", p.id)


def _email_receipt(db: Session, p: PlanPurchase, lead: ElderProspect, plan_name: str) -> None:
    if not lead.email:
        return
    try:
        from app.livewell.email_notifications import send

        visit = is_visit(p.plan_id)
        if visit:
            v = sp.catalog.SINGLE_VISIT
            need = VISIT_NEEDS.get((p.details or {}).get("need") or "", "Visit")
            what = (f"a {plan_name} — {need} ({_rupees(v['price_paise'])} visit + "
                    f"{_rupees(v['registration_paise'])} registration, GST included)")
        else:
            what = f"{plan_name} ({_cycle_word(p.billing_cycle)}, GST included)"
        lines = [
            f"Dear {lead.first_name or 'there'},",
            "",
            f"Thank you — we have received {_rupees(p.amount_paise)} for {what}.",
            f"Reference: {reference(p)}",
            f"Payment ID: {p.gateway_payment_id or '—'}",
        ]
        if p.coupon_code:
            label = "price" if visit else "plan price"
            lines.append(f"Coupon {p.coupon_code}: −{_rupees(p.discount_paise)} ({label} {_rupees(p.list_paise)})")
        if visit:
            when = _visit_when(p.details or {})
            if when:
                lines.append(f"Preferred: {when}")
            lines += ["", "Our care team will call you shortly to confirm the date and time of the visit."]
        else:
            lines += ["", "Your care manager will call you shortly to welcome you and plan the first visit."]
        send([lead.email], f"Payment received — {reference(p)}", "\n".join(lines), family=True)
    except Exception:  # noqa: BLE001 — a failed email never undoes a payment
        logger.exception("plan_purchase_receipt_failed purchase=%s", p.id)
