"""Operations board (sales pipeline) and customer plans.

Leads are the existing ``ElderProspect`` rows (website enquiries arrive at NEW);
every move is a ``PipelineActivity`` (from, to, comment, who, when). Board stages:

    New -> Assessment booked -> Assessment done -> Follow-up 1 -> Follow-up 2 -> Won / Lost

"Assessment booked" is stored as the existing ASSESSMENT_SCHEDULED code so the
website funnel and older rows keep working. Older codes are shown in the nearest
column (CONTACTED -> New, PROPOSAL_SENT -> Follow-up 1).

Won needs a plan and a billing cycle: the lead is linked to a client (created
when there is none) and a ``CustomerPlan`` is added in "pending_approval",
unpaid, priced from care_plan_catalog. Authorize makes it active. Money is paise.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.pipeline_constants import (
    ACTIVITY_NOTE,
    ACTIVITY_STAGE_CHANGE,
    PROSPECT_STATUS_LOST,
    PROSPECT_STATUS_OPEN,
    PROSPECT_STATUS_WON,
)
from app.core.rbac import resolve_tenant_id
from app.core.team_scope import assert_elder_in_team, scope_elder_query
from app.livewell import care_plan_catalog as catalog
from app.models.customer_plan import CustomerPlan
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.pipeline_activity import PipelineActivity
from app.models.user import User


def _iso(dt: datetime | None) -> str | None:
    """DB datetimes are naive UTC; send them with the offset so browsers don't read them as local time."""
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


SALES_STAGES: tuple[str, ...] = (
    "NEW",
    "ASSESSMENT_SCHEDULED",
    "ASSESSMENT_DONE",
    "FOLLOW_UP_1",
    "FOLLOW_UP_2",
    "WON",
    "LOST",
)
STAGE_LABELS: dict[str, str] = {
    "NEW": "New",
    "ASSESSMENT_SCHEDULED": "Assessment booked",
    "ASSESSMENT_DONE": "Assessment done",
    "FOLLOW_UP_1": "Follow-up 1",
    "FOLLOW_UP_2": "Follow-up 2",
    "WON": "Won",
    "LOST": "Lost",
}
#: Older pipeline codes -> the board column they show in.
_LEGACY_COLUMN = {"CONTACTED": "NEW", "PROPOSAL_SENT": "FOLLOW_UP_1"}

PAYMENT_MODES: tuple[str, ...] = ("cash", "upi", "bank_transfer", "card", "cheque", "online", "razorpay", "other")

#: Won / Lost leads older than this drop off the board (open leads always show).
CLOSED_DAYS_ON_BOARD = 180
MAX_COMMENT = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bad(detail: str, code: int = 422) -> None:
    raise HTTPException(status_code=code, detail=detail)


def customer_code(elder_id: int) -> str:
    return f"KC-{int(elder_id):06d}"


_STATES = {
    "india", "telangana", "andhra pradesh", "karnataka", "tamil nadu", "kerala", "maharashtra",
    "delhi", "new delhi", "gujarat", "west bengal", "uttar pradesh", "rajasthan", "punjab",
    "haryana", "odisha", "goa", "madhya pradesh", "bihar", "ts", "ap", "tn", "ka",
}


def city_from_address(address: str | None) -> str | None:
    """Best guess at the city in a free-text address: the last comma part that is
    not a PIN code, a state or "India" ("Flat 2, Banjara Hills, Hyderabad, Telangana 500034" -> "Hyderabad")."""
    import re

    parts = [p.strip() for p in re.split(r"[,\n]", address or "")]
    for part in reversed(parts):
        text = re.sub(r"[-\s]*\b\d{6}\b", "", part).strip(" .-")
        if not text or text.isdigit() or text.lower() in _STATES:
            continue
        return text[:80]
    return None


def board_stage(row: ElderProspect) -> str:
    if row.status == PROSPECT_STATUS_WON or row.stage == "WON":
        return "WON"
    if row.status == PROSPECT_STATUS_LOST or row.stage == "LOST":
        return "LOST"
    stage = _LEGACY_COLUMN.get(row.stage, row.stage)
    return stage if stage in SALES_STAGES else "NEW"


def add_months(start: date, months: int) -> date:
    """Same day ``months`` later, clamped to the month's last day (31 Jan + 1 -> 28/29 Feb)."""
    y, m = divmod(start.month - 1 + months, 12)
    year, month = start.year + y, m + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def plan_terms(plan_id: str | None, cycle: str | None) -> tuple[dict, int, int]:
    """(plan, amount_paise, months) for a plan + cycle, or 422 with a plain reason."""
    plan = catalog.plan(plan_id or "")
    if plan is None:
        _bad("Choose one of the four plans.")
    if cycle not in catalog.BILLING_CYCLES:
        _bad("Choose Yearly or Monthly.")
    amount = catalog.price_paise(plan["id"], cycle)
    if amount is None:
        _bad(f"{plan['name']} isn't offered on that billing cycle.")
    return plan, int(amount), 12 if cycle == "yearly" else 1


def coupon_discount_paise(list_paise: int, kind: str, value: int) -> int:
    """What a coupon takes off a price: percent in basis points (300 = 3%), floored
    to the paisa; amount in paise. Never more than the price, never negative."""
    off = int(list_paise) * int(value) // 10000 if kind == "percent" else int(value)
    return max(0, min(int(list_paise), off))


def price_plan(db: Session, tenant_id: int, plan_id: str | None, cycle: str | None, coupon_code: str | None = None) -> dict:
    """Server-side price of a plan + cycle with an optional coupon (422/400 with a plain reason).
    Coupons are the agency's pre-approved discounts (Sales -> Coupons), e.g. PAYNOW3 / PAYNOW5."""
    plan, list_paise, months = plan_terms(plan_id, cycle)
    code = (coupon_code or "").strip().upper()[:40]
    discount = 0
    if code:
        from app.livewell.commerce import _valid_coupon

        c = _valid_coupon(db, tenant_id, code)
        discount = coupon_discount_paise(list_paise, c.kind, c.value)
        code = c.code
    return {
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "billing_cycle": cycle,
        "months": months,
        "list_paise": list_paise,
        "discount_paise": discount,
        "amount_paise": list_paise - discount,
        "coupon_code": code or None,
    }


def use_coupon(db: Session, tenant_id: int, code: str | None, *, strict: bool = True) -> bool:
    """Count one use of a coupon, atomically (two sales racing for the last use can't both
    get it). ``strict=False`` is for money already taken online: count it even when full."""
    if not code:
        return False
    from sqlalchemy import or_, update

    from app.models.commerce import Coupon

    cond = [Coupon.tenant_id == tenant_id, Coupon.code == code]
    if strict:
        cond.append(or_(Coupon.max_uses.is_(None), Coupon.used_count < Coupon.max_uses))
    res = db.execute(
        update(Coupon).where(*cond).values(used_count=Coupon.used_count + 1).execution_options(synchronize_session=False)
    )
    if strict and res.rowcount != 1:
        _bad("This coupon has been used up.", 400)
    return res.rowcount == 1


# --- Customer plans ---------------------------------------------------------


def effective_status(row: CustomerPlan, today: date | None = None) -> str:
    if row.status == "active" and row.end_date < (today or date.today()):
        return "expired"
    return row.status


def _user_name(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    u = db.get(User, user_id)
    return f"{u.first_name} {u.last_name}".strip() if u else None


def plan_dict(db: Session, row: CustomerPlan) -> dict:
    p = catalog.plan(row.plan_id)
    return {
        "id": row.id,
        "elder_id": row.elder_id,
        "customer_id": customer_code(row.elder_id),
        "prospect_id": row.prospect_id,
        "plan_id": row.plan_id,
        "plan_name": p["name"] if p else row.plan_id,
        "billing_cycle": row.billing_cycle,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "amount_paise": row.amount_paise,
        "coupon_code": row.coupon_code,
        "discount_paise": row.discount_paise or 0,
        "payment_status": row.payment_status,
        "payment_mode": row.payment_mode,
        "paid_at": _iso(row.paid_at),
        "status": effective_status(row),
        "authorized_by_name": _user_name(db, row.authorized_by_user_id),
        "authorized_at": _iso(row.authorized_at),
        "created_at": _iso(row.created_at),
    }


def _elder_for(db: Session, user: User, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    tid = resolve_tenant_id(user)
    if elder is None or (tid is not None and elder.tenant_id != tid):
        _bad("Client not found", 404)
    assert_elder_in_team(db, user, elder.id)
    return elder


def create_plan(
    db: Session,
    user: User,
    elder: Elder,
    *,
    plan_id: str | None,
    billing_cycle: str | None,
    start_date: date | None = None,
    prospect_id: int | None = None,
    coupon_code: str | None = None,
    priced: dict | None = None,
    paid: dict | None = None,
    by: str | None = None,
) -> CustomerPlan:
    """New plan in pending approval, priced from the catalog less any coupon (flushes, no commit).

    ``priced`` / ``paid`` come from a website purchase: the price fixed when the order was
    made, and the payment (mode, at, note). A paid plan skips the one-waiting-plan rule:
    the money is already taken, so the plan must be recorded."""
    _plan, _, months = plan_terms(plan_id, billing_cycle)
    priced = priced or price_plan(db, elder.tenant_id, plan_id, billing_cycle, coupon_code)
    waiting = (
        db.query(CustomerPlan.id)
        .filter(CustomerPlan.elder_id == elder.id, CustomerPlan.status == "pending_approval")
        .first()
    )
    if waiting and not paid:
        _bad("This client already has a plan waiting for approval.", 400)
    start = start_date or date.today()
    row = CustomerPlan(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        prospect_id=prospect_id,
        plan_id=_plan["id"],
        billing_cycle=billing_cycle,
        start_date=start,
        end_date=add_months(start, months),
        amount_paise=int(priced["amount_paise"]),
        coupon_code=priced.get("coupon_code"),
        discount_paise=int(priced.get("discount_paise") or 0),
        payment_status="paid" if paid else "unpaid",
        payment_mode=(paid or {}).get("mode"),
        paid_at=(paid or {}).get("at"),
        notes=(paid or {}).get("note"),
        status="pending_approval",
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    use_coupon(db, elder.tenant_id, row.coupon_code, strict=not paid)
    _email_plan_approval(db, user, elder, row, _plan["name"], by=by)
    return row


def _email_plan_approval(db: Session, user: User, elder, row: CustomerPlan, plan_name: str, by: str | None = None) -> None:
    """Admins hear straight away that a new plan is waiting for them (Won on the board,
    or a plan added on the client's page). A failed email never stops the sale."""
    try:
        from app.livewell.email_notifications import email_staff, staff_path

        by = by or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        who = f"{elder.first_name or ''} {elder.last_name or ''}".strip() or "a client"
        cycle = "yearly" if row.billing_cycle == "yearly" else "monthly"
        coupon = f", coupon {row.coupon_code} took off ₹{row.discount_paise / 100:,.0f}" if row.coupon_code else ""
        paid = " Already paid online." if row.payment_status == "paid" else ""
        email_staff(
            db, elder, "approval",
            f"Plan to approve: {plan_name} — {who}",
            f"{by} signed {who} up for {plan_name} ({cycle}, ₹{row.amount_paise / 100:,.0f} including GST{coupon}, "
            f"from {row.start_date:%d %b %Y}).{paid} It is waiting for an admin to approve it."
            "\nOpen the client's Plan & payments to approve it and record the payment.",
            path=staff_path(elder, "plan"),
        )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("plan_approval_email_failed plan=%s", row.id)


def assign_plan(db: Session, user: User, elder_id: int, **terms) -> dict:
    elder = _elder_for(db, user, elder_id)
    row = create_plan(db, user, elder, **terms)
    db.commit()
    db.refresh(row)
    return plan_dict(db, row)


def _plan_for(db: Session, user: User, plan_row_id: int) -> CustomerPlan:
    row = db.get(CustomerPlan, plan_row_id)
    tid = resolve_tenant_id(user)
    if row is None or (tid is not None and row.tenant_id != tid):
        _bad("Plan not found", 404)
    assert_elder_in_team(db, user, row.elder_id)
    return row


def _mode(mode: str | None) -> str:
    m = (mode or "").strip().lower()
    if m not in PAYMENT_MODES:
        _bad("Choose how they paid (payment mode).")
    return m


def authorize(db: Session, user: User, plan_row_id: int, *, payment_mode: str | None, paid: bool) -> dict:
    row = _plan_for(db, user, plan_row_id)
    if row.status != "pending_approval":
        _bad("Only a plan waiting for approval can be authorized.", 400)
    row.payment_mode = _mode(payment_mode)
    if paid:
        row.payment_status = "paid"
        row.paid_at = _now()
    row.status = "active"
    row.authorized_by_user_id = user.id
    row.authorized_at = _now()
    db.commit()
    db.refresh(row)
    return plan_dict(db, row)


def mark_paid(db: Session, user: User, plan_row_id: int, *, payment_mode: str | None = None) -> dict:
    row = _plan_for(db, user, plan_row_id)
    if row.status == "cancelled":
        _bad("This plan was cancelled.", 400)
    if row.payment_status == "paid":
        _bad("This plan is already paid.", 400)
    row.payment_mode = _mode(payment_mode or row.payment_mode)
    row.payment_status = "paid"
    row.paid_at = _now()
    db.commit()
    db.refresh(row)
    return plan_dict(db, row)


def elder_plans(db: Session, user: User, elder_id: int) -> dict:
    elder = _elder_for(db, user, elder_id)
    rows = (
        db.query(CustomerPlan)
        .filter(CustomerPlan.elder_id == elder.id)
        .order_by(CustomerPlan.start_date.desc(), CustomerPlan.id.desc())
        .all()
    )
    plans = [plan_dict(db, r) for r in rows]
    current = _current(plans)
    return {
        "elder_id": elder.id,
        "customer_id": customer_code(elder.id),
        "current": current,
        "plans": plans,
        "total_paise": sum(p["amount_paise"] for p in plans if p["status"] != "cancelled"),
        "paid_paise": sum(p["amount_paise"] for p in plans if p["payment_status"] == "paid"),
    }


def _current(plans: list[dict]) -> dict | None:
    """The plan a list shows: active, else waiting for approval, else the latest one."""
    for wanted in ("active", "pending_approval"):
        hit = next((p for p in plans if p["status"] == wanted), None)
        if hit:
            return hit
    return plans[0] if plans else None


def list_customers(db: Session, user: User) -> dict:
    q = db.query(Elder).filter(Elder.status != "INACTIVE")
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(Elder.tenant_id == tid)
    elders = scope_elder_query(db, user, q).order_by(Elder.first_name, Elder.last_name).limit(2000).all()
    ids = [e.id for e in elders]
    by_elder: dict[int, list[dict]] = {}
    if ids:
        rows = (
            db.query(CustomerPlan)
            .filter(CustomerPlan.elder_id.in_(ids))
            .order_by(CustomerPlan.start_date.desc(), CustomerPlan.id.desc())
            .all()
        )
        for r in rows:
            by_elder.setdefault(r.elder_id, []).append(plan_dict(db, r))
    sources: dict[int, str | None] = {}
    devices: set[int] = set()
    if ids:
        for eid, src in (
            db.query(ElderProspect.converted_elder_id, ElderProspect.source)
            .filter(ElderProspect.converted_elder_id.in_(ids))
            .order_by(ElderProspect.id)
            .all()
        ):
            sources.setdefault(eid, src)
        from app.models.iot_device import IotDevice

        devices = {
            r[0]
            for r in db.query(IotDevice.elder_id)
            .filter(IotDevice.elder_id.in_(ids), IotDevice.status == "active")
            .all()
        }
    managers: dict[int, str | None] = {}
    out, pending = [], []
    for e in elders:
        if e.manager_user_id and e.manager_user_id not in managers:
            managers[e.manager_user_id] = _user_name(db, e.manager_user_id)
        plans = by_elder.get(e.id, [])
        current = _current(plans)
        name = f"{e.first_name} {e.last_name}".strip()
        manager = managers.get(e.manager_user_id) if e.manager_user_id else None
        out.append({
            "elder_id": e.id,
            "customer_id": customer_code(e.id),
            "name": name,
            "phone": e.phone,
            "city": (e.custom_attributes or {}).get("city") or city_from_address(e.address),
            "referred_by": sources.get(e.id),
            "device_linked": e.id in devices,
            "care_manager": manager,
            "plan": current,
            "status": current["status"] if current else "none",
        })
        for p in plans:
            if p["status"] == "pending_approval":
                pending.append({**p, "name": name, "care_manager": manager})
    return {"customers": out, "pending": pending}


# --- Leads -------------------------------------------------------------------


def lead_dict(row: ElderProspect) -> dict:
    return {
        "id": row.id,
        "name": f"{row.first_name} {row.last_name}".strip(),
        "first_name": row.first_name,
        "last_name": row.last_name,
        "phone": row.phone,
        "email": row.email,
        "address": row.address,
        "pincode": row.pincode,
        "care_level": row.care_level,
        "source": row.source,
        "stage": board_stage(row),
        "status": row.status,
        "lost_reason": row.lost_reason,
        "converted_elder_id": row.converted_elder_id,
        "customer_id": customer_code(row.converted_elder_id) if row.converted_elder_id else None,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _lead_for(db: Session, user: User, lead_id: int) -> ElderProspect:
    from app.services.prospect_service import ProspectService

    return ProspectService.get_elder_prospect(db, lead_id, user)


def _naive_utc(t: datetime | None) -> datetime | None:
    if t is None or t.tzinfo is None:
        return t
    return t.astimezone(timezone.utc).replace(tzinfo=None)


def list_leads(
    db: Session,
    user: User,
    *,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    all_time: bool = False,
) -> list[dict]:
    """Leads for the Operations table. With ``created_from`` / ``created_to`` (or
    ``all_time``) every lead created in that window is listed, closed ones included;
    without them the old board rule applies (open + closed in the last 180 days)."""
    from app.services.prospect_service import ProspectService

    ProspectService._assert_elder_prospects(db, user)
    q = db.query(ElderProspect)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(ElderProspect.tenant_id == tid)
    created_from, created_to = _naive_utc(created_from), _naive_utc(created_to)
    if created_from is not None:
        q = q.filter(ElderProspect.created_at >= created_from)
    if created_to is not None:
        q = q.filter(ElderProspect.created_at < created_to)
    if created_from is None and created_to is None and not all_time:
        since = _now() - timedelta(days=CLOSED_DAYS_ON_BOARD)
        q = q.filter((ElderProspect.status == PROSPECT_STATUS_OPEN) | (ElderProspect.updated_at >= since))
    rows = q.order_by(ElderProspect.updated_at.desc()).limit(2000).all()
    since_by: dict[int, datetime] = {}
    comment_by: dict[int, str] = {}
    if rows:
        acts = (
            db.query(PipelineActivity)
            .filter(PipelineActivity.elder_prospect_id.in_([r.id for r in rows]))
            .order_by(PipelineActivity.created_at.desc(), PipelineActivity.id.desc())
            .all()
        )
        for a in acts:
            meta = a.metadata_ or {}
            pid = a.elder_prospect_id
            if pid not in since_by and a.activity_type == ACTIVITY_STAGE_CHANGE and meta.get("to"):
                since_by[pid] = a.created_at
            if pid not in comment_by:
                text = meta.get("comment") if a.activity_type == ACTIVITY_STAGE_CHANGE else a.body
                if text:
                    comment_by[pid] = str(text)[:500]
    # Won leads: their plan (Pending approval until an admin authorizes it).
    plan_by: dict[int, CustomerPlan] = {}
    won_ids = [r.id for r in rows if board_stage(r) == "WON"]
    if won_ids:
        for p in (
            db.query(CustomerPlan)
            .filter(CustomerPlan.prospect_id.in_(won_ids))
            .order_by(CustomerPlan.id.desc())
            .all()
        ):
            plan_by.setdefault(int(p.prospect_id), p)
    # Newest home assessment saved against the lead.
    assess_by: dict[int, HomeSafetyAssessmentRecord] = {}
    if rows:
        for a in (
            db.query(HomeSafetyAssessmentRecord)
            .filter(HomeSafetyAssessmentRecord.prospect_id.in_([r.id for r in rows]))
            .order_by(HomeSafetyAssessmentRecord.id.desc())
            .all()
        ):
            assess_by.setdefault(int(a.prospect_id), a)
    out = []
    for r in rows:
        d = lead_dict(r)
        since = since_by.get(r.id) or r.created_at
        d["stage_since"] = _iso(since)
        d["last_comment"] = comment_by.get(r.id)
        plan = plan_by.get(r.id)
        d["plan"] = plan_dict(db, plan) if plan is not None else None
        rec = assess_by.get(r.id)
        d["assessment"] = {"assessment_id": rec.assessment_id, "status": rec.status} if rec is not None else None
        out.append(d)
    return out


def add_comment(db: Session, user: User, lead_id: int, text: str) -> dict:
    """A note on the lead's history without changing its stage."""
    row = _lead_for(db, user, lead_id)
    note = (text or "").strip()[:MAX_COMMENT]
    if not note:
        _bad("Write a comment.")
    db.add(PipelineActivity(
        tenant_id=row.tenant_id,
        elder_prospect_id=row.id,
        activity_type=ACTIVITY_NOTE,
        body=note,
        metadata_={},
        created_by_user_id=user.id,
    ))
    row.updated_at = _now()
    db.commit()
    return {"ok": True}


def _month_start_utc(now: datetime | None = None) -> datetime:
    """Start of this month in India (IST, UTC+5:30), as naive UTC."""
    ist = (now or _now()) + timedelta(hours=5, minutes=30)
    start = ist.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(hours=5, minutes=30)


def dashboard_counts(db: Session, user: User) -> dict:
    """Key numbers for the ops Dashboard tiles. Leads are agency-wide (like the board);
    clients and plans follow the manager's team."""
    tid = resolve_tenant_id(user)
    eq = db.query(Elder.id).filter(Elder.status != "INACTIVE")
    if tid is not None:
        eq = eq.filter(Elder.tenant_id == tid)
    elder_ids = [r[0] for r in scope_elder_query(db, user, eq).all()]

    stages = {s: 0 for s in SALES_STAGES}
    month = _month_start_utc()
    won_month = lost_month = 0
    lq = db.query(ElderProspect)
    if tid is not None:
        lq = lq.filter(ElderProspect.tenant_id == tid)
    for row in lq.filter(
        (ElderProspect.status == PROSPECT_STATUS_OPEN) | (ElderProspect.updated_at >= month)
    ).all():
        st = board_stage(row)
        if st == "WON":
            won_month += 1
        elif st == "LOST":
            lost_month += 1
        else:
            stages[st] += 1

    today = date.today()
    pending = unpaid = ending = 0
    if elder_ids:
        for p in db.query(CustomerPlan).filter(CustomerPlan.elder_id.in_(elder_ids), CustomerPlan.status != "cancelled").all():
            status = effective_status(p, today)
            if status == "pending_approval":
                pending += 1
            if p.payment_status == "unpaid":
                unpaid += 1
            if status == "active" and p.end_date <= today + timedelta(days=30):
                ending += 1
    return {
        "active_clients": len(elder_ids),
        "leads": {s: stages[s] for s in SALES_STAGES if s not in ("WON", "LOST")},
        "won_this_month": won_month,
        "lost_this_month": lost_month,
        "pending_approval": pending,
        "unpaid_plans": unpaid,
        "plans_ending_30_days": ending,
    }


def _clean(v: str | None, limit: int) -> str | None:
    return " ".join((v or "").split())[:limit] or None


def update_lead(
    db: Session, user: User, lead_id: int, *, name: str, phone: str | None, email: str | None,
    address: str | None, pincode: str | None,
) -> dict:
    """Correct a lead's contact details and address. Won leads are edited on the customer."""
    row = _lead_for(db, user, lead_id)
    if board_stage(row) == "WON":
        _bad("This lead is a customer now. Edit the details on the customer page.")
    full = " ".join((name or "").split())[:200]
    if not full:
        _bad("Add a name.")
    if not (phone or "").strip() and not (email or "").strip():
        _bad("Add a mobile number or an email.")
    first, _, last = full.rpartition(" ")
    if not first:
        first, last = full, ""
    row.first_name, row.last_name = first[:100], last[:100]
    row.phone = (phone or "").strip()[:50] or None
    row.email = (email or "").strip()[:255] or None
    row.address = _clean(address, 500)
    row.pincode = _clean(pincode, 10)
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return lead_dict(row)


def delete_lead(db: Session, user: User, lead_id: int) -> dict:
    """Remove a lead added by mistake (a duplicate). Admins, or the lead's own owner.
    A lead with an assessment, a plan or a customer keeps its history: mark it lost instead."""
    from app.core.rbac import ADMIN_ROLES
    from app.livewell.assessment_start import lead_record

    row = _lead_for(db, user, lead_id)
    role = getattr(user.role, "value", user.role)
    if role not in {getattr(r, "value", r) for r in ADMIN_ROLES} and row.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only an admin or the lead's owner can delete it.")
    used = (
        row.converted_elder_id is not None
        or lead_record(db, row) is not None
        or db.query(HomeSafetyAssessmentRecord.id).filter(HomeSafetyAssessmentRecord.prospect_id == row.id).first() is not None
        or db.query(CustomerPlan.id).filter(CustomerPlan.prospect_id == row.id).first() is not None
    )
    if used:
        _bad("This lead has an assessment or a plan, so it can't be deleted. Mark it lost instead.")
    db.query(PipelineActivity).filter(PipelineActivity.elder_prospect_id == row.id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"ok": True}


def create_lead(
    db: Session, user: User, *, name: str, source: str | None, phone: str | None, email: str | None,
    address: str | None = None, pincode: str | None = None,
) -> dict:
    from app.schemas.prospects import ElderProspectCreate
    from app.services.prospect_service import ProspectService

    full = " ".join((name or "").split())[:200]
    if not full:
        _bad("Add a name.")
    if not (phone or "").strip() and not (email or "").strip():
        _bad("Add a mobile number or an email.")
    first, _, last = full.rpartition(" ")
    if not first:
        first, last = full, ""
    created = ProspectService.create_elder_prospect(
        db,
        ElderProspectCreate(
            first_name=first[:100],
            last_name=last[:100],
            phone=(phone or "").strip() or None,
            email=(email or "").strip() or None,
            source=(source or "").strip()[:100] or None,
        ),
        user,
    )
    from app.livewell import team_alerts

    row = _lead_for(db, user, created["id"])
    if _clean(address, 500) or _clean(pincode, 10):
        row.address = _clean(address, 500)
        row.pincode = _clean(pincode, 10)
        db.commit()
    team_alerts.alert_team(
        db, row.tenant_id, "lead_new", f"New lead: {full}",
        f"Added by {user.first_name} {user.last_name}. Phone: {row.phone or 'not given'}.",
        path="/kushalaya/enquiries",
    )
    return lead_dict(row)


def lead_history(db: Session, user: User, lead_id: int) -> list[dict]:
    row = _lead_for(db, user, lead_id)
    acts = (
        db.query(PipelineActivity)
        .filter(PipelineActivity.elder_prospect_id == row.id)
        .order_by(PipelineActivity.created_at.desc(), PipelineActivity.id.desc())
        .limit(200)
        .all()
    )
    out = []
    for a in acts:
        meta = a.metadata_ or {}
        frm = meta.get("from")
        to = meta.get("to")
        out.append({
            "id": a.id,
            "type": a.activity_type,
            "from": frm,
            "to": to,
            "from_label": STAGE_LABELS.get(_LEGACY_COLUMN.get(frm, frm), frm) if frm else None,
            "to_label": STAGE_LABELS.get(_LEGACY_COLUMN.get(to, to), to) if to else None,
            "comment": meta.get("comment") if "comment" in meta else None,
            "body": a.body,
            "by": _user_name(db, a.created_by_user_id),
            "at": _iso(a.created_at),
        })
    return out


def _won_elder(db: Session, user: User, row: ElderProspect, elder_id: int | None) -> Elder:
    """The client for a Won lead: already linked, the one picked, or a new one."""
    from app.livewell.family_elder_link import absorb_prospect_into_elder
    from app.schemas.elder import ElderCreate
    from app.services.elder_service import ElderService

    from app.livewell.assessment_start import LEAD_KEY, lead_record

    started = None if row.converted_elder_id else lead_record(db, row)
    if row.converted_elder_id:
        elder = _elder_for(db, user, int(row.converted_elder_id))
    elif elder_id:
        elder = _elder_for(db, user, int(elder_id))
    elif started is not None:
        # The hidden record made when an assessment was started for this lead:
        # it becomes the client, so the assessment stays linked.
        elder = _elder_for(db, user, started.id)
        elder.status = "ACTIVE"
        attrs = dict(elder.custom_attributes or {})
        attrs.pop(LEAD_KEY, None)
        attrs["from_lead_id"] = row.id
        elder.custom_attributes = attrs
    else:
        elder = ElderService.create_elder(
            db,
            ElderCreate(
                tenant_id=row.tenant_id,
                first_name=row.first_name,
                last_name=row.last_name or "",
                phone=row.phone,
                address=row.address,
                care_level=row.care_level,
                status="ACTIVE",
            ),
            user,
        )
    if elder.tenant_id != row.tenant_id:
        _bad("Lead and client must belong to the same agency.", 400)
    if started is not None and started.id != elder.id:
        # Linked to an existing client instead: the lead's assessment follows it.
        from app.models.care_job import CareJob
        from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

        db.query(CareJob).filter(CareJob.elder_id == started.id).update(
            {CareJob.elder_id: elder.id}, synchronize_session=False
        )
        db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.elder_id == started.id).update(
            {HomeSafetyAssessmentRecord.elder_id: elder.id}, synchronize_session=False
        )
    # Assessments, photos and documents follow the client; the lead and its history stay.
    absorb_prospect_into_elder(db, prospect_id=row.id, elder_id=elder.id, keep_lead=True)
    return elder


def move_lead(
    db: Session,
    user: User,
    lead_id: int,
    *,
    to: str,
    comment: str | None = None,
    plan_id: str | None = None,
    billing_cycle: str | None = None,
    start_date: date | None = None,
    elder_id: int | None = None,
    coupon_code: str | None = None,
) -> dict:
    row = _lead_for(db, user, lead_id)
    if to not in SALES_STAGES:
        _bad("Unknown stage.")
    current = board_stage(row)
    if current == "WON":
        _bad("This lead is already won. Change the plan from the client's profile.", 400)
    if to == current:
        _bad("The lead is already in that stage.", 400)
    note = (comment or "").strip()[:MAX_COMMENT]
    if to == "LOST" and not note:
        _bad("Say why the lead was lost.")

    meta: dict = {"from": current, "to": to, "comment": note or None}
    plan_row: CustomerPlan | None = None
    if to == "WON":
        priced = price_plan(db, row.tenant_id, plan_id, billing_cycle, coupon_code)  # validate before creating anything
        elder = _won_elder(db, user, row, elder_id)
        plan_row = create_plan(
            db, user, elder,
            plan_id=plan_id, billing_cycle=billing_cycle, start_date=start_date, prospect_id=row.id,
            priced=priced,
        )
        row.converted_elder_id = elder.id
        row.status = PROSPECT_STATUS_WON
        meta.update({"elder_id": elder.id, "customer_plan_id": plan_row.id, "plan_id": plan_row.plan_id,
                     "billing_cycle": plan_row.billing_cycle, "amount_paise": plan_row.amount_paise,
                     "coupon_code": plan_row.coupon_code, "discount_paise": plan_row.discount_paise})
    elif to == "LOST":
        row.status = PROSPECT_STATUS_LOST
        row.lost_reason = note[:500]
    else:
        row.status = PROSPECT_STATUS_OPEN
        row.lost_reason = None

    body = f"{STAGE_LABELS.get(current, current)} → {STAGE_LABELS[to]}"
    if note:
        body += f": {note}"
    row.stage = to
    db.add(PipelineActivity(
        tenant_id=row.tenant_id,
        elder_prospect_id=row.id,
        activity_type=ACTIVITY_STAGE_CHANGE,
        body=body[:MAX_COMMENT + 100],
        metadata_=meta,
        created_by_user_id=user.id,
    ))
    db.commit()
    db.refresh(row)
    out = lead_dict(row)
    if plan_row is not None:
        db.refresh(plan_row)
        out["customer_plan"] = plan_dict(db, plan_row)
    return out
