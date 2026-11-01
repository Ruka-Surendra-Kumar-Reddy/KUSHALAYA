"""Care jobs: scheduled visits, assessments and installs (see app/models/care_job.py).

Managers schedule jobs for clients in their team and pick the caregiver; the
caregiver moves the job through the field app. The family gets a portal
notification whenever a job is scheduled, changed or cancelled.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import event, or_
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import CAREGIVER, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.core.team_scope import assert_elder_in_team, team_caregiver_ids, team_elder_ids
from app.models.care_job import JOB_KINDS, JOB_STATUSES, CareJob
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User

IST = timezone(timedelta(hours=5, minutes=30))
KIND_LABEL = {"visit": "Care visit", "assessment": "Home safety assessment", "install": "Product installation"}
STATUS_LABEL = {
    "requested": "Requested",
    "scheduled": "Scheduled",
    "on_the_way": "On the way",
    "checked_in": "Checked in",
    "completed": "Completed",
    "cancelled": "Cancelled",
    "missed": "Missed",
}
STAFF_FIELD_ROLES = ("SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER")

# What a caregiver may move a job to, from each status.
CAREGIVER_NEXT = {
    "scheduled": {"on_the_way", "checked_in"},
    "on_the_way": {"checked_in"},
    "checked_in": {"completed"},
}

# What staff may set through update_job. Completed, cancelled and missed are
# final — a missed visit is rebooked as a new job.
STAFF_NEXT = {
    "requested": {"scheduled", "cancelled"},
    "scheduled": {"on_the_way", "checked_in", "cancelled", "missed"},
    "on_the_way": {"scheduled", "checked_in", "cancelled", "missed"},
    "checked_in": {"completed", "cancelled"},
    # A missed job can still be called off (it otherwise stays "overdue" forever).
    "missed": {"cancelled"},
}
OPEN_STATUSES = ("requested", "scheduled", "on_the_way", "checked_in")
DEFAULT_MINUTES = 60


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _when(dt: datetime | None) -> str:
    dt = _aware(dt)
    if not dt:
        return "a time to be confirmed"
    local = dt.astimezone(IST)
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def _family_when(dt: datetime | None) -> str:
    """Like _when, but each family reader's email shows it in their own timezone."""
    if not _aware(dt):
        return _when(dt)
    from app.livewell.family_contacts import email_time

    return email_time(_aware(dt))


def _name(first: str | None, last: str | None) -> str:
    return f"{first or ''} {last or ''}".strip()


def home_point(db: Session, elder_id: int | None) -> dict | None:
    """The client's saved home pin ({lat, lng}) for directions, or None."""
    if not elder_id:
        return None
    from app.models.elder_location import ElderLocation

    row = db.query(ElderLocation).filter(ElderLocation.elder_id == elder_id).first()
    return {"lat": float(row.latitude), "lng": float(row.longitude)} if row else None


def _assignee_name(db: Session, job: CareJob) -> str:
    u = db.get(User, job.assignee_user_id) if job.assignee_user_id else None
    return _name(u.first_name, u.last_name) if u else ""


def serialize(db: Session, job: CareJob) -> dict:
    elder = db.get(Elder, job.elder_id)
    cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
    iso = lambda d: _aware(d).isoformat() if d else None  # noqa: E731
    return {
        "id": job.id,
        "elder_id": job.elder_id,
        "elder_name": _name(elder.first_name, elder.last_name) if elder else "",
        "elder_address": (elder.address if elder else "") or "",
        "elder_home": home_point(db, job.elder_id),
        # Tap-to-call on the caregiver's visit card.
        "elder_phone": ((elder.phone or "") if elder else "").strip(),
        "kind": job.kind,
        "kind_label": KIND_LABEL.get(job.kind, "Visit"),
        "title": job.title or KIND_LABEL.get(job.kind, "Visit"),
        "tasks": job.tasks or "",
        "location": job.location or ((elder.address if elder else "") or ""),
        "scheduled_at": iso(job.scheduled_at),
        "duration_minutes": job.duration_minutes,
        "caregiver_id": job.caregiver_id,
        "caregiver_name": _name(cg.first_name, cg.last_name) if cg else "",
        "assignee_user_id": job.assignee_user_id,
        "assignee_name": _assignee_name(db, job),
        "status": job.status,
        "status_label": STATUS_LABEL.get(job.status, job.status),
        "request_id": job.request_id,
        "assessment_id": job.assessment_id,
        "series_id": job.series_id,
        "series_date": job.series_date.isoformat() if job.series_date else None,
        "staff_note": job.staff_note or "",
        "caregiver_note": job.caregiver_note or "",
        "started_at": iso(job.started_at),
        "checked_in_at": iso(job.checked_in_at),
        "completed_at": iso(job.completed_at),
        "created_at": iso(job.created_at),
        "report": job.report or None,
        "photo_urls": _report_photos(job.report, family=False),
        "know_them": _know_them(elder) if elder else None,
        "checklist": _checklist(elder) if elder and job.kind == "visit" else [],
    }


def _report_photos(report, *, family: bool) -> list[str]:
    from app.livewell.visit_reports import photo_urls

    return photo_urls(report, family=family)


def _checklist(elder: Elder) -> list[dict]:
    from app.livewell.visit_checklist import items_for

    return items_for(elder)


def _know_them(elder: Elder) -> dict:
    from app.livewell.visit_reports import know_them

    return know_them(elder)


# The family page each kind of notice opens.
_FAMILY_PAGE = {"report": "/visits"}


ON_THE_WAY_NOTICE_WINDOW = timedelta(hours=3)


def _in_past(at: datetime | None, now: datetime | None = None) -> bool:
    """A visit dated before now: no "scheduled" / "updated" notice for it."""
    at = _aware(at)
    return at is not None and at < (now or datetime.now(timezone.utc))


def _on_the_way_notice_ok(at: datetime | None, now: datetime | None = None) -> bool:
    """Send "on the way" only within 3 hours of the scheduled time."""
    at = _aware(at)
    if at is None:
        return True
    return at - (now or datetime.now(timezone.utc)) <= ON_THE_WAY_NOTICE_WINDOW


def _notify_family(db: Session, elder: Elder, title: str, body: str, event: str = "visit") -> None:
    from app.livewell.family_notify import notify_family

    notify_family(db, elder, title, body, event=event, path=_FAMILY_PAGE.get(event, "/schedule"))


def _notify_staff_done(db: Session, elder: Elder, title: str, body: str) -> None:
    from app.livewell.email_notifications import email_staff, staff_path

    name = f"{elder.first_name} {elder.last_name}".strip()
    email_staff(db, elder, "visit_done", f"{title} — {name}", body, path=staff_path(elder, "timeline"))


def _elder_for(db: Session, user: User, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(user, elder.tenant_id)
    assert_elder_in_team(db, user, elder.id)
    return elder


INACTIVE_CAREGIVER = ("INACTIVE", "TERMINATED", "EXITED", "ARCHIVED")


SERIES_CHANGED_NOTE = "Series changed"  # staff_note on visits cancelled because their series changed or ended


def not_series_changed():
    """SQL filter: leave out visits cancelled because their repeating series changed (NULL-safe)."""
    return or_(
        CareJob.status != "cancelled", CareJob.staff_note.is_(None), CareJob.staff_note != SERIES_CHANGED_NOTE
    )


def caregiver_inactive(cg: Caregiver | None) -> bool:
    return bool(cg) and (cg.status or "ACTIVE").upper() in INACTIVE_CAREGIVER


def _caregiver_for(
    db: Session, user: User, elder: Elder, caregiver_id: int | None, *, active_only: bool = True
) -> Caregiver | None:
    if caregiver_id is None:
        return None
    cg = db.get(Caregiver, caregiver_id)
    if not cg or cg.tenant_id != elder.tenant_id:
        raise_bad_request("Caregiver not found")
    team = team_caregiver_ids(db, user)
    if team is not None and cg.id not in team:
        raise_bad_request("That caregiver is not in your team")
    if active_only and caregiver_inactive(cg):
        raise_bad_request(f"{cg.first_name} no longer works with us. Pick another caregiver.")
    return cg


def list_jobs(
    db: Session,
    user: User,
    *,
    elder_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    include_closed: bool = True,
) -> list[dict]:
    q = db.query(CareJob).filter(not_series_changed())
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(CareJob.tenant_id == tid)
    if elder_id is not None:
        _elder_for(db, user, elder_id)
        q = q.filter(CareJob.elder_id == elder_id)
    team = team_elder_ids(db, user)
    if team is not None:
        q = q.filter(CareJob.elder_id.in_(team or {-1}))
    if start is not None:
        q = q.filter(CareJob.scheduled_at >= start)
    if end is not None:
        q = q.filter(CareJob.scheduled_at < end)
    if not include_closed:
        q = q.filter(CareJob.status.notin_(("completed", "cancelled", "missed")))
    rows = q.order_by(CareJob.scheduled_at.desc().nullslast(), CareJob.id.desc()).limit(500).all()
    handled = rebooked_missed_ids(db, [j for j in rows if j.status == "missed"])
    from app.livewell.live_location import view as live_view

    from app.livewell.visit_location import view as location_view

    out = []
    for j in rows:
        if j.id in handled:
            continue
        item = serialize(db, j)
        item["visit_location"] = location_view(db, j)  # staff only, like live
        if j.status == "on_the_way":
            item["live"] = live_view(db, j)  # staff only; family/caregiver lists never carry it
        out.append(item)
    return out


ASSESSOR_ROLES = ("CARE_MANAGER", "TENANT_ADMIN", "SYSTEM_ADMIN")


def _care_manager_for(db: Session, elder: Elder, user_id: int | None) -> User | None:
    """The staff member doing a home assessment: a care manager (or the owner)."""
    if user_id is None:
        return None
    u = db.get(User, int(user_id))
    if not u or u.role not in ASSESSOR_ROLES or (u.tenant_id not in (None, elder.tenant_id)):
        raise_bad_request("Pick a care manager")
    if (u.status or "ACTIVE").upper() != "ACTIVE":
        raise_bad_request(f"{u.first_name} is not active. Pick another care manager.")
    return u


def create_job(db: Session, user: User, data: dict) -> dict:
    elder = _elder_for(db, user, int(data["elder_id"]))
    kind = str(data.get("kind") or "visit")
    if kind not in JOB_KINDS:
        raise_bad_request("Choose visit, assessment or install")
    scheduled_at = _aware(data.get("scheduled_at"))
    if scheduled_at is not None:
        scheduled_at = scheduled_at.astimezone(timezone.utc)  # "+05:30" from the form is stored as UTC
    if scheduled_at is None:
        raise_bad_request("Pick a date and time")
    cg = _caregiver_for(db, user, elder, data.get("caregiver_id"))
    if not data.get("force"):
        _check_clash(db, elder, kind, scheduled_at, data.get("duration_minutes"), cg)
    job = CareJob(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind=kind,
        title=(data.get("title") or KIND_LABEL[kind]).strip()[:200],
        tasks=(data.get("tasks") or "").strip(),
        location=(data.get("location") or elder.address or "").strip()[:500],
        scheduled_at=scheduled_at,
        duration_minutes=data.get("duration_minutes"),
        caregiver_id=cg.id if cg else None,
        # Assessments default to the client's own care manager.
        assignee_user_id=(
            _care_manager_for(db, elder, data.get("assignee_user_id") or elder.manager_user_id).id
            if kind == "assessment" and (data.get("assignee_user_id") or elder.manager_user_id)
            else None
        ),
        status="scheduled",
        request_id=data.get("request_id"),
        product_ids=",".join(str(p) for p in (data.get("product_ids") or [])),
        staff_note=(data.get("staff_note") or "").strip(),
        created_by_user_id=user.id,
    )
    db.add(job)
    db.flush()
    who = f" with {cg.first_name}" if cg else ""
    if not _in_past(scheduled_at):
        _notify_family(
            db,
            elder,
            f"{job.title} scheduled",
            f"{job.title} on {_family_when(scheduled_at)}{who}.",
        )
    note = ""
    if data.get("request_id") and not _close_family_request(db, elder, str(data["request_id"]), job):
        job.request_id = None
        note = "The family had already closed that request, so this booking isn't linked to it."
    db.commit()
    db.refresh(job)
    out = serialize(db, job)
    if note:
        out["note"] = note
    return out


def _hm(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%I:%M").lstrip("0")


def _check_clash(
    db: Session,
    elder: Elder,
    kind: str,
    at: datetime,
    minutes: int | None,
    cg: Caregiver | None,
    *,
    skip_id: int | None = None,
) -> None:
    """409 when the caregiver is already booked then, or the client already has an
    open assessment. The form resends with force=true after "Book anyway"."""
    q = db.query(CareJob).filter(CareJob.status.in_(OPEN_STATUSES))
    if skip_id is not None:
        q = q.filter(CareJob.id != skip_id)
    if kind == "assessment":
        other = q.filter(CareJob.elder_id == elder.id, CareJob.kind == "assessment").first()
        if other:
            raise_conflict(
                f"{elder.first_name} already has a home safety assessment on {_when(other.scheduled_at)}. Book anyway?"
            )
    if cg is None:
        return
    start = at
    end = at + timedelta(minutes=minutes or DEFAULT_MINUTES)
    for other in q.filter(CareJob.caregiver_id == cg.id, CareJob.scheduled_at.isnot(None)).all():
        o_start = _aware(other.scheduled_at)
        o_end = o_start + timedelta(minutes=other.duration_minutes or DEFAULT_MINUTES)
        if o_start < end and start < o_end:
            day = o_start.astimezone(IST).strftime("%a %d %b").replace(" 0", " ")
            raise_conflict(
                f"{cg.first_name} already has a visit {_hm(o_start)}–{_hm(o_end)} on {day}. Book anyway?"
            )


def _close_family_request(db: Session, elder: Elder, request_id: str, job: CareJob) -> bool:
    """The family's request is now scheduled: mark it confirmed and link the job.

    False when the family already cancelled it (or it is done/declined) — booking
    must not bring it back; the caller leaves the job unlinked. Ids that aren't
    family requests (e.g. "order-N") stay linked.
    """
    from app.livewell.family_service_requests import _requests, _save_requests

    rows = _requests(elder)
    for r in rows:
        if str(r.get("id")) == request_id:
            if r.get("status") not in ("requested", "confirmed"):
                return False
            r["status"] = "confirmed"
            r["visit_id"] = f"job-{job.id}"
            r["preferred_at"] = _aware(job.scheduled_at).isoformat() if job.scheduled_at else r.get("preferred_at")
    _save_requests(db, elder, rows)
    return True


def rebooked_missed_ids(db: Session, missed: list[CareJob]) -> set[int]:
    """Missed jobs already dealt with: a newer, not-cancelled job exists for the same
    client and kind (and the same family request, when there is one), booked after
    the missed job's time. Schedule and the dashboard hide these."""
    if not missed:
        return set()
    elder_ids = {j.elder_id for j in missed}
    later = (
        db.query(CareJob)
        .filter(CareJob.elder_id.in_(elder_ids), CareJob.status.notin_(("cancelled", "missed")))
        .all()
    )
    done: set[int] = set()
    for m in missed:
        since = _aware(m.scheduled_at) or _aware(m.created_at)
        for j in later:
            if j.elder_id != m.elder_id or j.kind != m.kind or j.id == m.id:
                continue
            if m.request_id and j.request_id != m.request_id:
                continue
            if since and _aware(j.created_at) and _aware(j.created_at) < since:
                continue
            done.add(m.id)
            break
    return done


def _missed_notices(db: Session, elder: Elder, job: CareJob) -> None:
    """Missed visit: email the care manager, tell the family (timer and staff alike)."""
    from app.livewell.email_notifications import email_staff

    when = _when(job.scheduled_at) + " IST" if job.scheduled_at else "its planned time"
    name = f"{elder.first_name} {elder.last_name}".strip()
    cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
    who = f" with {cg.first_name}" if cg else ""
    email_staff(
        db,
        elder,
        "visit_missed",
        f"Missed: {job.title} — {name}",
        f"The {job.title.lower()}{who} for {name} on {when} was not started.\n"
        "The family has been told it didn’t happen and that their care manager will call them.\n"
        "Next: call the family today, then book a new time from Schedule.",
        path="/kushalaya/visits",
    )
    # "Today" only when the visit was due today; a missed visit found days later
    # (the timer catching up) must not promise a call today.
    today = not job.scheduled_at or datetime.now(timezone.utc) - _aware(job.scheduled_at) < timedelta(hours=24)
    _notify_family(
        db,
        elder,
        f"{job.title} didn’t happen",
        f"We’re sorry — the {job.title.lower()} planned for {_family_when(job.scheduled_at) + ' IST' if job.scheduled_at else when} didn’t take place.\n"
        f"Your care manager will call you{' today' if today else ''} to find a new time that suits you. "
        "If anything is urgent before then, reply in Messages or call us.",
        "missed",
    )


@event.listens_for(CareJob.status, "set")
def _follow_request(job: CareJob, value, oldvalue, _initiator) -> None:
    """The family's request follows its job, whichever code path closes it:
    completed → request done; cancelled or missed → back to "requested" so it
    waits to be scheduled again. A request the family cancelled stays cancelled."""
    if value == oldvalue or value not in ("completed", "cancelled", "missed") or not job.request_id:
        return
    db = object_session(job)
    if db is None or job.elder_id is None:
        return
    from app.livewell.family_service_requests import _requests

    with db.no_autoflush:
        elder = db.get(Elder, job.elder_id)
        if not elder:
            return
        rows = _requests(elder)
        changed = False
        for r in rows:
            if str(r.get("id")) != str(job.request_id) or r.get("status") not in ("confirmed", "requested"):
                continue
            if value == "completed":
                r["status"] = "done"
            else:
                r["status"] = "requested"
                r["staff_note"] = "We'll rebook this"
                r["visit_id"] = None
            r["updated_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
        if changed:
            attrs = dict(elder.custom_attributes or {})
            block = dict(attrs.get("safe_home") or {})
            block["service_requests"] = rows
            attrs["safe_home"] = block
            elder.custom_attributes = attrs
            flag_modified(elder, "custom_attributes")


def cancel_for_request(db: Session, elder: Elder, request_id: str) -> CareJob | None:
    """The family cancelled their request: cancel its open job too (no commit)."""
    job = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder.id, CareJob.request_id == str(request_id), CareJob.status.in_(OPEN_STATUSES))
        .first()
    )
    if job:
        job.status = "cancelled"
        from app.livewell.live_location import clear as clear_live

        clear_live(db, job.id)
    return job


def update_job(db: Session, user: User, job_id: int, data: dict) -> dict:
    job = db.get(CareJob, job_id)
    if not job:
        raise_not_found("Job not found")
    elder = _elder_for(db, user, job.elder_id)
    before = (job.scheduled_at, job.caregiver_id, job.status)
    status = data.get("status")
    if status and status != job.status:
        if status not in JOB_STATUSES:
            raise_bad_request("Unknown status")
        if status not in STAFF_NEXT.get(job.status, set()):
            raise_bad_request(f"Can't change a {STATUS_LABEL.get(job.status, job.status).lower()} job to {STATUS_LABEL[status].lower()}")
        if job.kind == "assessment" and status == "completed" and not job.assessment_id:
            raise_bad_request("Finish the assessment first")
        if status == "checked_in":
            assert_check_in_not_too_early(job)
    elif job.status in ("completed", "cancelled", "missed") and any(
        f in data for f in ("scheduled_at", "caregiver_id")
    ):
        raise_bad_request(f"This job is {STATUS_LABEL[job.status].lower()} — book a new one instead")
    if "scheduled_at" in data and data["scheduled_at"] is not None:
        job.scheduled_at = _aware(data["scheduled_at"]).astimezone(timezone.utc)
    if "assignee_user_id" in data:
        cm = _care_manager_for(db, elder, data["assignee_user_id"])
        job.assignee_user_id = cm.id if cm else None
    if "caregiver_id" in data:
        cg = _caregiver_for(db, user, elder, data["caregiver_id"])
        job.caregiver_id = cg.id if cg else None
        if cg and (job.staff_note or "").startswith("Needs a caregiver:"):
            job.staff_note = ""  # the clash note is answered once someone is assigned
    for f in ("title", "tasks", "location", "staff_note"):
        if f in data and data[f] is not None:
            setattr(job, f, str(data[f]).strip())
    if "duration_minutes" in data:
        job.duration_minutes = data["duration_minutes"]
    if not data.get("force") and (job.scheduled_at, job.caregiver_id) != before[:2] and job.scheduled_at:
        cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
        # Only the caregiver clash applies on a change; the assessment check is for new bookings.
        _check_clash(db, elder, "visit", _aware(job.scheduled_at), job.duration_minutes, cg, skip_id=job.id)
    if status:
        job.status = status
        if status == "completed" and not job.completed_at:
            job.completed_at = datetime.now(timezone.utc)
    if job.status != "on_the_way" or job.caregiver_id != before[1]:
        from app.livewell.live_location import clear as clear_live

        clear_live(db, job.id)  # live location is kept only while on the way
    if job.status == "missed" and before[2] != "missed":
        _missed_notices(db, elder, job)
    elif job.status == "completed" and before[2] != "completed" and job.kind != "assessment":
        # Ops closed it (no caregiver tap): the family still hears it was done, and when.
        # (Assessments tell the family themselves when the report is finished.)
        done_at = _family_when(job.completed_at) + " IST"
        _notify_family(
            db, elder, f"{job.title} completed", f"The {job.title.lower()} was completed on {done_at}.", "report"
        )
    elif job.status == "cancelled" and before[2] != "cancelled":
        _notify_family(db, elder, f"{job.title} cancelled", f"{job.title} on {_family_when(job.scheduled_at)} was cancelled.")
    elif (
        (job.scheduled_at, job.caregiver_id) != before[:2]
        and job.status in ("scheduled", "on_the_way")
        and not _in_past(job.scheduled_at)
    ):
        cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
        who = f" with {cg.first_name}" if cg else ""
        _notify_family(db, elder, f"{job.title} updated", f"{job.title} is now on {_family_when(job.scheduled_at)}{who}.")
    db.commit()
    db.refresh(job)
    return serialize(db, job)


# --- Caregiver side ------------------------------------------------------------


def _caregiver_job(db: Session, user: User, job_id: int) -> CareJob:
    """The job a field user may work on.

    A caregiver works on their own jobs. Staff (admins, care managers) run any
    job for a client in their team — the care manager can do the whole visit
    from the ops portal when the caregiver does not use the app.
    """
    job = db.get(CareJob, job_id)
    if not job:
        raise_not_found("Job not found")
    if user.role == CAREGIVER:
        if not user.caregiver_id or job.caregiver_id != user.caregiver_id:
            raise_not_found("Job not found")
        return job
    if user.role in STAFF_FIELD_ROLES:
        assert_tenant_access(user, job.tenant_id)
        assert_elder_in_team(db, user, job.elder_id)
        return job
    raise_bad_request("Not allowed")


def list_for_caregiver(db: Session, user: User, *, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    day_start = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(CareJob)
        .filter(
            CareJob.caregiver_id == user.caregiver_id,
            CareJob.status != "cancelled",
            or_(
                CareJob.scheduled_at >= day_start - timedelta(days=1),
                # Started on an earlier day and never finished: the app asks to finish it.
                (CareJob.status.in_(("checked_in", "on_the_way")))
                & (CareJob.scheduled_at >= day_start - timedelta(days=30)),
            ),
            CareJob.scheduled_at < day_start + timedelta(days=15),
        )
        .order_by(CareJob.scheduled_at)
        .all()
    )
    return [serialize(db, j) for j in rows]


CHECK_IN_EARLY_HOURS = 12


def assert_check_in_not_too_early(job: CareJob, now: datetime | None = None) -> None:
    """Refuse "arrived" more than 12 h before the booked time (a tap on a future day's visit)."""
    at = _aware(job.scheduled_at)
    now = now or datetime.now(timezone.utc)
    if at is not None and at - now > timedelta(hours=CHECK_IN_EARLY_HOURS):
        when = at.astimezone(IST)
        label = f"{when.strftime('%a')} {when.day} {when.strftime('%b')}, {when.strftime('%I:%M %p').lstrip('0').lower()}"
        raise_bad_request(
            f"This visit is booked for {label} IST. You can check in from {CHECK_IN_EARLY_HOURS} hours before it starts."
        )


def record_location(db: Session, job: CareJob, event: str, lat, lng, accuracy=None) -> None:
    from app.livewell.visit_location import record

    record(db, job, event, lat, lng, accuracy)


def caregiver_set_status(
    db: Session,
    user: User,
    job_id: int,
    status: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    accuracy: float | None = None,
    note: str | None = None,
) -> dict:
    """Move a job along. lat/lng/accuracy is where it was done from (optional here;
    the caregiver-portal route requires it for check-in and completion)."""
    job = _caregiver_job(db, user, job_id)
    allowed = CAREGIVER_NEXT.get(job.status, set())
    if status not in allowed:
        raise_bad_request(f"Can't go from {STATUS_LABEL.get(job.status)} to {STATUS_LABEL.get(status, status)}")
    if job.kind == "assessment" and status == "completed" and not job.assessment_id:
        raise_bad_request("Finish the assessment first")
    if status == "checked_in":
        assert_check_in_not_too_early(job)
    now = datetime.now(timezone.utc)
    job.status = status
    if status != "on_the_way":
        from app.livewell.live_location import clear as clear_live

        clear_live(db, job.id)  # arrived / done: forget where the caregiver was
    if status == "on_the_way":
        job.started_at = now
    elif status == "checked_in":
        job.checked_in_at = now
        record_location(db, job, "checkin", lat, lng, accuracy)
    elif status == "completed":
        job.completed_at = now
        record_location(db, job, "checkout", lat, lng, accuracy)
    if note:
        job.caregiver_note = note.strip()
    elder = db.get(Elder, job.elder_id)
    cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
    # A care manager doing the visit from the ops page (no caregiver on it): their name.
    first = cg.first_name if cg else (user.first_name if user.role != CAREGIVER and user.first_name else "Your care team")
    if status == "on_the_way":
        if _on_the_way_notice_ok(job.scheduled_at, now):
            from app.livewell.email_notifications import FAMILY_URL
            from app.livewell.family_notify import notify_family
            from app.livewell.live_location import track_token

            db.flush()  # started_at is part of the link's signature
            token = track_token(job)
            follow = f" Follow live: {FAMILY_URL}/track/{token}" if token else ""
            notify_family(
                db, elder, f"{first} is on the way", f"{first} is on the way for the {job.title.lower()}.{follow}",
                event="visit_live", path=f"/track/{token}" if token else _FAMILY_PAGE.get("visit_live", "/schedule"),
            )
    elif status == "checked_in":
        _notify_family(db, elder, f"{first} has arrived", f"{first} checked in for the {job.title.lower()}.", "visit_live")
    elif status == "completed":
        done = note.strip() if note else f"{first} completed the {job.title.lower()}."
        _notify_family(db, elder, f"{job.title} completed", done, "report")
        _notify_staff_done(db, elder, f"{job.title} completed", done)
    db.commit()
    db.refresh(job)
    return serialize(db, job)


# --- Family side ---------------------------------------------------------------


def family_visit_times(job: CareJob) -> dict:
    """Check-in / finish / duration a family can trust.

    A finish less than a minute after check-in (both stamped by the same tap, or
    seed data) is not shown, and the duration is the real time between them;
    the planned length is never shown as if it were how long the visit took.
    """
    start = _aware(job.checked_in_at or job.started_at)
    end = _aware(job.completed_at)
    if start and end and (end - start).total_seconds() >= 60:
        return {
            "checked_in_at": start,
            "checked_out_at": end,
            "duration_minutes": int(round((end - start).total_seconds() / 60)),
        }
    return {"checked_in_at": start, "checked_out_at": None, "duration_minutes": None}


def family_caregiver_name(db: Session, job: CareJob, *, full: bool = False) -> str:
    """The assigned caregiver, else the name saved on the visit report."""
    cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
    if cg is not None:
        last = (cg.last_name or "").strip()
        return f"{cg.first_name} {last[:1]}.".strip() if full and last else (cg.first_name or "")
    return str(((job.report or {}).get("caregiver_name") or "")).strip()


def family_jobs(db: Session, user: User) -> tuple[list[dict], list[dict]]:
    """(upcoming, recent) jobs for the family's client, shaped like family visits.

    Staff notes are never included; the caregiver's note to the family is.
    """
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    now = datetime.now(timezone.utc)
    rows = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder.id, CareJob.status != "cancelled")
        .order_by(CareJob.scheduled_at.desc())
        .limit(60)
        .all()
    )
    upcoming, recent = [], []
    for j in rows:
        when = _aware(j.completed_at if j.status == "completed" else j.scheduled_at) or now
        item = {
            "id": f"job-{j.id}",
            "visit_type": j.title or KIND_LABEL.get(j.kind, "Visit"),
            "visited_at": when.isoformat(),
            "staff_name": family_caregiver_name(db, j),
            "summary": "Your care manager will call you to rebook." if j.status == "missed" else _family_summary(j),
            "family_message": j.caregiver_note or "",
            "status": {"completed": "completed", "missed": "Didn't happen"}.get(j.status, "scheduled"),
            "can_rate": False,
            "wellness_notes": "",
            "concerns": [],
            "recommendations": "",
            "photo_ids": [],
            "photo_urls": _report_photos(j.report, family=True),
            "partner_id": "",
            "partner_name": "",
            # Actual time on the visit only; never the planned length.
            "duration_minutes": family_visit_times(j)["duration_minutes"] if j.status == "completed" else None,
        }
        if j.status in ("completed", "missed"):
            recent.append(item)
        elif when >= now - timedelta(hours=12):
            upcoming.append(item)
    # #106: each family login rates a completed visit once (1–5).
    from app.livewell.visit_feedback import my_ratings

    mine = my_ratings(db, user, [int(i["id"][4:]) for i in recent])
    for i in recent:
        r = mine.get(int(i["id"][4:]))
        if r:
            i.update(experience_rating=r.rating, experience_comment=r.comment or "", rated_at=_aware(r.created_at))
        else:
            i["can_rate"] = i["status"] == "completed"
    return upcoming, recent


def _family_summary(j: CareJob) -> str:
    checks = (j.report or {}).get("checks") or {}
    if not checks:
        return j.tasks or ""
    marks = " · ".join(f"{k.capitalize()} {'✓' if v == 'ok' else '!'}" for k, v in checks.items())
    from app.livewell import kushlife
    from app.livewell.visit_checklist import family_lines

    extra = family_lines((j.report or {}).get("checklist"))
    # Never all ticks on their own when the carer noted something (same words as the status).
    noted = kushlife.noted_text(kushlife.record_changes((j.report or {}).get("kushlife")))
    return f"KushLife check: {marks}" + (f" · noted: {noted}" if noted else "") + (f"\n{extra}" if extra else "")
