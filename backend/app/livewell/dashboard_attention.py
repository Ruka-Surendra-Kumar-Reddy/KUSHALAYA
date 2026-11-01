"""Ops dashboard "needs attention" feed, scoped to the user's team.

Open family requests, unread family messages, open SOS / wearable alerts and
today's visits, for the clients the user may see (admins: all; managers: team).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import SYSTEM_ADMIN, TENANT_ADMIN, resolve_tenant_id
from app.core.team_scope import team_elder_ids
from app.livewell import incident_service
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.family_service_requests import _normalize as normalize_request
from app.livewell.family_service_requests import _requests as raw_requests
from app.livewell.visit_service import _visits_raw, normalize_visit
from app.models.elder import Elder
from app.models.user import User

# Dashboard day boundaries follow India time (all clients are in IST).
IST = timezone(timedelta(hours=5, minutes=30))


def awaiting_reply(row: dict) -> bool:
    """A family thread waits for us when it has unread family messages, or its
    last message is from the family (read but not yet answered)."""
    last = row.get("last_message") or {}
    return row.get("unread_count", 0) > 0 or str(last.get("sender_role") or "family") == "family"


def _name(e: Elder) -> str:
    return f"{e.first_name} {e.last_name}".strip()


def attention(db: Session, user: User, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    tid = resolve_tenant_id(user)
    team = team_elder_ids(db, user)

    q = db.query(Elder).filter(Elder.status != "INACTIVE")
    if tid is not None:
        q = q.filter(Elder.tenant_id == tid)
    elders = [e for e in q.all() if team is None or e.id in team]

    day_start = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    week_start = day_start - timedelta(days=day_start.weekday())
    # Query bounds in UTC: SQLite keeps naive UTC, so an IST-offset bound would compare wrong.
    start_utc = day_start.astimezone(timezone.utc)
    end_utc = day_end.astimezone(timezone.utc)

    requests: list[dict] = []
    today: list[dict] = []
    visits_this_week = 0
    for e in elders:
        for raw in raw_requests(e):
            r = normalize_request(raw)
            if r["status"] == "requested":
                requests.append(
                    {
                        "elder_id": e.id,
                        "elder_name": _name(e),
                        "id": r["id"],
                        "label": r["service_label"],
                        "group": r["group"],
                        "service_type": r["service_type"],
                        "notes": r["notes"],
                        "preferred_at": r["preferred_at"],
                        "created_at": r["created_at"],
                        "requested_by": r.get("created_by") or "",
                        "paid_online_minor": r.get("paid_online_minor") or 0,
                    }
                )
        for raw in _visits_raw(e):
            v = normalize_visit(raw)
            at = datetime.fromisoformat(v["visited_at"])
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if day_start <= at < day_end:
                today.append(
                    {
                        "elder_id": e.id,
                        "elder_name": _name(e),
                        "id": v["id"],
                        "visit_type": v["visit_type"],
                        "at": v["visited_at"],
                        "status": v["status"],
                        "staff_name": v["staff_name"],
                    }
                )
            if week_start <= at < day_end and v["status"] == "completed":
                visits_this_week += 1

    # Scheduled jobs today (visits, assessments, installs) for the same clients.
    from app.models.care_job import CareJob
    from app.models.caregiver import Caregiver
    from app.livewell.live_location import view as live_view

    elder_names ={e.id: _name(e) for e in elders}
    jobs = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id.in_(list(elder_names) or [-1]),
            CareJob.scheduled_at >= start_utc,
            CareJob.scheduled_at < end_utc,
            CareJob.status != "cancelled",
        )
        .all()
    )
    for j in jobs:
        cg = db.get(Caregiver, j.caregiver_id) if j.caregiver_id else None
        at = j.scheduled_at if j.scheduled_at.tzinfo else j.scheduled_at.replace(tzinfo=timezone.utc)
        today.append(
            {
                "elder_id": j.elder_id,
                "elder_name": elder_names.get(j.elder_id, ""),
                "id": f"job-{j.id}",
                "visit_type": j.title,
                "at": at.isoformat(),
                "status": "completed" if j.status == "completed" else j.status,
                "staff_name": f"{cg.first_name} {cg.last_name}".strip() if cg else "",
                "kind": j.kind,
                "job_id": j.id,
                **({"live": live_view(db, j)} if j.status == "on_the_way" else {}),
            }
        )

    # "Completed this week" counts the old visit log above plus completed scheduled jobs (IST week).
    visits_this_week += (
        db.query(CareJob)
        .filter(
            CareJob.elder_id.in_(list(elder_names) or [-1]),
            CareJob.status == "completed",
            CareJob.completed_at >= week_start.astimezone(timezone.utc),
            CareJob.completed_at < end_utc,
        )
        .count()
    )

    # Missed or never-started jobs from the last 7 days (today's are in "today").
    from app.livewell.care_jobs import rebooked_missed_ids

    past = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id.in_(list(elder_names) or [-1]),
            CareJob.scheduled_at >= start_utc - timedelta(days=7),
            CareJob.scheduled_at < start_utc,
            CareJob.status.in_(("missed", "scheduled", "on_the_way")),
        )
        .order_by(CareJob.scheduled_at.desc())
        .all()
    )
    # Missed jobs already rebooked need nothing more (same rule as Schedule).
    rebooked = rebooked_missed_ids(db, [j for j in past if j.status == "missed"])
    missed = []
    for j in (j for j in past if j.id not in rebooked):
        at = j.scheduled_at if j.scheduled_at.tzinfo else j.scheduled_at.replace(tzinfo=timezone.utc)
        missed.append(
            {
                "job_id": j.id,
                "elder_id": j.elder_id,
                "elder_name": elder_names.get(j.elder_id, ""),
                "kind": j.kind,
                "title": j.title,
                "at": at.isoformat(),
                "status": j.status,
            }
        )

    # Orders waiting for an admin to approve a discount above 10%.
    from app.models.commerce import Order

    is_admin = user.role in (SYSTEM_ADMIN, TENANT_ADMIN)
    approvals = [
        {
            "id": o.id,
            "elder_id": o.elder_id,
            "elder_name": elder_names.get(o.elder_id, ""),
            "total_paise": o.total_paise,
            "discount_paise": o.discount_paise,
            "subtotal_paise": o.subtotal_paise,
            "created_at": _aware_iso(o.created_at),
        }
        for o in db.query(Order)
        .filter(Order.elder_id.in_(list(elder_names) or [-1]), Order.status == "pending_approval")
        .all()
    ] if is_admin else []

    from app.livewell.visit_reports import list_hazards

    hazards = [
        {"elder_id": e.id, "elder_name": _name(e), **h}
        for e in elders
        for h in list_hazards(e)
        if h.get("status") == "spotted"
    ]

    requests.sort(key=lambda r: r["created_at"], reverse=True)
    today.sort(key=lambda v: v["at"])

    messages = [
        {
            "elder_id": r["elder_id"],
            "elder_name": r["elder_name"],
            "unread_count": r["unread_count"],
            "awaiting_reply": True,
            "last_message": r.get("last_message"),
            "last_at": r["last_message"]["created_at"] if r.get("last_message") else None,
        }
        for r in FamilyCareHubService.staff_inbox(db, tid, elders=elders)
        if awaiting_reply(r) and (team is None or r["elder_id"] in team)
    ]

    alerts = [
        {
            "id": a["id"],
            "elder_id": a["elder_id"],
            "elder_name": a["elder_name"],
            "kind": a["kind"],
            "kind_label": a["kind_label"],
            "severity": a["severity"],
            "status": a["status"],
            "minutes_open": a["minutes_open"],
            "acknowledged_at": a["acknowledged_at"],
        }
        # Team filter in the query, so other teams' alerts can't push ours past the limit.
        for a in incident_service.list_for_tenant(db, tid, limit=50, elder_ids=team)
    ]
    from app.livewell.leave_cover import needs_cover

    # Approved leave over a booked visit: "Visit needs cover" until reassigned.
    cover = needs_cover(db, list(elder_names), now=now)
    reassessments = _reassessments(db, elders)
    flags = _kushlife_flags(db, elders, now)
    enquiries = _new_enquiries(db, tid, now)
    from app.livewell.family_questions import open_for_elders

    # "Call me" / "Ask about…" from families (K2 #91), oldest first.
    questions = open_for_elders(db, elders)
    from app.livewell.incident_reports import attention_rows

    # Serious incident reports (#97) until the manager reviews them.
    incidents = attention_rows(db, elders)
    from app.livewell import client_care

    # Phase 4B: care plan reviews due, high/overdue risks, handovers waiting for me.
    care_reviews = client_care.review_due_list(db, elders, now=now)
    risks = client_care.risk_flags(db, elders, now=now)
    handovers = client_care.pending_handovers(db, user)
    from app.livewell.visit_feedback import attention_rows as feedback_rows

    # #106: visit ratings ≤ 2 and NPS detractors (0–6) until the manager marks them reviewed.
    feedback = feedback_rows(db, elders)

    return {
        "requests": requests,
        "messages": messages,
        "alerts": alerts,
        "today": today,
        "approvals": approvals,
        "hazards": hazards,
        "reassessments": reassessments,
        "missed": missed,
        "cover": cover,
        "kushlife": flags,
        "enquiries": enquiries,
        "questions": questions,
        "incidents": incidents,
        "care_reviews": care_reviews,
        "risks": risks,
        "handovers": handovers,
        "feedback": feedback,
        "viewer": {"first_name": (user.first_name or "").strip(), "role": user.role, "is_admin": is_admin},
        "counts": {
            "clients": len(elders),
            "open_requests": len(requests),
            "unread_messages": sum(m["unread_count"] for m in messages),
            "open_alerts": len(alerts),
            "visits_today": len(today),
            "visits_this_week": visits_this_week,
            "reassessments": len(reassessments),
            "missed": len(missed),
            "cover": len(cover),
            "awaiting_reply": len(messages),
            "kushlife_flags": len(flags),
            "approvals": len(approvals),
            "hazards": len(hazards),
            "enquiries": len(enquiries),
            "questions": len(questions),
            "incidents": len(incidents),
            "care_reviews": len(care_reviews),
            "risks": len(risks),
            "handovers": len(handovers),
            "feedback": len(feedback),
            # Rows in "Needs attention" (the pill); messages count threads, not messages.
            "attention": len(alerts) + len(requests) + len(messages) + len(approvals) + len(hazards)
            + len(reassessments) + len(missed) + len(cover) + len(flags) + len(enquiries) + len(questions)
            + len(incidents) + len(care_reviews) + len(risks) + len(handovers) + len(feedback),
        },
    }


def _new_enquiry_query(db: Session, tenant_id):
    """The one rule for a "New" enquiry, shared by the Dashboard rows, the menu
    badge and the Enquiries list: open and still at stage NEW (nobody has
    contacted them yet), whatever its age."""
    from app.models.elder_prospect import ElderProspect

    q = db.query(ElderProspect).filter(ElderProspect.stage == "NEW", ElderProspect.status == "OPEN")
    if tenant_id is not None:
        q = q.filter(ElderProspect.tenant_id == tenant_id)
    return q


def new_enquiry_count(db: Session, tenant_id) -> int:
    return _new_enquiry_query(db, tenant_id).count()


def _new_enquiries(db: Session, tenant_id, now: datetime) -> list[dict]:
    """Enquiries nobody has contacted yet (stage NEW), newest first."""
    from app.models.elder_prospect import ElderProspect

    rows = _new_enquiry_query(db, tenant_id).order_by(ElderProspect.created_at.desc()).limit(20).all()
    out = []
    for r in rows:
        created = r.created_at if r.created_at and r.created_at.tzinfo else (r.created_at.replace(tzinfo=timezone.utc) if r.created_at else None)
        out.append({
            "id": r.id,
            "name": f"{r.first_name} {r.last_name}".strip(),
            "phone": r.phone,
            "email": r.email,
            "area": r.address,
            "source": r.source,
            "summary": (r.notes or "")[:160],
            "created_at": created.isoformat() if created else None,
            "reference": f"KA-{r.id:06d}",
        })
    return out


def _reassessments(db: Session, elders: list[Elder]) -> list[dict]:
    from app.livewell.reassessment import due_list

    return due_list(db, elders)


KUSHLIFE_CAP = 50


def _aware_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _kushlife_flags(db: Session, elders: list[Elder], now: datetime) -> list[dict]:
    """Unacknowledged amber/red KushLife flags; only clients visited in the last 30 days (cheap)."""
    from app.livewell.kushlife import open_flags, recent_visits
    from app.models.care_job import CareJob

    from sqlalchemy import func

    by_id = {e.id: e for e in elders}
    # At most the 50 most recently visited clients, so the 60 s refresh stays cheap.
    last = func.max(CareJob.completed_at)
    recent = [
        r[0]
        for r in db.query(CareJob.elder_id, last)
        .filter(
            CareJob.elder_id.in_(list(by_id) or [-1]),
            CareJob.status == "completed",
            CareJob.completed_at >= (now - timedelta(days=30)).astimezone(timezone.utc),
        )
        .group_by(CareJob.elder_id)
        .order_by(last.desc())
        .limit(KUSHLIFE_CAP)
        .all()
    ]
    out = []
    for eid in recent:
        e = by_id[eid]
        for f in open_flags(e, recent_visits(db, eid, limit=3)):
            if f.get("acknowledged_at") or f["level"] not in ("red", "amber"):
                continue
            out.append({"elder_id": eid, "elder_name": _name(e), "key": f["key"], "level": f["level"],
                        "reason": f["reason"], "date": f["date"]})
    out.sort(key=lambda f: (f["level"] != "red", f["elder_name"]))
    return out


def nav_counts(db: Session, user: User, *, now: datetime | None = None) -> dict:
    """Small integers for the ops sidebar badges, team scoped like ``attention``.

    Polled every minute, so it skips the heavy rows (KushLife flags, hazards,
    feedback) and only counts.
    """
    from app.livewell.care_jobs import rebooked_missed_ids
    from app.livewell.incident_service import OPEN_STATUSES, Incident
    from app.models.care_job import CareJob

    now = now or datetime.now(timezone.utc)
    tid = resolve_tenant_id(user)
    team = team_elder_ids(db, user)

    q = db.query(Elder).filter(Elder.status != "INACTIVE")
    if tid is not None:
        q = q.filter(Elder.tenant_id == tid)
    elders = [e for e in q.all() if team is None or e.id in team]
    ids = [e.id for e in elders] or [-1]

    iq = db.query(Incident).filter(Incident.status.in_(list(OPEN_STATUSES)))
    if tid is not None:
        iq = iq.filter(Incident.tenant_id == tid)
    if team is not None:
        iq = iq.filter(Incident.elder_id.in_(team or {-1}))
    alerts = iq.count()

    inbox = [
        r for r in FamilyCareHubService.staff_inbox(db, tid, elders=elders) if team is None or r["elder_id"] in team
    ]
    unread = sum(r["unread_count"] for r in inbox)
    # Threads whose last word is the family's: they wait for us even once read.
    awaiting = sum(1 for r in inbox if awaiting_reply(r))
    # Same rows as the Visits "Requests" tab: family requests plus (re)assessments
    # waiting to be booked, so the menu badge and the tab agree.
    requests = sum(
        1 for e in elders for raw in raw_requests(e) if normalize_request(raw)["status"] == "requested"
    ) + len(_reassessments(db, elders))

    day_start = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = day_start.astimezone(timezone.utc)
    end_utc = (day_start + timedelta(days=1)).astimezone(timezone.utc)
    visits_today = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id.in_(ids),
            CareJob.scheduled_at >= start_utc,
            CareJob.scheduled_at < end_utc,
            CareJob.status != "cancelled",
        )
        .count()
    )
    past = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id.in_(ids),
            CareJob.scheduled_at >= start_utc - timedelta(days=7),
            CareJob.scheduled_at < start_utc,
            CareJob.status.in_(("missed", "scheduled", "on_the_way")),
        )
        .all()
    )
    rebooked = rebooked_missed_ids(db, [j for j in past if j.status == "missed"])
    missed = sum(1 for j in past if j.id not in rebooked)
    from app.livewell.leave_cover import needs_cover

    cover = len(needs_cover(db, [e.id for e in elders], now=now))

    from app.livewell import client_care
    from app.livewell.family_questions import open_for_elders
    from app.livewell.incident_reports import attention_rows

    questions = len(open_for_elders(db, elders))
    incidents = len(attention_rows(db, elders))
    handovers = len(client_care.pending_handovers(db, user))
    risks = len(client_care.risk_flags(db, elders, now=now))
    care_reviews = len(client_care.review_due_list(db, elders, now=now))
    enquiries = new_enquiry_count(db, tid)

    approvals = 0
    if user.role in (SYSTEM_ADMIN, TENANT_ADMIN):
        from app.models.commerce import Order

        approvals = db.query(Order).filter(Order.elder_id.in_(ids), Order.status == "pending_approval").count()

    return {
        "alerts": alerts,
        "messages": unread,
        "awaiting_reply": awaiting,
        "requests": requests,
        "visits_today": visits_today,
        "missed": missed,
        "cover": cover,
        "questions": questions,
        "incidents": incidents,
        "handovers": handovers,
        "risks": risks,
        "care_reviews": care_reviews,
        "enquiries": enquiries,
        "approvals": approvals,
        # Per menu item, so the client just reads them off.
        "nav": {
            "dashboard": alerts,
            "messages": awaiting,
            "schedule": missed + requests + cover,
            "clients": questions + incidents + handovers + risks + care_reviews,
            "enquiries": enquiries,
            "orders": approvals,
        },
    }
