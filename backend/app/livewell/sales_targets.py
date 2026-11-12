"""Team targets: each person's monthly KPIs against the target an admin set.

Credit goes to the lead's owner (the person who created it, unless reassigned); a lead
with no owner counts under "Unassigned". Revenue is the plan amount (integer paise) of
plans created in the month that are not cancelled, credited to the lead's owner, else to
whoever created the plan. Targets live in tenant.workflow_config["sales_targets"] as
{"YYYY-MM": {"<user id>": {"<kpi>": value}}}; a month with none set uses the latest
earlier month, so targets carry forward until changed.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.pipeline_constants import ACTIVITY_STAGE_CHANGE
from app.models.customer_plan import CustomerPlan
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.tenant import Tenant
from app.models.user import User

KEY = "sales_targets"
IST = ZoneInfo("Asia/Kolkata")
KPIS: list[dict] = [
    {"key": "leads", "label": "Leads added", "unit": "count"},
    {"key": "assessments_booked", "label": "Assessments booked", "unit": "count"},
    {"key": "assessments_done", "label": "Assessments completed", "unit": "count"},
    {"key": "won", "label": "Customers won", "unit": "count"},
    {"key": "revenue_paise", "label": "Revenue", "unit": "paise"},
]
KPI_KEYS = [k["key"] for k in KPIS]
STAGE_KPI = {"ASSESSMENT_SCHEDULED": "assessments_booked", "ASSESSMENT_DONE": "assessments_done", "WON": "won"}
STAFF_ROLES = ("TENANT_ADMIN", "CARE_MANAGER")
UNASSIGNED = 0
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def current_month(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(IST).strftime("%Y-%m")


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """Start and end of the month in IST, as naive UTC (how these tables store times)."""
    if not MONTH_RE.match(month or ""):
        raise ValueError("Month must look like 2026-11")
    y, m = int(month[:4]), int(month[5:])
    start = datetime(y, m, 1, tzinfo=IST)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=IST)
    return tuple(t.astimezone(timezone.utc).replace(tzinfo=None) for t in (start, end))  # type: ignore[return-value]


def _naive(t: datetime | None) -> datetime | None:
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t is not None and t.tzinfo else t


def targets_for(tenant: Tenant, month: str) -> dict[int, dict[str, int]]:
    stored = ((tenant.workflow_config or {}).get(KEY) or {})
    use = month if month in stored else max((m for m in stored if m <= month), default=None)
    raw = stored.get(use, {}) if use else {}
    return {int(uid): {k: int(v) for k, v in (vals or {}).items() if k in KPI_KEYS} for uid, vals in raw.items()}


def save_targets(db: Session, tenant: Tenant, month: str, user_id: int, values: dict) -> None:
    month_bounds(month)
    cfg = dict(tenant.workflow_config or {})
    stored = dict(cfg.get(KEY) or {})
    # Start the month from what was carrying forward, so editing one person keeps the rest.
    if month not in stored:
        stored[month] = {str(u): dict(v) for u, v in targets_for(tenant, month).items()}
    month_targets = dict(stored[month])
    clean = {k: max(0, int(values[k])) for k in KPI_KEYS if values.get(k) not in (None, "")}
    month_targets[str(user_id)] = clean
    stored[month] = month_targets
    cfg[KEY] = stored
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()


def achievements(db: Session, tenant_id: int, month: str) -> dict[int, dict[str, int]]:
    start, end = month_bounds(month)
    out: dict[int, dict[str, int]] = {}

    def add(uid: int | None, kpi: str, amount: int = 1) -> None:
        row = out.setdefault(uid or UNASSIGNED, {k: 0 for k in KPI_KEYS})
        row[kpi] += amount

    leads = {p.id: p for p in db.query(ElderProspect).filter(ElderProspect.tenant_id == tenant_id).all()}
    for p in leads.values():
        created = _naive(p.created_at)
        if created and start <= created < end:
            add(p.owner_user_id, "leads")

    moves = (
        db.query(PipelineActivity)
        .filter(
            PipelineActivity.tenant_id == tenant_id,
            PipelineActivity.activity_type == ACTIVITY_STAGE_CHANGE,
            PipelineActivity.elder_prospect_id.isnot(None),
        )
        .all()
    )
    counted: set[tuple[int, str]] = set()  # a lead counts once per KPI per month
    for a in moves:
        when = _naive(a.created_at)
        kpi = STAGE_KPI.get(str((a.metadata_ or {}).get("to") or "").upper())
        if not kpi or not when or not (start <= when < end) or (a.elder_prospect_id, kpi) in counted:
            continue
        counted.add((a.elder_prospect_id, kpi))
        lead = leads.get(a.elder_prospect_id)
        add((lead.owner_user_id if lead else None) or a.created_by_user_id, kpi)

    plans = db.query(CustomerPlan).filter(CustomerPlan.tenant_id == tenant_id, CustomerPlan.status != "cancelled").all()
    for plan in plans:
        created = _naive(plan.created_at)
        if not created or not (start <= created < end):
            continue
        lead = leads.get(plan.prospect_id) if plan.prospect_id else None
        add((lead.owner_user_id if lead else None) or plan.created_by_user_id, "revenue_paise", int(plan.amount_paise or 0))
    return out


def report(db: Session, viewer: User, tenant_id: int, month: str, *, everyone: bool) -> dict:
    tenant = db.get(Tenant, tenant_id)
    targets = targets_for(tenant, month)
    done = achievements(db, tenant_id, month)
    staff = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.status == "ACTIVE", User.role.in_(STAFF_ROLES))
        .order_by(User.first_name)
        .all()
    )
    people = [(u.id, f"{u.first_name} {u.last_name}".strip() or u.email) for u in staff]
    if everyone and done.get(UNASSIGNED):
        people.append((UNASSIGNED, "Unassigned"))
    if not everyone:
        people = [p for p in people if p[0] == viewer.id]
    rows = []
    for uid, name in people:
        got = done.get(uid) or {k: 0 for k in KPI_KEYS}
        tgt = targets.get(uid, {})
        rows.append({
            "user_id": uid,
            "name": name,
            "kpis": [
                {
                    "key": k["key"],
                    "label": k["label"],
                    "unit": k["unit"],
                    "target": tgt.get(k["key"]),
                    "achieved": got[k["key"]],
                    "percent": round(got[k["key"]] * 100 / tgt[k["key"]]) if tgt.get(k["key"]) else None,
                }
                for k in KPIS
            ],
        })
    now_ist = datetime.now(timezone.utc).astimezone(IST).date()
    first = date(int(month[:4]), int(month[5:]), 1)
    return {"month": month, "as_of": now_ist.isoformat() if month == current_month() else None,
            "month_start": first.isoformat(), "kpis": KPIS, "people": rows}
