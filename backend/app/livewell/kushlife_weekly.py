"""KushLife K2: the Monday card ("This week for Amma") and the weekly summary.

* ``week_card``: last full week (Mon–Sun, IST) from the visits' KushLife records, compared
  with the week before — visits, sleep / appetite / mood, BP and oxygen, flags, next visits.
* ``draft_weekly_summaries``: run by the jobs timer (every 2 min). From Monday 07:00 IST it
  drafts one plain-English summary per client who had a visit last week. One row per client
  per week (unique constraint), so repeated ticks never draft twice.
* The client's care manager edits and approves it; only approved text reaches the family
  (portal + email under the family event ``weekly_summary``). A draft still unapproved on
  Tuesday 18:00 IST shows as overdue on the ops Dashboard.

Templates only — no AI calls. Care observation, not diagnosis.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.responses import WorkforceHTTPError, raise_bad_request, raise_not_found
from app.livewell import kushlife as kl
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.kushlife_weekly import KushLifeWeekly

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
DRAFT_HOUR_IST = 7  # Monday 07:00 IST
REMIND_AFTER = (1, 18)  # Tuesday 18:00 IST (weekday, hour)
_INACTIVE = ("inactive", "archived", "deleted", "discharged")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(IST)


def this_monday(now: datetime | None = None) -> date:
    local = _now(now)
    return local.date() - timedelta(days=local.weekday())


def last_week_start(now: datetime | None = None) -> date:
    """Monday of the last full week — the week the Monday card and the summary describe."""
    return this_monday(now) - timedelta(days=7)


def _bounds(monday: date) -> tuple[datetime, datetime]:
    start = datetime.combine(monday, time(0, 0), tzinfo=IST)
    return start, start + timedelta(days=7)


def overdue_at(week_start: date) -> datetime:
    """Tuesday 18:00 IST of the week after the one summarised."""
    day, hour = REMIND_AFTER
    return datetime.combine(week_start + timedelta(days=7 + day), time(hour, 0), tzinfo=IST)


# --- the week in numbers -----------------------------------------------------------


def _in_week(visits: list[dict], monday: date) -> list[dict]:
    start, end = _bounds(monday)
    return [v for v in visits if v["date"] and start <= datetime.fromisoformat(v["date"]) < end]


def _share(visits: list[dict], key: str, good: str) -> dict:
    answered = [v[key] for v in visits if v.get(key) in kl.CATEGORICAL[key]]
    return {"good": sum(1 for a in answered if a == good), "answered": len(answered)}


def _trend(this: dict, prev: dict) -> str | None:
    if not this["answered"] or not prev["answered"]:
        return None
    a, b = this["good"] / this["answered"], prev["good"] / prev["answered"]
    return "better" if a - b > 0.2 else "worse" if b - a > 0.2 else "same"


def _vitals(visits: list[dict]) -> dict:
    out = {}
    for k in kl.NUMERIC:
        vals = sorted(v["vitals"][k] for v in visits if v["vitals"].get(k) is not None)
        out[k] = int(round(kl._quantile([float(x) for x in vals], 0.5))) if vals else None
    return out


def _flags(elder: Elder, visits: list[dict], monday: date, staff: bool) -> dict:
    acks = kl._ack(elder)
    start, end = _bounds(monday)
    raised = 0
    for v in visits:
        if v["level"] == "red":
            raised += 1
        elif v["level"] == "amber":
            # The family hears of an amber change only once the care manager has seen it.
            seen = any(k == f"visit:{v['job_id']}" or k.endswith(f":{v['job_id']}") for k in acks)
            raised += 1 if staff or seen else 0
    closed = 0
    for a in acks.values():
        try:
            at = datetime.fromisoformat(a.get("at") or "")
        except ValueError:
            continue
        if start <= kl._aware(at) < end:
            closed += 1
    return {"raised": raised, "closed": closed}


def _next_visits(db: Session, elder_id: int, now: datetime) -> list[dict]:
    rows = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id == elder_id,
            CareJob.kind == "visit",
            CareJob.status.in_(("scheduled", "on_the_way")),
            CareJob.scheduled_at >= now - timedelta(hours=1),
        )
        .order_by(CareJob.scheduled_at)
        .limit(3)
        .all()
    )
    return [{"date": kl._aware(j.scheduled_at).isoformat(), "title": j.title} for j in rows]


def week_stats(db: Session, elder: Elder, monday: date, *, staff: bool, now: datetime | None = None) -> dict:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    baseline = kl.baseline_for(db, elder)
    visits = kl.recent_visits(db, elder.id, limit=40, baseline=baseline["values"])
    this, prev = _in_week(visits, monday), _in_week(visits, monday - timedelta(days=7))
    trend = {}
    for key, good in (("mood", "good"), ("sleep", "well"), ("appetite", "usual")):
        a, b = _share(this, key, good), _share(prev, key, good)
        trend[key] = {**a, "prev_good": b["good"], "prev_answered": b["answered"], "trend": _trend(a, b)}
    return {
        "name": (elder.first_name or "").strip(),
        "week_start": monday.isoformat(),
        "week_end": (monday + timedelta(days=6)).isoformat(),
        "visits_done": len(this),
        "visits_prev": len(prev),
        "trend": trend,
        "vitals": _vitals(this),
        "vitals_prev": _vitals(prev),
        "baseline": {k: baseline["values"].get(k) for k in kl.NUMERIC},
        "flags": _flags(elder, this, monday, staff),
        "next_visits": _next_visits(db, elder.id, now_utc),
    }


# --- plain-English template --------------------------------------------------------


def _d(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%a %d %b").replace(" 0", " ")


def _part(t: dict, good_words: str, other_words: str) -> str | None:
    if not t["answered"]:
        return None
    if t["good"] == t["answered"]:
        return f"{good_words} on {'every visit' if t['answered'] > 1 else 'the visit'}"
    return f"{good_words} on {t['good']} of {t['answered']} visits ({other_words} on the others)"


def draft_text(s: dict) -> str:
    name = s["name"] or "Your parent"
    out = [f"Week of {_d(s['week_start'])} – {_d(s['week_end'])}."]
    n = s["visits_done"]
    out.append(
        f"{name} had {n} KushLife visit{'s' if n != 1 else ''}"
        + (f" ({s['visits_prev']} the week before)." if s["visits_prev"] != n else ", the same as the week before.")
    )
    t = s["trend"]
    for part in (
        _part(t["mood"], "Mood was as usual", "low"),
        _part(t["sleep"], "Slept well", "slept poorly"),
        _part(t["appetite"], "Ate as usual", "ate differently"),
    ):
        if part:
            out.append(part + ".")
    v, b = s["vitals"], s["baseline"]
    if v.get("bp_sys") and v.get("bp_dia"):
        normal = f" (normal for {name}: {b['bp_sys']}/{b['bp_dia']})" if b.get("bp_sys") and b.get("bp_dia") else ""
        out.append(f"Blood pressure was around {v['bp_sys']}/{v['bp_dia']}{normal}.")
    if v.get("spo2"):
        normal = f" (normal for {name}: {b['spo2']}%)" if b.get("spo2") else ""
        out.append(f"Oxygen was around {v['spo2']}%{normal}.")
    f = s["flags"]
    if f["raised"]:
        out.append(
            f"{f['raised']} change{'s were' if f['raised'] != 1 else ' was'} noticed and followed up by the care manager."
        )
    else:
        out.append("Nothing needed following up.")
    if s["next_visits"]:
        nxt = kl._aware(datetime.fromisoformat(s["next_visits"][0]["date"])).astimezone(IST)
        # Stored text read by everyone (portal + email), so the zone is spelled out.
        out.append(f"Next visit: {nxt.strftime('%a %d %b, %I:%M %p').replace(' 0', ' ')} India time.")
    return " ".join(out)


# --- the job ---------------------------------------------------------------------


def draft_weekly_summaries(db: Session, *, now: datetime | None = None) -> list[int]:
    """Draft last week's summary for every active client who had a visit. Safe to run every tick."""
    local = _now(now)
    monday = this_monday(now)
    if local < datetime.combine(monday, time(DRAFT_HOUR_IST, 0), tzinfo=IST):
        return []
    week = monday - timedelta(days=7)
    start, end = _bounds(week)
    have = {r[0] for r in db.query(KushLifeWeekly.elder_id).filter(KushLifeWeekly.week_start == week).all()}
    visited = {
        r[0]
        for r in db.query(CareJob.elder_id)
        .filter(
            CareJob.status == "completed",
            CareJob.kind.in_(("visit", "install")),
            CareJob.completed_at >= start.astimezone(timezone.utc),
            CareJob.completed_at < end.astimezone(timezone.utc),
        )
        .distinct()
        .all()
    }
    made: list[int] = []
    for elder_id in sorted(visited - have):
        elder = db.get(Elder, elder_id)
        if not elder or (elder.status or "").lower() in _INACTIVE:
            continue
        # The family's counts (an amber change counts once the care manager has seen it),
        # so the approved text matches the family's Monday card.
        stats = week_stats(db, elder, week, staff=False, now=now)
        if not stats["visits_done"]:
            # A completed job without a KushLife record: remember it, so the next tick
            # doesn't recompute this client. "skipped" rows are never shown to anyone.
            row = KushLifeWeekly(
                tenant_id=elder.tenant_id, elder_id=elder.id, week_start=week, status="skipped",
                draft_text="", text="", stats=None,
            )
        else:
            text = draft_text(stats)
            row = KushLifeWeekly(
                tenant_id=elder.tenant_id, elder_id=elder.id, week_start=week, status="draft",
                draft_text=text, text=text, stats=stats,
            )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:  # another tick drafted it first
            db.rollback()
            continue
        if row.status == "draft":
            made.append(row.id)
    return made


# --- reading and approving -------------------------------------------------------


def as_dict(row: KushLifeWeekly, *, now: datetime | None = None) -> dict:
    now_utc = now or datetime.now(timezone.utc)
    return {
        "id": row.id,
        "elder_id": row.elder_id,
        "week_start": row.week_start.isoformat(),
        "status": row.status,
        "text": row.text,
        "draft_text": row.draft_text,
        "stats": row.stats or {},
        "approved_at": kl._aware(row.approved_at).isoformat() if row.approved_at else None,
        "overdue": row.status == "draft" and now_utc >= overdue_at(row.week_start),
    }


def staff_list(db: Session, elder: Elder, limit: int = 8) -> list[dict]:
    rows = (
        db.query(KushLifeWeekly)
        .filter(KushLifeWeekly.elder_id == elder.id, KushLifeWeekly.status != "skipped")
        .order_by(KushLifeWeekly.week_start.desc())
        .limit(limit)
        .all()
    )
    return [as_dict(r) for r in rows]


def _get(db: Session, elder: Elder, summary_id: int) -> KushLifeWeekly:
    row = db.get(KushLifeWeekly, summary_id)
    if not row or row.elder_id != elder.id or row.status == "skipped":
        raise_not_found("Weekly summary not found")
    return row


def edit_summary(db: Session, elder: Elder, summary_id: int, text: str, user) -> dict:
    row = _get(db, elder, summary_id)
    if row.status == "approved":
        raise_bad_request("This summary is already approved and sent")
    text = (text or "").strip()
    if not text:
        raise_bad_request("The summary can't be empty")
    row.text = text[:4000]
    row.edited_by_user_id = user.id
    db.commit()
    return as_dict(row)


def approve_summary(db: Session, elder: Elder, summary_id: int, user, text: str | None = None) -> dict:
    """Approve and send: portal note + email to the family (respecting their email choices)."""
    row = _get(db, elder, summary_id)
    if row.status == "approved":
        raise WorkforceHTTPError("This summary is already approved and sent", status_code=409)
    edited = text is not None and bool(text.strip())
    final = (text.strip() if edited else (row.text or "").strip())[:4000]
    if not final:
        raise_bad_request("Write the summary before approving")
    now = datetime.now(timezone.utc)
    values = {"status": "approved", "text": final, "approved_by_user_id": user.id, "approved_at": now}
    if edited:
        values["edited_by_user_id"] = user.id
    # Conditional UPDATE: of two approvals racing, only one moves draft → approved (and sends).
    res = db.execute(
        update(KushLifeWeekly)
        .where(KushLifeWeekly.id == row.id, KushLifeWeekly.status == "draft")
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount != 1:
        db.rollback()
        raise WorkforceHTTPError("This summary is already approved and sent", status_code=409)
    db.commit()
    db.refresh(row)
    try:
        from app.livewell.family_notify import notify_family

        name = (elder.first_name or "").strip() or "your parent"
        notify_family(db, elder, f"KushLife this week for {name}", row.text, event="weekly_summary", path="/")
        row.sent_at = now
        db.commit()
    except Exception:  # a failed send must not undo the approval
        db.rollback()
        logger.exception("kushlife_weekly_send_failed summary=%s", row.id)
    return as_dict(row)


def pending_for(db: Session, user, *, now: datetime | None = None) -> dict:
    """Drafts waiting for approval in the user's team (Dashboard reminder)."""
    from app.core.team_scope import scope_elder_query

    q = db.query(KushLifeWeekly, Elder).join(Elder, Elder.id == KushLifeWeekly.elder_id).filter(
        KushLifeWeekly.status == "draft",
        KushLifeWeekly.tenant_id == user.tenant_id,
        KushLifeWeekly.week_start >= last_week_start(now) - timedelta(days=21),
    )
    q = scope_elder_query(db, user, q, column=KushLifeWeekly.elder_id)
    items = []
    for row, elder in q.order_by(KushLifeWeekly.week_start.desc(), Elder.first_name).all():
        d = as_dict(row, now=now)
        items.append({
            "id": row.id, "elder_id": elder.id,
            "elder_name": f"{elder.first_name or ''} {elder.last_name or ''}".strip(),
            "week_start": d["week_start"], "overdue": d["overdue"],
        })
    return {"items": items, "overdue": sum(1 for i in items if i["overdue"])}


def family_week(db: Session, elder: Elder, *, now: datetime | None = None) -> dict:
    """The Monday card for the family, plus the approved summary for that week (never a draft)."""
    week = last_week_start(now)
    card = week_stats(db, elder, week, staff=False, now=now)
    row = (
        db.query(KushLifeWeekly)
        .filter(KushLifeWeekly.elder_id == elder.id, KushLifeWeekly.week_start == week,
                KushLifeWeekly.status == "approved")
        .first()
    )
    return {
        "card": card,
        "summary": {"text": row.text, "approved_at": kl._aware(row.approved_at).isoformat()} if row else None,
        "is_monday": _now(now).weekday() == 0,
    }
