"""Owner dashboard (#101) and monthly CSV exports (#103). Admins only.

Months are IST calendar months. Money is integer paise; CSVs write rupees with
two decimals (from paise, no float). Definitions used on the dashboard:

- Cash collected: successful wallet top-ups in the month (money that came in).
  "Billed" is invoices issued in the month minus credit notes.
- Dues: orders sent to the family (or booked / done) and not yet paid, plus
  service requests with a price waiting for the family's approval. Age is days
  since the quote was sent, as of the end of the month (or now, this month).
- Orders pipeline: orders created in the month, total ₹ by status.
- Gross margin: orders paid in the month (not cancelled): (price after discount
  − product cost) / price after discount. GST is not revenue.
- Visits: care jobs scheduled in the month: planned (not cancelled), done, missed.
- SOS acknowledge time: median minutes from opened to acknowledged for alerts
  opened in the month.
- Reassessment compliance: active clients whose last completed assessment is
  within 182 days of the month end, over all active clients.
- Staff utilisation: hours of completed visits (check-in → done, else the
  booked length) over available hours = active caregivers × available hours a
  month (workflow_config["business"]["available_hours_per_caregiver"], default
  208 = 26 days × 8 h).
- Clients: new = created in the month; churned = made inactive in the month
  (status inactive / discharged and last updated in the month).
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Iterator

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.csv_safe import csv_safe_row
from app.core.responses import raise_bad_request
from app.livewell.gst_invoices import IST, STATE_NAMES
from app.models.care_job import CareJob
from app.models.caregiver import Caregiver
from app.models.commerce import Order
from app.models.elder import Elder
from app.models.family_wallet import FamilyWallet, WalletTransaction
from app.models.tax_invoice import TaxInvoice
from app.models.tenant import Tenant

DEFAULT_AVAILABLE_HOURS = 208
INACTIVE_ELDER = ("INACTIVE", "DISCHARGED", "ARCHIVED", "DELETED")
INACTIVE_CAREGIVER = ("INACTIVE", "TERMINATED", "EXITED", "ARCHIVED")
REASSESS_DAYS = 182
AGING_BUCKETS = (("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, 10**9))
DUE_ORDER_STATUSES = ("quoted", "family_accepted", "scheduled", "completed")


# --- Month helpers ---------------------------------------------------------------


def parse_month(value: str | None, now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    if not value:
        d = now.astimezone(IST)
        return date(d.year, d.month, 1)
    m = re.match(r"^(\d{4})-(\d{2})$", value.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise_bad_request("Month must look like 2026-10")
    return date(int(m.group(1)), int(m.group(2)), 1)


def _next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _prev_month(d: date) -> date:
    return date(d.year - (d.month == 1), (d.month - 2) % 12 + 1, 1)


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """[start, end) of an IST month, as UTC datetimes."""
    start = datetime(month.year, month.month, 1, tzinfo=IST).astimezone(timezone.utc)
    nxt = _next_month(month)
    end = datetime(nxt.year, nxt.month, 1, tzinfo=IST).astimezone(timezone.utc)
    return start, end


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def rupees(paise: int | None) -> str:
    """Paise → '1234.50' (no float)."""
    p = int(paise or 0)
    sign = "-" if p < 0 else ""
    whole, frac = divmod(abs(p), 100)
    return f"{sign}{whole}.{frac:02d}"


def _ist(dt: datetime | None, fmt: str = "%Y-%m-%d") -> str:
    dt = _aware(dt)
    return dt.astimezone(IST).strftime(fmt) if dt else ""


def _job_minutes(job_start, job_done, booked) -> int:
    s, e = _aware(job_start), _aware(job_done)
    if s and e and e > s:
        return int((e - s).total_seconds() // 60)
    return int(booked or 60)


def _name(first, last) -> str:
    return f"{first or ''} {last or ''}".strip()


# --- Dues ------------------------------------------------------------------------


def dues_rows(db: Session, tenant_id: int, as_of: datetime) -> list[dict]:
    """Unpaid amounts owed by families, oldest first."""
    rows: list[dict] = []
    q = (
        db.query(Order.id, Order.elder_id, Order.status, Order.total_paise, Order.paid_paise,
                 Order.quoted_at, Order.created_at, Elder.first_name, Elder.last_name)
        .join(Elder, Elder.id == Order.elder_id)
        .filter(Order.tenant_id == tenant_id, Order.status.in_(DUE_ORDER_STATUSES),
                Order.total_paise > func.coalesce(Order.paid_paise, 0),
                func.coalesce(Order.quoted_at, Order.created_at) < as_of)
    )
    for oid, eid, status, total, paid, quoted_at, created_at, fn, ln in q:
        since = _aware(quoted_at or created_at)
        rows.append({
            "kind": "order", "ref": f"Order #{oid}", "elder_id": eid, "client": _name(fn, ln), "status": status,
            "since": since, "days": max(0, (as_of - since).days) if since else 0,
            "amount_paise": int(total or 0) - int(paid or 0),
        })
    # Service requests with a price the family hasn't approved yet (stored on the client).
    for eid, fn, ln, attrs in db.query(Elder.id, Elder.first_name, Elder.last_name, Elder.custom_attributes).filter(
        Elder.tenant_id == tenant_id
    ):
        reqs = ((attrs or {}).get("safe_home") or {}).get("service_requests") if isinstance(attrs, dict) else None
        for r in reqs if isinstance(reqs, list) else []:
            if not isinstance(r, dict) or r.get("payment_status") != "awaiting_approval":
                continue
            if str(r.get("status") or "") in ("cancelled", "declined"):
                continue
            try:
                amount = int(r.get("quoted_amount_minor") or 0)
                since = _aware(datetime.fromisoformat(str(r.get("updated_at") or r.get("created_at"))))
            except (TypeError, ValueError):
                continue
            if amount <= 0 or not since or since >= as_of:
                continue
            rows.append({
                "kind": "service_request", "ref": str(r.get("service_type") or "service").replace("_", " ").capitalize(),
                "elder_id": eid, "client": _name(fn, ln), "status": "awaiting approval",
                "since": since, "days": max(0, (as_of - since).days), "amount_paise": amount,
            })
    rows.sort(key=lambda r: -r["days"])
    return rows


def aging(rows: list[dict]) -> list[dict]:
    out = []
    for label, lo, hi in AGING_BUCKETS:
        hit = [r for r in rows if lo <= r["days"] <= hi]
        out.append({"bucket": label, "count": len(hit), "amount_paise": sum(r["amount_paise"] for r in hit)})
    return out


# --- Dashboard -------------------------------------------------------------------


def _cash(db: Session, tenant_id: int, start: datetime, end: datetime) -> int:
    return int(
        db.query(func.coalesce(func.sum(WalletTransaction.amount_minor), 0))
        .filter(WalletTransaction.tenant_id == tenant_id, WalletTransaction.kind == "recharge",
                WalletTransaction.status == "success",
                WalletTransaction.created_at >= start, WalletTransaction.created_at < end)
        .scalar() or 0
    )


def _billed(db: Session, tenant_id: int, start: datetime, end: datetime) -> int:
    rows = (
        db.query(TaxInvoice.kind, func.coalesce(func.sum(TaxInvoice.total_paise), 0))
        .filter(TaxInvoice.tenant_id == tenant_id, TaxInvoice.issued_at >= start, TaxInvoice.issued_at < end)
        .group_by(TaxInvoice.kind)
        .all()
    )
    d = {k: int(v or 0) for k, v in rows}
    return d.get("invoice", 0) - d.get("credit_note", 0)


def _satisfaction(db: Session, tenant_id: int, start: datetime, end: datetime) -> dict:
    try:
        from app.models.kushlife_quality import NpsResponse, VisitRating
    except Exception:  # noqa: BLE001 — ratings ship in a separate update
        return {"available": False, "message": "Ratings start after the next update"}
    try:
        avg, count = (
            db.query(func.avg(VisitRating.rating), func.count(VisitRating.id))
            .filter(VisitRating.tenant_id == tenant_id, VisitRating.created_at >= start, VisitRating.created_at < end)
            .one()
        )
        scores = [
            int(s) for (s,) in db.query(NpsResponse.score).filter(
                NpsResponse.tenant_id == tenant_id, NpsResponse.score.isnot(None),
                NpsResponse.created_at >= start, NpsResponse.created_at < end,
            )
        ]
    except Exception:  # noqa: BLE001 — table not created yet on this server
        db.rollback()
        return {"available": False, "message": "Ratings start after the next update"}
    nps = None
    if scores:
        promoters = sum(1 for s in scores if s >= 9)
        detractors = sum(1 for s in scores if s <= 6)
        nps = round((promoters - detractors) * 100 / len(scores))
    return {
        "available": True,
        "ratings": int(count or 0),
        "average_rating": round(float(avg), 2) if avg is not None else None,
        "nps_responses": len(scores),
        "nps": nps,
    }


def dashboard(db: Session, tenant: Tenant, month: date, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    tid = tenant.id
    start, end = month_bounds(month)
    prev_start, prev_end = month_bounds(_prev_month(month))
    as_of = min(end, now)

    # Dues
    dues = dues_rows(db, tid, as_of)

    # Orders pipeline (created in the month)
    pipeline = [
        {"status": s, "count": int(c), "amount_paise": int(a or 0)}
        for s, c, a in db.query(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total_paise), 0))
        .filter(Order.tenant_id == tid, Order.created_at >= start, Order.created_at < end)
        .group_by(Order.status)
        .all()
    ]

    # Gross margin (orders paid in the month)
    rev, cost, n_paid = (
        db.query(
            func.coalesce(func.sum(Order.subtotal_paise - Order.discount_paise), 0),
            func.coalesce(func.sum(Order.cost_paise), 0),
            func.count(Order.id),
        )
        .filter(Order.tenant_id == tid, Order.status != "cancelled", Order.paid_at >= start, Order.paid_at < end)
        .one()
    )
    rev, cost = int(rev or 0), int(cost or 0)

    # Visits
    visit_counts = dict(
        db.query(CareJob.status, func.count(CareJob.id))
        .filter(CareJob.tenant_id == tid, CareJob.scheduled_at >= start, CareJob.scheduled_at < end)
        .group_by(CareJob.status)
        .all()
    )
    planned = sum(int(v) for k, v in visit_counts.items() if k != "cancelled")

    # SOS acknowledge time
    from app.models.incident import Incident

    pairs = (
        db.query(Incident.opened_at, Incident.acknowledged_at)
        .filter(Incident.tenant_id == tid, Incident.opened_at >= start, Incident.opened_at < end)
        .all()
    )
    ack_minutes = [
        (_aware(a) - _aware(o)).total_seconds() / 60 for o, a in pairs if o and a and _aware(a) >= _aware(o)
    ]

    # Reassessment compliance (as of month end)
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    active_ids = {
        r[0] for r in db.query(Elder.id).filter(Elder.tenant_id == tid, func.upper(Elder.status).notin_(INACTIVE_ELDER))
    }
    cutoff = as_of - timedelta(days=REASSESS_DAYS)
    last = (
        db.query(HomeSafetyAssessmentRecord.elder_id,
                 func.max(func.coalesce(HomeSafetyAssessmentRecord.completed_at, HomeSafetyAssessmentRecord.updated_at)))
        .filter(HomeSafetyAssessmentRecord.status == "completed",
                HomeSafetyAssessmentRecord.elder_id.in_(list(active_ids) or [-1]))
        .group_by(HomeSafetyAssessmentRecord.elder_id)
        .all()
    )
    in_date = sum(1 for _eid, at in last if at and cutoff <= _aware(at) <= as_of)

    # Staff utilisation
    hours_each = int(((tenant.workflow_config or {}).get("business") or {}).get("available_hours_per_caregiver")
                     or DEFAULT_AVAILABLE_HOURS)
    caregivers = (
        db.query(func.count(Caregiver.id))
        .filter(Caregiver.tenant_id == tid, func.upper(Caregiver.status).notin_(INACTIVE_CAREGIVER))
        .scalar() or 0
    )
    minutes = sum(
        _job_minutes(ci, done, booked)
        for ci, done, booked in db.query(CareJob.checked_in_at, CareJob.completed_at, CareJob.duration_minutes).filter(
            CareJob.tenant_id == tid, CareJob.status == "completed",
            CareJob.scheduled_at >= start, CareJob.scheduled_at < end,
        )
    )
    available = int(caregivers) * hours_each

    # Clients
    new_clients = db.query(func.count(Elder.id)).filter(
        Elder.tenant_id == tid, Elder.created_at >= start, Elder.created_at < end
    ).scalar() or 0
    churned = db.query(func.count(Elder.id)).filter(
        Elder.tenant_id == tid, func.upper(Elder.status).in_(INACTIVE_ELDER),
        Elder.updated_at >= start, Elder.updated_at < end,
    ).scalar() or 0

    first = db.query(func.min(Elder.created_at)).filter(Elder.tenant_id == tid).scalar() or tenant.created_at
    return {
        "month": month.strftime("%Y-%m"),
        # The month picker starts here, not before the business had any clients.
        "first_month": _aware(first).astimezone(IST).strftime("%Y-%m") if first else None,
        "as_of": as_of.isoformat(),
        "cash": {
            "this_month_paise": _cash(db, tid, start, end),
            "last_month_paise": _cash(db, tid, prev_start, prev_end),
            "billed_paise": _billed(db, tid, start, end),
        },
        "dues": {
            "total_paise": sum(r["amount_paise"] for r in dues),
            "count": len(dues),
            "aging": aging(dues),
        },
        "pipeline": sorted(pipeline, key=lambda r: -r["amount_paise"]),
        "margin": {
            "orders": int(n_paid or 0),
            "revenue_paise": rev,
            "cost_paise": cost,
            "margin_paise": rev - cost,
            "margin_bp": ((rev - cost) * 10000 // rev) if rev else None,
        },
        "visits": {
            "planned": planned,
            "done": int(visit_counts.get("completed", 0)),
            "missed": int(visit_counts.get("missed", 0)),
            "cancelled": int(visit_counts.get("cancelled", 0)),
        },
        "sos": {
            "alerts": len(pairs),
            "acknowledged": len(ack_minutes),
            "median_ack_minutes": round(median(ack_minutes), 1) if ack_minutes else None,
        },
        "reassessment": {
            "active_clients": len(active_ids),
            "in_date": in_date,
            "percent": round(in_date * 100 / len(active_ids)) if active_ids else None,
        },
        "utilisation": {
            "caregivers": int(caregivers),
            "visit_hours": round(minutes / 60, 1),
            "available_hours": available,
            "percent": round(minutes * 100 / 60 / available) if available else None,
        },
        "clients": {"new": int(new_clients), "churned": int(churned), "active": len(active_ids)},
        "satisfaction": _satisfaction(db, tid, start, end),
    }


# --- CSV exports -----------------------------------------------------------------

EXPORTS = {
    "gst-register": "GST register (invoices and credit notes)",
    "dues": "Dues (unpaid, aged)",
    "payments": "Payments and wallet ledger",
    "visits": "Visits",
    "payroll": "Payroll hours per caregiver",
}


def _csv_stream(header: list[str], rows) -> Iterator[str]:
    buf = io.StringIO()
    writer = csv.writer(buf)
    buf.write("﻿")  # Excel opens UTF-8 (₹, Telugu names) correctly
    writer.writerow(header)
    yield buf.getvalue()
    for row in rows:
        buf.seek(0)
        buf.truncate(0)
        writer.writerow(csv_safe_row(row))
        yield buf.getvalue()


def export_csv(db: Session, tenant: Tenant, kind: str, month: date, *, now: datetime | None = None) -> Iterator[str]:
    now = now or datetime.now(timezone.utc)
    tid = tenant.id
    start, end = month_bounds(month)

    if kind == "gst-register":
        originals = {}

        def gst_rows():
            q = (
                db.query(TaxInvoice)
                .filter(TaxInvoice.tenant_id == tid, TaxInvoice.issued_at >= start, TaxInvoice.issued_at < end)
                .order_by(TaxInvoice.issued_at, TaxInvoice.id)
            )
            for inv in q.yield_per(500):
                sign = -1 if inv.kind == "credit_note" else 1
                orig = ""
                if inv.original_invoice_id:
                    if inv.original_invoice_id not in originals:
                        o = db.get(TaxInvoice, inv.original_invoice_id)
                        originals[inv.original_invoice_id] = o.number if o else ""
                    orig = originals[inv.original_invoice_id]
                cus = inv.customer or {}
                yield [
                    _ist(inv.issued_at), inv.number,
                    "Credit note" if inv.kind == "credit_note" else (
                        "Tax invoice" if inv.doc_type == "tax_invoice" else "Bill of supply"),
                    orig, cus.get("name", ""), cus.get("gstin", ""),
                    f"{inv.place_of_supply}-{STATE_NAMES.get(inv.place_of_supply, '')}",
                    ";".join(sorted({str(ln.get("hsn_sac", "")) for ln in inv.lines or []})),
                    rupees(sign * inv.taxable_paise), rupees(sign * inv.cgst_paise), rupees(sign * inv.sgst_paise),
                    rupees(sign * inv.igst_paise), rupees(sign * inv.total_paise), f"{inv.source_type}:{inv.source_id}",
                ]

        return _csv_stream(
            ["Date (IST)", "Number", "Type", "Against invoice", "Customer", "Customer GSTIN", "Place of supply",
             "HSN/SAC", "Taxable value (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total (₹)", "For"],
            gst_rows(),
        )

    if kind == "dues":
        as_of = min(end, now)
        return _csv_stream(
            ["As of (IST)", "Client", "What", "Status", "Since (IST)", "Days", "Bucket", "Amount due (₹)"],
            (
                [_ist(as_of), r["client"], r["ref"], r["status"], _ist(r["since"]), r["days"],
                 next(b for b, lo, hi in AGING_BUCKETS if lo <= r["days"] <= hi), rupees(r["amount_paise"])]
                for r in dues_rows(db, tid, as_of)
            ),
        )

    if kind == "payments":
        q = (
            db.query(WalletTransaction, Elder.first_name, Elder.last_name)
            .join(FamilyWallet, FamilyWallet.id == WalletTransaction.wallet_id)
            .join(Elder, Elder.id == FamilyWallet.elder_id)
            .filter(WalletTransaction.tenant_id == tid, WalletTransaction.created_at >= start,
                    WalletTransaction.created_at < end)
            .order_by(WalletTransaction.created_at, WalletTransaction.id)
        )
        return _csv_stream(
            ["Date (IST)", "Time (IST)", "Entry", "Client", "Type", "Status", "Amount (₹)", "Balance after (₹)",
             "For", "Gateway", "Gateway payment id", "Note"],
            (
                [_ist(t.created_at), _ist(t.created_at, "%H:%M"), t.public_id, _name(fn, ln), t.kind, t.status,
                 rupees(t.amount_minor), rupees(t.balance_after_minor) if t.balance_after_minor is not None else "",
                 f"{t.reference_type}:{t.reference_id}" if t.reference_type else "", t.gateway or "",
                 t.gateway_payment_id or "", t.note or ""]
                for t, fn, ln in q.yield_per(500)
            ),
        )

    if kind == "visits":
        q = (
            db.query(CareJob, Elder.first_name, Elder.last_name, Caregiver.first_name, Caregiver.last_name)
            .join(Elder, Elder.id == CareJob.elder_id)
            .outerjoin(Caregiver, Caregiver.id == CareJob.caregiver_id)
            .filter(CareJob.tenant_id == tid, CareJob.scheduled_at >= start, CareJob.scheduled_at < end)
            .order_by(CareJob.scheduled_at, CareJob.id)
        )
        return _csv_stream(
            ["Date (IST)", "Time (IST)", "Client", "Caregiver", "Kind", "Title", "Status", "Checked in (IST)",
             "Completed (IST)", "Minutes"],
            (
                [_ist(j.scheduled_at), _ist(j.scheduled_at, "%H:%M"), _name(efn, eln), _name(cfn, cln), j.kind,
                 j.title, j.status, _ist(j.checked_in_at, "%Y-%m-%d %H:%M"), _ist(j.completed_at, "%Y-%m-%d %H:%M"),
                 _job_minutes(j.checked_in_at, j.completed_at, j.duration_minutes) if j.status == "completed" else ""]
                for j, efn, eln, cfn, cln in q.yield_per(500)
            ),
        )

    if kind == "payroll":
        per: dict[int, dict] = {}
        q = (
            db.query(CareJob.caregiver_id, CareJob.status, CareJob.checked_in_at, CareJob.completed_at,
                     CareJob.duration_minutes)
            .filter(CareJob.tenant_id == tid, CareJob.caregiver_id.isnot(None),
                    CareJob.scheduled_at >= start, CareJob.scheduled_at < end)
        )
        for cg_id, status, ci, done, booked in q:
            row = per.setdefault(cg_id, {"done": 0, "missed": 0, "minutes": 0})
            if status == "completed":
                row["done"] += 1
                row["minutes"] += _job_minutes(ci, done, booked)
            elif status == "missed":
                row["missed"] += 1
        names = {
            c.id: (_name(c.first_name, c.last_name), c.status)
            for c in db.query(Caregiver).filter(Caregiver.id.in_(list(per) or [-1]))
        }

        def payroll_rows():
            for cg_id, r in sorted(per.items(), key=lambda kv: names.get(kv[0], ("", ""))[0]):
                name, status = names.get(cg_id, ("", ""))
                h, m = divmod(r["minutes"], 60)
                yield [month.strftime("%Y-%m"), cg_id, name, status, r["done"], r["missed"], r["minutes"],
                       f"{h}.{m * 100 // 60:02d}"]

        return _csv_stream(
            ["Month", "Caregiver id", "Caregiver", "Status", "Visits done", "Visits missed", "Minutes", "Hours"],
            payroll_rows(),
        )

    raise_bad_request("Unknown export")
