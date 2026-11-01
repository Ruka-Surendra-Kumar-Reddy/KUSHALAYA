"""Incident reports (FIX_TODO #97): falls, near-misses, medication errors, complaints.

Filed after the event by a caregiver (on one of their own visits) or by staff (client
page). Lifecycle: open → reviewed → closed (closing needs an outcome). Serious reports
(a fall with an injury, any medication error, or ticked "serious") email the care
manager at once and sit in Dashboard "Needs attention" until reviewed.

The family sees a plain summary of a report only after review, never staff notes.
Live SOS / wearable alerts are a different thing: see ``incident_service``.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import CAREGIVER, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.team_scope import assert_elder_in_team, team_elder_ids
from app.models.elder import Elder
from app.models.incident_report import IncidentReport
from app.models.user import User

IST = timezone(timedelta(hours=5, minutes=30))
KINDS = {
    "fall": "Fall",
    "near_miss": "Near-miss",
    "medication_error": "Medication error",
    "complaint": "Complaint",
    "injury": "Injury",
    "other": "Other",
}
STATUS_LABEL = {"open": "Waiting for review", "reviewed": "Reviewed", "closed": "Closed"}
FAMILY_VISIBLE = ("reviewed", "closed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _parse(value, *, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _aware(value).astimezone(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise_bad_request(f"{field}: use a date and time")
    # A bare local time from a form is India time. Stored as UTC (SQLite drops the offset).
    return (dt if dt.tzinfo else dt.replace(tzinfo=IST)).astimezone(timezone.utc)


def _txt(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def is_serious(kind: str, injury: str, flagged: bool = False) -> bool:
    return bool(flagged) or kind == "medication_error" or (kind == "fall" and bool((injury or "").strip()))


def _name(first: str | None, last: str | None) -> str:
    return f"{first or ''} {last or ''}".strip()


def _clean_follow_ups(rows) -> list[dict]:
    out = []
    for r in (rows or [])[:30]:
        if not isinstance(r, dict):
            continue
        action = _txt(r.get("action"), 300)
        if not action:
            continue
        due = _txt(r.get("due_date"), 10)
        if due:
            try:
                datetime.strptime(due, "%Y-%m-%d")
            except ValueError:
                raise_bad_request("Follow-up due date: use YYYY-MM-DD")
        out.append({
            "id": _txt(r.get("id"), 20) or uuid.uuid4().hex[:8],
            "action": action,
            "owner": _txt(r.get("owner"), 120),
            "due_date": due or None,
            "done": bool(r.get("done")),
        })
    return out


def serialize(r: IncidentReport, elder: Elder | None = None) -> dict:
    """Staff view (everything)."""
    return {
        "id": r.id,
        "elder_id": r.elder_id,
        "elder_name": _name(elder.first_name, elder.last_name) if elder else "",
        "care_job_id": r.care_job_id,
        "kind": r.kind,
        "kind_label": KINDS.get(r.kind, "Other"),
        "serious": bool(r.serious),
        "occurred_at": _iso(r.occurred_at),
        "location": r.location or "",
        "what_happened": r.what_happened or "",
        "injury": r.injury or "",
        "action_taken": r.action_taken or "",
        "witnesses": r.witnesses or "",
        "family_informed": bool(r.family_informed),
        "family_informed_at": _iso(r.family_informed_at),
        "reported_by_name": r.reported_by_name or "",
        "reporter_role": r.reporter_role or "",
        "status": r.status,
        "status_label": STATUS_LABEL.get(r.status, r.status),
        "follow_ups": list(r.follow_ups or []),
        "staff_notes": r.staff_notes or "",
        "family_summary": r.family_summary or "",
        "outcome": r.outcome or "",
        "reviewed_at": _iso(r.reviewed_at),
        "closed_at": _iso(r.closed_at),
        "created_at": _iso(r.created_at),
    }


def default_family_summary(r: IncidentReport) -> str:
    when = _aware(r.occurred_at).astimezone(IST).strftime("%d %b %Y") if r.occurred_at else ""
    label = KINDS.get(r.kind, "An incident").lower()
    hurt = " There was an injury." if (r.injury or "").strip() else ""
    return (
        f"A {label} was reported{f' on {when}' if when else ''}.{hurt} "
        "Your care manager has reviewed what happened and what we are doing about it."
    ).strip()


def family_view(r: IncidentReport) -> dict:
    """Plain words only: no staff notes, reporter, witnesses or follow-up owners."""
    return {
        "id": r.id,
        "kind_label": KINDS.get(r.kind, "Other"),
        "occurred_at": _iso(r.occurred_at),
        "summary": r.family_summary or default_family_summary(r),
        "status": "Closed" if r.status == "closed" else "Reviewed",
        "serious": bool(r.serious),
    }


# --- access ---------------------------------------------------------------------------


def _elder_for_staff(db: Session, user: User, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(user, elder.tenant_id)
    assert_elder_in_team(db, user, elder.id)
    return elder


def _report_for_staff(db: Session, user: User, report_id: int) -> IncidentReport:
    r = db.get(IncidentReport, report_id)
    if not r:
        raise_not_found("Report not found")
    assert_tenant_access(user, r.tenant_id)
    ids = team_elder_ids(db, user)
    if ids is not None and r.elder_id not in ids:
        raise_not_found("Report not found")
    return r


# --- filing ---------------------------------------------------------------------------


def _apply_fields(r: IncidentReport, data: dict, *, creating: bool) -> None:
    if creating or "kind" in data:
        kind = _txt(data.get("kind"), 30).lower()
        if kind not in KINDS:
            raise_bad_request("Pick what kind of incident it was")
        r.kind = kind
    if creating or "what_happened" in data:
        r.what_happened = _txt(data.get("what_happened"), 4000)
        if not r.what_happened:
            raise_bad_request("Say what happened")
    if creating or "occurred_at" in data:
        when = _parse(data.get("occurred_at"), field="When") or _now()
        if when > _now() + timedelta(minutes=10):
            raise_bad_request("That time is in the future")
        r.occurred_at = when
    for f, n in (("location", 300), ("injury", 2000), ("action_taken", 2000), ("witnesses", 500)):
        if creating or f in data:
            setattr(r, f, _txt(data.get(f), n))
    if creating or "family_informed" in data:
        r.family_informed = bool(data.get("family_informed"))
        r.family_informed_at = _parse(data.get("family_informed_at"), field="Family told at") if r.family_informed else None
    if "follow_ups" in data:
        r.follow_ups = _clean_follow_ups(data.get("follow_ups"))
        flag_modified(r, "follow_ups")


def _create(db: Session, user: User, elder: Elder, data: dict, *, job_id: int | None) -> IncidentReport:
    r = IncidentReport(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        care_job_id=job_id,
        reported_by_user_id=user.id,
        reported_by_name=_name(user.first_name, user.last_name),
        reporter_role=user.role,
        status="open",
        follow_ups=[],
    )
    _apply_fields(r, data, creating=True)
    r.serious = is_serious(r.kind, r.injury, bool(data.get("serious")))
    db.add(r)
    db.commit()
    db.refresh(r)
    if r.serious:
        _notify_serious(db, elder, r)
    return r


def _notify_serious(db: Session, elder: Elder, r: IncidentReport) -> None:
    from app.livewell.email_notifications import email_staff, staff_path

    when = _aware(r.occurred_at).astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    lines = [
        f"{KINDS.get(r.kind, 'Incident')} reported by {r.reported_by_name or 'the care team'} ({when}).",
        f"What happened: {r.what_happened}",
    ]
    if r.injury:
        lines.append(f"Injury: {r.injury}")
    if r.action_taken:
        lines.append(f"Action taken: {r.action_taken}")
    lines.append("Family informed: " + ("yes" if r.family_informed else "not yet"))
    lines.append("Please review it today.")
    email_staff(
        db, elder, "incident_serious", f"Serious incident: {KINDS.get(r.kind, 'Incident').lower()}",
        "\n".join(lines), path=staff_path(elder, "incidents"),
    )


def staff_create(db: Session, user: User, data: dict) -> dict:
    try:
        elder_id = int(data.get("elder_id"))
    except (TypeError, ValueError):
        raise_bad_request("Pick the client")
    elder = _elder_for_staff(db, user, elder_id)
    job_id = data.get("care_job_id")
    if job_id:
        from app.models.care_job import CareJob

        job = db.get(CareJob, int(job_id))
        if not job or job.elder_id != elder.id:
            raise_bad_request("Visit not found for this client")
    return serialize(_create(db, user, elder, data, job_id=int(job_id) if job_id else None), elder)


def caregiver_create(db: Session, user: User, job_id: int, data: dict) -> dict:
    """A caregiver files a report on one of their own visits (404 for anyone else's)."""
    from app.livewell.care_jobs import _caregiver_job

    job = _caregiver_job(db, user, job_id)
    if user.role != CAREGIVER:
        assert_elder_in_team(db, user, job.elder_id)
    if job.status == "cancelled":
        raise_bad_request("That visit was cancelled")
    elder = db.get(Elder, job.elder_id)
    r = _create(db, user, elder, data, job_id=job.id)
    out = serialize(r, elder)
    out.pop("staff_notes", None)
    return out


# --- staff work -----------------------------------------------------------------------


def counts_for(db: Session, elder_id: int) -> dict:
    rows = db.query(IncidentReport.kind, IncidentReport.status, IncidentReport.occurred_at).filter(
        IncidentReport.elder_id == elder_id
    ).all()
    since = _now() - timedelta(days=90)
    return {
        "total": len(rows),
        "falls": sum(1 for k, _, _ in rows if k == "fall"),
        "falls_90d": sum(1 for k, _, at in rows if k == "fall" and at and _aware(at) >= since),
        "open": sum(1 for _, s, _ in rows if s == "open"),
    }


def list_reports(db: Session, user: User, *, elder_id: int | None = None, status: str | None = None) -> dict:
    q = db.query(IncidentReport)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(IncidentReport.tenant_id == tid)
    if elder_id is not None:
        _elder_for_staff(db, user, elder_id)
        q = q.filter(IncidentReport.elder_id == elder_id)
    else:
        ids = team_elder_ids(db, user)
        if ids is not None:
            q = q.filter(IncidentReport.elder_id.in_(ids or {-1}))
    if status:
        q = q.filter(IncidentReport.status == status)
    rows = q.order_by(IncidentReport.occurred_at.desc()).limit(200).all()
    elders = {e.id: e for e in db.query(Elder).filter(Elder.id.in_({r.elder_id for r in rows} or {-1})).all()}
    out = {"reports": [serialize(r, elders.get(r.elder_id)) for r in rows]}
    if elder_id is not None:
        out["counts"] = counts_for(db, elder_id)
    return out


def get_report(db: Session, user: User, report_id: int) -> dict:
    r = _report_for_staff(db, user, report_id)
    return serialize(r, db.get(Elder, r.elder_id))


def update_report(db: Session, user: User, report_id: int, data: dict) -> dict:
    r = _report_for_staff(db, user, report_id)
    if r.status == "closed" and set(data) - {"staff_notes"}:
        raise_bad_request("This report is closed")
    _apply_fields(r, data, creating=False)
    if "serious" in data or "kind" in data or "injury" in data:
        r.serious = is_serious(r.kind, r.injury, bool(data.get("serious", r.serious)))
    if "staff_notes" in data:
        r.staff_notes = _txt(data.get("staff_notes"), 4000)
    if "family_summary" in data:
        r.family_summary = _txt(data.get("family_summary"), 2000)
    db.commit()
    return get_report(db, user, r.id)


def review_report(db: Session, user: User, report_id: int, data: dict) -> dict:
    """Manager has read it: the family now sees the plain summary; leaves "Needs attention"."""
    r = _report_for_staff(db, user, report_id)
    if r.status == "closed":
        raise_bad_request("This report is closed")
    if data.get("staff_notes") is not None:
        r.staff_notes = _txt(data.get("staff_notes"), 4000)
    if "follow_ups" in data:
        r.follow_ups = _clean_follow_ups(data.get("follow_ups"))
        flag_modified(r, "follow_ups")
    r.family_summary = _txt(data.get("family_summary"), 2000) or r.family_summary or default_family_summary(r)
    r.status = "reviewed"
    r.reviewed_by_user_id = user.id
    r.reviewed_at = _now()
    db.commit()
    return get_report(db, user, r.id)


def close_report(db: Session, user: User, report_id: int, data: dict) -> dict:
    r = _report_for_staff(db, user, report_id)
    outcome = _txt(data.get("outcome"), 2000)
    if not outcome:
        raise_bad_request("Write the outcome before closing")
    if r.status == "closed":
        raise_bad_request("This report is already closed")
    if r.status == "open":  # closing also counts as the review
        r.reviewed_by_user_id = user.id
        r.reviewed_at = _now()
    if data.get("family_summary"):
        r.family_summary = _txt(data.get("family_summary"), 2000)
    r.family_summary = r.family_summary or default_family_summary(r)
    r.outcome = outcome
    r.status = "closed"
    r.closed_at = _now()
    db.commit()
    return get_report(db, user, r.id)


# --- dashboard and family -------------------------------------------------------------


def attention_rows(db: Session, elders: list[Elder]) -> list[dict]:
    """Serious reports nobody has reviewed yet, newest first."""
    by_id = {e.id: e for e in elders}
    rows = (
        db.query(IncidentReport)
        .filter(
            IncidentReport.elder_id.in_(list(by_id) or [-1]),
            IncidentReport.serious.is_(True),
            IncidentReport.status == "open",
        )
        .order_by(IncidentReport.occurred_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "elder_id": r.elder_id,
            "elder_name": _name(by_id[r.elder_id].first_name, by_id[r.elder_id].last_name),
            "kind": r.kind,
            "kind_label": KINDS.get(r.kind, "Other"),
            "occurred_at": _iso(r.occurred_at),
            "injury": r.injury or "",
            "reported_by_name": r.reported_by_name or "",
        }
        for r in rows
    ]


def family_list(db: Session, elder: Elder) -> list[dict]:
    rows = (
        db.query(IncidentReport)
        .filter(IncidentReport.elder_id == elder.id, IncidentReport.status.in_(FAMILY_VISIBLE))
        .order_by(IncidentReport.occurred_at.desc())
        .limit(50)
        .all()
    )
    return [family_view(r) for r in rows]
