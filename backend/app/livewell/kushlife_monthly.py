"""KushLife K3 (#100): the monthly letter, and vitals trends.

* ``draft_monthly_letters``: run by the jobs timer (every 2 min). From the 1st, 07:00 IST, it
  drafts one letter per active client who had a completed visit last month. One row per
  client per month (unique constraint), so repeated ticks never draft twice.
* The client's care manager edits the letter (text, own note, next month's plan) and
  approves it — same gate as the weekly summary. Only approved letters reach the family
  (portal page + PDF, and an email under the family event ``monthly_letter``).
* ``vitals_series``: BP / oxygen / pulse from KushLife visits over the last ~3 months, with
  the client's normal, for the SVG trend charts (family Home, ops client page).

Templates only — no AI calls. Care observation, not diagnosis.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.responses import WorkforceHTTPError, raise_bad_request, raise_not_found
from app.livewell import kushlife as kl
from app.livewell import kushlife_weekly as kw
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.kushlife_quality import KushLifeMonthly
from app.livewell.brand import safety_score_name

logger = logging.getLogger(__name__)

IST = kw.IST
DRAFT_HOUR_IST = 7  # 1st of the month, 07:00 IST
OVERDUE_DAY = (5, 18)  # 5th of the month, 18:00 IST
_INACTIVE = ("inactive", "archived", "deleted", "discharged")
_VISIT_KINDS = ("visit", "install")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(IST)


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def prev_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def last_month_start(now: datetime | None = None) -> date:
    return prev_month(_now(now).date())


def _bounds(first: date) -> tuple[datetime, datetime]:
    """[start, end) of the month in UTC (SQLite keeps naive UTC, so compare in UTC)."""
    start = datetime.combine(first, time(0, 0), tzinfo=IST)
    end = datetime.combine(next_month(first), time(0, 0), tzinfo=IST)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def overdue_at(first: date) -> datetime:
    day, hour = OVERDUE_DAY
    return datetime.combine(next_month(first).replace(day=day), time(hour, 0), tzinfo=IST)


def month_label(first: date) -> str:
    return first.strftime("%B %Y")


# --- the month in numbers ----------------------------------------------------------


def _in_month(visits: list[dict], first: date) -> list[dict]:
    start, end = _bounds(first)
    out = []
    for v in visits:
        if not v["date"]:
            continue
        at = kl._aware(datetime.fromisoformat(v["date"]))
        if start <= at < end:
            out.append(v)
    return out


def _jobs_in(db: Session, elder_id: int, first: date) -> tuple[int, int]:
    start, end = _bounds(first)
    done = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder_id, CareJob.kind.in_(_VISIT_KINDS), CareJob.status == "completed",
                CareJob.completed_at >= start, CareJob.completed_at < end)
        .count()
    )
    missed = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder_id, CareJob.kind.in_(_VISIT_KINDS), CareJob.status == "missed",
                CareJob.scheduled_at >= start, CareJob.scheduled_at < end)
        .count()
    )
    return done, missed


def _incidents(db: Session, elder_id: int, first: date) -> dict:
    from app.models.incident_report import IncidentReport

    start, end = _bounds(first)
    rows = (
        db.query(IncidentReport)
        .filter(IncidentReport.elder_id == elder_id, IncidentReport.occurred_at >= start,
                IncidentReport.occurred_at < end)
        .all()
    )
    return {"total": len(rows), "reviewed": sum(1 for r in rows if r.status != "open"),
            "serious": sum(1 for r in rows if r.serious)}


def _goals(db: Session, elder_id: int) -> list[dict]:
    from app.models.client_care import CareGoal

    rows = (
        db.query(CareGoal)
        .filter(CareGoal.elder_id == elder_id, CareGoal.status.in_(("active", "achieved")))
        .order_by(CareGoal.sort_order, CareGoal.id)
        .limit(8)
        .all()
    )
    return [{"goal": g.goal, "status": g.status, "progress": g.progress or ""} for g in rows]


def _safety(db: Session, elder_id: int, first: date) -> dict:
    """Independence Score: latest completed assessment vs the one before."""
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    rows = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder_id, HomeSafetyAssessmentRecord.status == "completed",
                HomeSafetyAssessmentRecord.server_score.isnot(None))
        .order_by(HomeSafetyAssessmentRecord.completed_at.desc().nullslast(), HomeSafetyAssessmentRecord.id.desc())
        .limit(2)
        .all()
    )
    if not rows:
        return {"score": None, "previous": None, "change": None, "assessed_this_month": False}
    start, end = _bounds(first)
    latest = rows[0]
    at = kl._aware(latest.completed_at)
    prev = rows[1].server_score if len(rows) > 1 else None
    return {
        "score": latest.server_score,
        "previous": prev,
        "change": (latest.server_score - prev) if prev is not None else None,
        "assessed_this_month": bool(at and start <= at < end),
    }


def _next_month_visits(db: Session, elder_id: int, first: date) -> int:
    start, end = _bounds(next_month(first))
    return (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder_id, CareJob.kind == "visit",
                CareJob.status.in_(("scheduled", "on_the_way")),
                CareJob.scheduled_at >= start, CareJob.scheduled_at < end)
        .count()
    )


def month_stats(db: Session, elder: Elder, first: date) -> dict:
    baseline = kl.baseline_for(db, elder)
    visits = kl.recent_visits(db, elder.id, limit=80, baseline=baseline["values"])
    this, prev = _in_month(visits, first), _in_month(visits, prev_month(first))
    trend = {}
    for key, good in (("mood", "good"), ("sleep", "well"), ("appetite", "usual")):
        a, b = kw._share(this, key, good), kw._share(prev, key, good)
        trend[key] = {**a, "prev_good": b["good"], "prev_answered": b["answered"], "trend": kw._trend(a, b)}
    done, missed = _jobs_in(db, elder.id, first)
    return {
        "name": (elder.first_name or "").strip(),
        "month_start": first.isoformat(),
        "month_label": month_label(first),
        "visits_done": done,
        "visits_missed": missed,
        "kushlife_visits": len(this),
        "kushlife_prev": len(prev),
        "all_four_ok": sum(1 for v in this if all(s == "ok" for s in v["checks"].values())),
        "checks_ok": {k: sum(1 for v in this if v["checks"].get(k) == "ok") for k in kl.CHECKS},
        "trend": trend,
        "vitals": kw._vitals(this),
        "vitals_prev": kw._vitals(prev),
        "baseline": {k: baseline["values"].get(k) for k in kl.NUMERIC},
        "flags": sum(1 for v in this if v["level"] in ("amber", "red")),
        "photos": sum(v.get("photo_count") or 0 for v in this),
        "incidents": _incidents(db, elder.id, first),
        "goals": _goals(db, elder.id),
        "safety": _safety(db, elder.id, first),
        "next_month_visits": _next_month_visits(db, elder.id, first),
    }


# --- plain-English template --------------------------------------------------------


def _vital_line(name: str, s: dict) -> list[str]:
    v, p, b = s["vitals"], s["vitals_prev"], s["baseline"]
    out = []
    if v.get("bp_sys") and v.get("bp_dia"):
        line = f"Blood pressure was around {v['bp_sys']}/{v['bp_dia']}"
        if b.get("bp_sys") and b.get("bp_dia"):
            line += f" (normal for {name}: {b['bp_sys']}/{b['bp_dia']})"
        if p.get("bp_sys") and p.get("bp_dia"):
            line += f"; last month {p['bp_sys']}/{p['bp_dia']}"
        out.append(line + ".")
    if v.get("spo2"):
        line = f"Oxygen was around {v['spo2']}%"
        if b.get("spo2"):
            line += f" (normal for {name}: {b['spo2']}%)"
        out.append(line + ".")
    if v.get("pulse"):
        line = f"Pulse was around {v['pulse']}"
        if b.get("pulse"):
            line += f" (normal for {name}: {b['pulse']})"
        out.append(line + ".")
    return out


def draft_text(s: dict) -> str:
    name = s["name"] or "Your parent"
    out = [f"KushLife letter for {s['month_label']}."]
    done, missed = s["visits_done"], s["visits_missed"]
    line = f"{name} had {done} visit{'s' if done != 1 else ''} this month"
    line += f" and {missed} visit{'s were' if missed != 1 else ' was'} missed." if missed else ", with none missed."
    out.append(line)
    if s["kushlife_visits"]:
        out.append(
            f"All four KushLife checks (Safe, Steady, Settled, Connected) were as usual on "
            f"{s['all_four_ok']} of {s['kushlife_visits']} checked visits."
        )
    t = s["trend"]
    for part in (
        kw._part(t["mood"], "Mood was as usual", "low"),
        kw._part(t["sleep"], "Slept well", "slept poorly"),
        kw._part(t["appetite"], "Ate as usual", "ate differently"),
    ):
        if part:
            out.append(part + ".")
    out.extend(_vital_line(name, s))
    if s["flags"]:
        out.append(f"{s['flags']} change{'s were' if s['flags'] != 1 else ' was'} noticed on visits and followed up.")
    inc = s["incidents"]
    if inc["total"]:
        out.append(
            f"{inc['total']} incident{'s were' if inc['total'] != 1 else ' was'} reported; "
            f"{inc['reviewed']} reviewed by the care manager."
        )
    for g in s["goals"][:4]:
        word = "Achieved" if g["status"] == "achieved" else "Goal"
        out.append(f"{word}: {g['goal']}" + (f" — {g['progress']}" if g["progress"] else "") + ".")
    sf = s["safety"]
    if sf["score"] is not None and sf["assessed_this_month"]:
        if sf["change"] is not None and sf["change"] != 0:
            out.append(f"The home's {safety_score_name()} is now {sf['score']} ({'+' if sf['change'] > 0 else ''}{sf['change']}).")
        else:
            out.append(f"The home's {safety_score_name()} is {sf['score']}.")
    return " ".join(out)


def draft_next_plan(s: dict) -> str:
    n = s["next_month_visits"]
    parts = [f"{n} visit{'s are' if n != 1 else ' is'} booked for next month." if n else "Next month's visits will be booked by your care manager."]
    active = [g["goal"] for g in s["goals"] if g["status"] == "active"][:3]
    if active:
        parts.append("We keep working on: " + "; ".join(active) + ".")
    return " ".join(parts)


# --- the job ---------------------------------------------------------------------


def draft_monthly_letters(db: Session, *, now: datetime | None = None) -> list[int]:
    """Draft last month's letter for every active client with a completed visit. Safe every tick."""
    local = _now(now)
    if local.day == 1 and local.hour < DRAFT_HOUR_IST:
        return []
    first = prev_month(local.date())
    start, end = _bounds(first)
    have = {r[0] for r in db.query(KushLifeMonthly.elder_id).filter(KushLifeMonthly.month_start == first).all()}
    visited = {
        r[0]
        for r in db.query(CareJob.elder_id)
        .filter(CareJob.status == "completed", CareJob.kind.in_(_VISIT_KINDS),
                CareJob.completed_at >= start, CareJob.completed_at < end)
        .distinct()
        .all()
    }
    made: list[int] = []
    for elder_id in sorted(visited - have):
        elder = db.get(Elder, elder_id)
        if not elder or (elder.status or "").lower() in _INACTIVE:
            continue
        stats = month_stats(db, elder, first)
        text, plan = draft_text(stats), draft_next_plan(stats)
        row = KushLifeMonthly(
            tenant_id=elder.tenant_id, elder_id=elder.id, month_start=first, status="draft",
            draft_text=text, text=text, next_plan=plan, manager_note="", stats=stats,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:  # another tick drafted it first
            db.rollback()
            continue
        made.append(row.id)
    return made


# --- reading, editing, approving ------------------------------------------------------


def as_dict(row: KushLifeMonthly, *, now: datetime | None = None, staff: bool = True) -> dict:
    now_utc = now or datetime.now(timezone.utc)
    out = {
        "id": row.id,
        "elder_id": row.elder_id,
        "month_start": row.month_start.isoformat(),
        "month_label": month_label(row.month_start),
        "status": row.status,
        "text": row.text,
        "manager_note": row.manager_note or "",
        "next_plan": row.next_plan or "",
        "stats": row.stats or {},
        "approved_at": kl._aware(row.approved_at).isoformat() if row.approved_at else None,
    }
    if staff:
        out["draft_text"] = row.draft_text
        out["overdue"] = row.status == "draft" and now_utc >= overdue_at(row.month_start)
    return out


def staff_list(db: Session, elder: Elder, limit: int = 6) -> list[dict]:
    rows = (
        db.query(KushLifeMonthly)
        .filter(KushLifeMonthly.elder_id == elder.id, KushLifeMonthly.status != "skipped")
        .order_by(KushLifeMonthly.month_start.desc())
        .limit(limit)
        .all()
    )
    return [as_dict(r) for r in rows]


def _get(db: Session, elder: Elder, letter_id: int) -> KushLifeMonthly:
    row = db.get(KushLifeMonthly, letter_id)
    if not row or row.elder_id != elder.id or row.status == "skipped":
        raise_not_found("Monthly letter not found")
    return row


def _clean(v: str | None, limit: int) -> str:
    return (v or "").strip()[:limit]


def edit_letter(db: Session, elder: Elder, letter_id: int, data: dict, user) -> dict:
    row = _get(db, elder, letter_id)
    if row.status == "approved":
        raise_bad_request("This letter is already approved and sent")
    if data.get("text") is not None:
        text = _clean(data["text"], 6000)
        if not text:
            raise_bad_request("The letter can't be empty")
        row.text = text
    if data.get("manager_note") is not None:
        row.manager_note = _clean(data["manager_note"], 2000)
    if data.get("next_plan") is not None:
        row.next_plan = _clean(data["next_plan"], 2000)
    row.edited_by_user_id = user.id
    db.commit()
    return as_dict(row)


def approve_letter(db: Session, elder: Elder, letter_id: int, user, data: dict | None = None) -> dict:
    """Approve and send: portal note + email to the family (respecting their email choices)."""
    row = _get(db, elder, letter_id)
    if row.status == "approved":
        raise WorkforceHTTPError("This letter is already approved and sent", status_code=409)
    data = data or {}
    final = _clean(data.get("text"), 6000) or (row.text or "").strip()
    if not final:
        raise_bad_request("Write the letter before approving")
    now = datetime.now(timezone.utc)
    values = {"status": "approved", "text": final, "approved_by_user_id": user.id, "approved_at": now}
    if data.get("manager_note") is not None:
        values["manager_note"] = _clean(data["manager_note"], 2000)
    if data.get("next_plan") is not None:
        values["next_plan"] = _clean(data["next_plan"], 2000)
    res = db.execute(
        update(KushLifeMonthly)
        .where(KushLifeMonthly.id == row.id, KushLifeMonthly.status == "draft")
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        db.rollback()
        raise WorkforceHTTPError("This letter is already approved and sent", status_code=409)
    db.commit()
    db.refresh(row)
    try:
        from app.livewell.family_notify import notify_family

        name = (elder.first_name or "").strip() or "your parent"
        notify_family(
            db, elder, f"KushLife letter for {name}: {month_label(row.month_start)}",
            "Your monthly KushLife letter is ready. Open it in the family portal under Documents; you can save it as a PDF.",
            event="monthly_letter", path=f"/documents/letters/{row.id}",
        )
        row.sent_at = now
        db.commit()
    except Exception:  # a failed send must not undo the approval
        db.rollback()
        logger.exception("kushlife_monthly_send_failed letter=%s", row.id)
    return as_dict(row)


def pending_for(db: Session, user, *, now: datetime | None = None) -> dict:
    """Letters waiting for approval in the user's team (Dashboard reminder)."""
    from app.core.team_scope import scope_elder_query

    q = db.query(KushLifeMonthly, Elder).join(Elder, Elder.id == KushLifeMonthly.elder_id).filter(
        KushLifeMonthly.status == "draft",
        KushLifeMonthly.tenant_id == user.tenant_id,
        KushLifeMonthly.month_start >= prev_month(last_month_start(now)),
    )
    q = scope_elder_query(db, user, q, column=KushLifeMonthly.elder_id)
    items = []
    for row, elder in q.order_by(KushLifeMonthly.month_start.desc(), Elder.first_name).all():
        d = as_dict(row, now=now)
        items.append({
            "id": row.id, "elder_id": elder.id,
            "elder_name": f"{elder.first_name or ''} {elder.last_name or ''}".strip(),
            "month_start": d["month_start"], "month_label": d["month_label"], "overdue": d["overdue"],
        })
    return {"items": items, "overdue": sum(1 for i in items if i["overdue"])}


def family_list(db: Session, elder: Elder) -> list[dict]:
    rows = (
        db.query(KushLifeMonthly)
        .filter(KushLifeMonthly.elder_id == elder.id, KushLifeMonthly.status == "approved")
        .order_by(KushLifeMonthly.month_start.desc())
        .limit(24)
        .all()
    )
    return [{"id": r.id, "month_start": r.month_start.isoformat(), "month_label": month_label(r.month_start),
             "approved_at": kl._aware(r.approved_at).isoformat() if r.approved_at else None} for r in rows]


def family_get(db: Session, elder: Elder, letter_id: int) -> KushLifeMonthly:
    """Approved letters only — a draft is a 404 for the family."""
    row = db.get(KushLifeMonthly, letter_id)
    if not row or row.elder_id != elder.id or row.status != "approved":
        raise_not_found("Letter not found")
    return row


# --- PDF -------------------------------------------------------------------------


def letter_pdf(db: Session, elder: Elder, row: KushLifeMonthly) -> bytes:
    """A one-to-two page PDF (reportlab, already used for invoices and payslips)."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from app.livewell.brand import brand_name

    s = row.stats or {}
    name = f"{elder.first_name or ''} {elder.last_name or ''}".strip() or "Client"
    styles = getSampleStyleSheet()
    body, h1, h2 = styles["BodyText"], styles["Title"], styles["Heading3"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"KushLife letter — {name} — {month_label(row.month_start)}")
    p = lambda t, st=body: Paragraph(escape(t or "").replace("\n", "<br/>"), st)  # noqa: E731
    story = [
        p(f"{brand_name()} · KushLife letter", h1),
        p(f"{name} — {month_label(row.month_start)}", styles["Heading2"]),
        Spacer(1, 4 * mm),
    ]
    grid = [["Visits done", "Visits missed", "KushLife checks", "All four as usual", "Incidents"],
            [str(s.get("visits_done", 0)), str(s.get("visits_missed", 0)), str(s.get("kushlife_visits", 0)),
             str(s.get("all_four_ok", 0)), str((s.get("incidents") or {}).get("total", 0))]]
    t = Table(grid, hAlign="LEFT")
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f1")),
                           ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [t, Spacer(1, 4 * mm)]
    v, b = s.get("vitals") or {}, s.get("baseline") or {}
    rows = [["Reading", "This month (typical)", "Normal for them"]]
    for key, label in (("bp", "Blood pressure"), ("spo2", "Oxygen %"), ("pulse", "Pulse")):
        if key == "bp":
            cur = f"{v['bp_sys']}/{v['bp_dia']}" if v.get("bp_sys") and v.get("bp_dia") else "—"
            nor = f"{b['bp_sys']}/{b['bp_dia']}" if b.get("bp_sys") and b.get("bp_dia") else "—"
        else:
            cur, nor = (str(v[key]) if v.get(key) else "—"), (str(b[key]) if b.get(key) else "—")
        rows.append([label, cur, nor])
    vt = Table(rows, hAlign="LEFT")
    vt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f1")),
                            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [p("The month", h2), p(row.text), Spacer(1, 3 * mm), p("Readings", h2), vt]
    goals = s.get("goals") or []
    if goals:
        story.append(p("Care plan goals", h2))
        for g in goals:
            story.append(p(f"• {g['goal']} — {'achieved' if g['status'] == 'achieved' else 'in progress'}"
                           + (f": {g['progress']}" if g.get("progress") else "")))
    if row.manager_note:
        story += [p("From your care manager", h2), p(row.manager_note)]
    if row.next_plan:
        story += [p("Next month", h2), p(row.next_plan)]
    story += [Spacer(1, 6 * mm),
              p("Care observations by your care team, not a medical diagnosis. "
                "Please talk to your doctor about any health concern.", styles["Italic"])]
    doc.build(story)
    return buf.getvalue()


# --- vitals trend (last ~3 months) ---------------------------------------------------


def vitals_series(db: Session, elder: Elder, *, days: int = 92, now: datetime | None = None) -> dict:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    since = now_utc - timedelta(days=days)
    baseline = kl.baseline_for(db, elder)
    points = []
    for _j, rec in reversed(kl._records(db, elder.id, 120)):
        when = kl._aware(_j.completed_at or _j.scheduled_at)
        if not when or when < since:
            continue
        vit = rec.get("vitals") or {}
        pt = {k: vit.get(k) for k in kl.NUMERIC if vit.get(k) is not None}
        if pt:
            points.append({"date": when.isoformat(), **pt})
    return {
        "days": days,
        "points": points,
        "baseline": {k: baseline["values"].get(k) for k in kl.NUMERIC},
        "label": baseline["label"],
    }
