"""Repeating visits and the weekly roster (FIX_TODO 93).

A series ("Mon/Wed/Fri 10:00 for 60 min until 31 Mar") materialises ordinary
CareJobs about four weeks ahead; the jobs timer (daily_checks.run) tops the
horizon up. Each job has a stable key (series_id, series_date) so generation is
idempotent. A day the caregiver cannot take (another visit, approved leave) is
still created for the client — unassigned — and reported as a clash.

Times are IST wall-clock; the DB stores UTC.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.team_scope import team_caregiver_ids, team_elder_ids
from app.livewell import care_jobs
from app.livewell.care_jobs import (
    DEFAULT_MINUTES,
    INACTIVE_CAREGIVER,
    IST,
    OPEN_STATUSES,
    _aware,
    _name,
    caregiver_inactive,
)
from app.models.care_job import CareJob
from app.models.care_series import CareSeries
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.leave_request import LeaveRequest
from app.models.user import User

HORIZON_DAYS = 28
MAX_WEEKS = 52
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CLASH_KEEP = 60
SERIES_CHANGED_NOTE = care_jobs.SERIES_CHANGED_NOTE
# INACTIVE_CAREGIVER is re-exported from care_jobs (leave_cover imports it from here).

log = logging.getLogger(__name__)


# --- helpers ------------------------------------------------------------------


def ist_today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(IST).date()


def ist_start(day: date, time_hm: str) -> datetime:
    """The UTC instant of an IST wall-clock time on a day (India has no DST)."""
    h, m = (int(x) for x in time_hm.split(":"))
    return datetime.combine(day, time(h, m), tzinfo=IST).astimezone(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return _aware(dt).astimezone(timezone.utc)


def _parse_time(value) -> str:
    try:
        h, m = (int(x) for x in str(value).strip().split(":")[:2])
    except (TypeError, ValueError):
        raise_bad_request("Give the time as HH:MM")
    if not (0 <= h < 24 and 0 <= m < 60):
        raise_bad_request("Give the time as HH:MM")
    return f"{h:02d}:{m:02d}"


def _parse_days(value) -> list[int]:
    days = sorted({int(d) for d in (value or [])})
    if not days or any(d < 0 or d > 6 for d in days):
        raise_bad_request("Pick at least one day of the week")
    return days


def _days(series: CareSeries) -> list[int]:
    return [int(d) for d in (series.weekdays or "").split(",") if d != ""]


def _days_label(days: list[int]) -> str:
    return "/".join(DAY_NAMES[d] for d in days)


def _time_label(time_hm: str) -> str:
    h, m = (int(x) for x in time_hm.split(":"))
    return time(h, m).strftime("%I:%M %p").lstrip("0")


def _date_label(d: date) -> str:
    return d.strftime("%a %d %b").replace(" 0", " ")


def _duration(value) -> int:
    minutes = int(value or DEFAULT_MINUTES)
    if not 15 <= minutes <= 720:
        raise_bad_request("A visit is between 15 minutes and 12 hours")
    return minutes


def clash_reason(
    db: Session,
    cg: Caregiver,
    at: datetime,
    minutes: int | None,
    *,
    skip_ids: set[int] | frozenset = frozenset(),
) -> str | None:
    """Why the caregiver cannot take a visit then (approved leave, another visit), or None."""
    day = _aware(at).astimezone(IST).date()
    on_leave = (
        db.query(LeaveRequest.id)
        .filter(
            LeaveRequest.caregiver_id == cg.id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.start_date <= day,
            LeaveRequest.end_date >= day,
        )
        .first()
    )
    if on_leave:
        return f"{cg.first_name} is on leave on {_date_label(day)}"
    start = _utc(at)
    end = start + timedelta(minutes=minutes or DEFAULT_MINUTES)
    q = db.query(CareJob).filter(
        CareJob.caregiver_id == cg.id,
        CareJob.status.in_(OPEN_STATUSES),
        CareJob.scheduled_at.isnot(None),
        CareJob.scheduled_at >= start - timedelta(hours=13),
        CareJob.scheduled_at < end,
    )
    for other in q.all():
        if other.id in skip_ids:
            continue
        o_start = _utc(other.scheduled_at)
        o_end = o_start + timedelta(minutes=other.duration_minutes or DEFAULT_MINUTES)
        if o_start < end and start < o_end:
            hm = lambda d: d.astimezone(IST).strftime("%I:%M").lstrip("0")  # noqa: E731
            return f"{cg.first_name} already has a visit {hm(o_start)}–{hm(o_end)} on {_date_label(day)}"
    return None


def _series_for(db: Session, user: User, series_id: int) -> tuple[CareSeries, Elder]:
    series = db.get(CareSeries, series_id)
    if not series:
        raise_not_found("Repeating visit not found")
    try:
        elder = care_jobs._elder_for(db, user, series.elder_id)
    except Exception:
        raise_not_found("Repeating visit not found")
    return series, elder


def serialize_series(db: Session, series: CareSeries) -> dict:
    elder = db.get(Elder, series.elder_id)
    cg = db.get(Caregiver, series.caregiver_id) if series.caregiver_id else None
    days = _days(series)
    return {
        "id": series.id,
        "elder_id": series.elder_id,
        "elder_name": _name(elder.first_name, elder.last_name) if elder else "",
        "caregiver_id": series.caregiver_id,
        "caregiver_name": _name(cg.first_name, cg.last_name) if cg else "",
        "title": series.title,
        "tasks": series.tasks or "",
        "weekdays": days,
        "days_label": _days_label(days),
        "time": series.time_hm,
        "duration_minutes": series.duration_minutes,
        "start_date": series.start_date.isoformat(),
        "end_date": series.end_date.isoformat() if series.end_date else None,
        "generated_until": series.generated_until.isoformat() if series.generated_until else None,
        "status": series.status,
        "previous_id": series.previous_id,
        "clashes": list(series.clashes or []),
        "summary": _summary(series, cg),
    }


def _summary(series: CareSeries, cg: Caregiver | None) -> str:
    until = f" until {_date_label(series.end_date)}" if series.end_date else ""
    who = f" with {cg.first_name}" if cg else ""
    return (
        f"{_days_label(_days(series))} at {_time_label(series.time_hm)} for {series.duration_minutes} min"
        f", from {_date_label(series.start_date)}{until}{who}"
    )


# --- generation -----------------------------------------------------------------


def generate(db: Session, series: CareSeries, *, now: datetime | None = None) -> tuple[int, list[dict]]:
    """Create the series' jobs up to the horizon. Idempotent. Returns (created, clashes)."""
    now = now or datetime.now(timezone.utc)
    if series.status != "active":
        return 0, []
    today = ist_today(now)
    last = today + timedelta(days=HORIZON_DAYS)
    if series.end_date and series.end_date < last:
        last = series.end_date
    first = max(series.start_date, today)
    if series.generated_until and series.generated_until >= first:
        first = series.generated_until + timedelta(days=1)
    if first > last:
        return 0, []
    keys = {series.id}
    if series.previous_id:
        keys.add(series.previous_id)  # a day the old series still covers (in progress) is not doubled
    taken = {
        d
        for (d,) in db.query(CareJob.series_date)
        .filter(
            CareJob.series_id.in_(keys),
            CareJob.series_date >= first,
            CareJob.series_date <= last,
            # Visits cancelled because the series changed don't hold their day; a single
            # visit staff cancelled by hand does (it is not recreated).
            care_jobs.not_series_changed(),
        )
        .all()
    }
    elder = db.get(Elder, series.elder_id)
    cg = db.get(Caregiver, series.caregiver_id) if series.caregiver_id else None
    days = set(_days(series))
    created, clashes = 0, []
    day = first
    while day <= last:
        if day.weekday() in days and day not in taken:
            at = ist_start(day, series.time_hm)
            if at > now:
                if cg and caregiver_inactive(cg):
                    reason = f"{_name(cg.first_name, cg.last_name)} no longer works with us"
                else:
                    reason = clash_reason(db, cg, at, series.duration_minutes) if cg else None
                job = CareJob(
                    tenant_id=series.tenant_id,
                    elder_id=series.elder_id,
                    kind="visit",
                    title=series.title or "Care visit",
                    tasks=series.tasks or "",
                    location=(elder.address if elder else "") or "",
                    scheduled_at=at,
                    duration_minutes=series.duration_minutes,
                    caregiver_id=None if (reason or not cg) else cg.id,
                    status="scheduled",
                    staff_note=f"Needs a caregiver: {reason}" if reason else "",
                    created_by_user_id=series.created_by_user_id,
                    series_id=series.id,
                    series_date=day,
                )
                db.add(job)
                db.flush()
                created += 1
                if reason:
                    clashes.append({"date": day.isoformat(), "reason": reason, "job_id": job.id})
        day += timedelta(days=1)
    series.generated_until = last
    if clashes:
        series.clashes = (list(series.clashes or []) + clashes)[-CLASH_KEEP:]
    return created, clashes


def top_up_series(db: Session, *, now: datetime | None = None) -> dict[int, int]:
    """Jobs timer: end finished series and extend the rest to the horizon."""
    now = now or datetime.now(timezone.utc)
    today = ist_today(now)
    out: dict[int, int] = {}
    for series in db.query(CareSeries).filter(CareSeries.status == "active").all():
        try:
            with db.begin_nested():
                if series.end_date and series.end_date < today:
                    series.status = "ended"
                    continue
                created, _ = generate(db, series, now=now)
            if created:
                out[series.id] = created
        except Exception:  # one bad series must not stop the others
            log.exception("care series %s: top-up failed", series.id)
    db.commit()
    return out


# --- staff actions ----------------------------------------------------------------


def _end_date(data: dict, start: date) -> date | None:
    if data.get("end_date"):
        end = data["end_date"] if isinstance(data["end_date"], date) else date.fromisoformat(str(data["end_date"]))
    elif data.get("weeks"):
        weeks = int(data["weeks"])
        if not 1 <= weeks <= MAX_WEEKS:
            raise_bad_request(f"Choose 1 to {MAX_WEEKS} weeks")
        end = start + timedelta(days=7 * weeks - 1)
    else:
        return None
    if end < start:
        raise_bad_request("The end date is before the first visit")
    return end


def _start_date(data: dict, now: datetime) -> date:
    raw = data.get("start_date")
    start = (raw if isinstance(raw, date) else date.fromisoformat(str(raw))) if raw else ist_today(now)
    if start < ist_today(now):
        raise_bad_request("The first visit can't be in the past")
    return start


def _result(db: Session, series: CareSeries, created: int, clashes: list[dict], **extra) -> dict:
    return {"series": serialize_series(db, series), "created": created, "clashes": clashes, **extra}


def create_series(db: Session, user: User, data: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    elder = care_jobs._elder_for(db, user, int(data["elder_id"]))
    cg = care_jobs._caregiver_for(db, user, elder, data.get("caregiver_id"))
    start = _start_date(data, now)
    series = CareSeries(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        caregiver_id=cg.id if cg else None,
        title=(data.get("title") or "Care visit").strip()[:200],
        tasks=(data.get("tasks") or "").strip(),
        weekdays=",".join(str(d) for d in _parse_days(data.get("weekdays"))),
        time_hm=_parse_time(data.get("time")),
        duration_minutes=_duration(data.get("duration_minutes")),
        start_date=start,
        end_date=_end_date(data, start),
        status="active",
        created_by_user_id=user.id,
    )
    db.add(series)
    db.flush()
    created, clashes = generate(db, series, now=now)
    care_jobs._notify_family(db, elder, "Regular visits booked", f"Regular visits: {_summary(series, cg)}.")
    db.commit()
    db.refresh(series)
    return _result(db, series, created, clashes)


def list_series(db: Session, user: User, *, elder_id: int | None = None, include_ended: bool = False) -> list[dict]:
    q = db.query(CareSeries)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(CareSeries.tenant_id == tid)
    if elder_id is not None:
        care_jobs._elder_for(db, user, elder_id)
        q = q.filter(CareSeries.elder_id == elder_id)
    team = team_elder_ids(db, user)
    if team is not None:
        q = q.filter(CareSeries.elder_id.in_(team or {-1}))
    if not include_ended:
        q = q.filter(CareSeries.status == "active")
    return [serialize_series(db, s) for s in q.order_by(CareSeries.id.desc()).limit(300).all()]


def _drop_scheduled(
    db: Session,
    series: CareSeries,
    *,
    from_date: date | None = None,
    after: datetime | None = None,
    user: User | None = None,
    keep_ids: set[int] | frozenset = frozenset(),
) -> int:
    """Cancel not-yet-started visits of a series (from a day, or after an instant).

    Cancelled, not deleted, so the history stays; staff_note marks why. Cancelled
    visits are never marked missed and family schedules leave them out. Each one is
    audit-logged with its caregiver (there is no caregiver notification channel yet)."""
    from app.services.audit_service import AuditService

    q = db.query(CareJob).filter(CareJob.series_id == series.id, CareJob.status == "scheduled")
    if from_date is not None:
        q = q.filter(CareJob.series_date >= from_date)
    n = 0
    for job in q.all():
        if job.id in keep_ids:
            continue
        if after is not None and _utc(job.scheduled_at) <= after:
            continue
        job.status = "cancelled"
        job.staff_note = SERIES_CHANGED_NOTE
        AuditService.log(
            db,
            tenant_id=job.tenant_id,
            user_id=user.id if user else None,
            entity_type="care_job",
            entity_id=job.id,
            action="series_visit_cancelled",
            new_value={
                "series_id": series.id,
                "caregiver_id": job.caregiver_id,
                "date": job.series_date.isoformat() if job.series_date else None,
            },
        )
        n += 1
    db.flush()
    return n


def _edited_one(series: CareSeries, job: CareJob) -> bool:
    """Was this visit changed on its own (scope "one") away from the series rule?"""
    note = job.staff_note or ""
    clash = note.startswith("Needs a caregiver:")
    if job.caregiver_id != series.caregiver_id and not (clash and job.caregiver_id is None):
        return True
    if job.series_date and _utc(job.scheduled_at) != ist_start(job.series_date, series.time_hm):
        return True
    if (job.duration_minutes or DEFAULT_MINUTES) != (series.duration_minutes or DEFAULT_MINUTES):
        return True
    if (job.tasks or "") != (series.tasks or ""):
        return True
    return bool(note) and not clash


def change_series(db: Session, user: User, series_id: int, data: dict, *, now: datetime | None = None) -> dict:
    """Edit one visit of a series, or this visit and all following ones.

    scope "one": the job keeps its place in the series; only that visit moves
    (same clash rule as any booking — 409 unless force).
    scope "following": the series is split at the job's day; a new series with the
    changes takes over from there and the old one ends the day before.
    """
    now = now or datetime.now(timezone.utc)
    series, elder = _series_for(db, user, series_id)
    job = db.get(CareJob, int(data["job_id"])) if data.get("job_id") else None
    if job is None or job.series_id != series.id:
        raise_bad_request("Pick a visit from this series")
    scope = data.get("scope") or "one"
    if scope == "one":
        if data.get("weekdays"):
            raise_bad_request("Days of the week change this and following visits")
        patch: dict = {"force": bool(data.get("force"))}
        if data.get("time"):
            day = job.series_date or _aware(job.scheduled_at).astimezone(IST).date()
            patch["scheduled_at"] = ist_start(day, _parse_time(data["time"]))
        if "caregiver_id" in data:
            patch["caregiver_id"] = data["caregiver_id"]
        if data.get("duration_minutes"):
            patch["duration_minutes"] = _duration(data["duration_minutes"])
        return {"job": care_jobs.update_job(db, user, job.id, patch)}
    if scope != "following":
        raise_bad_request("Choose this visit only, or this and following")
    if series.status != "active":
        raise_bad_request("This series has ended")
    if job.status != "scheduled":
        raise_bad_request("Pick a visit that hasn't started yet")
    from_date = job.series_date
    if from_date is None or from_date < ist_today(now):
        raise_bad_request("Pick a visit from today onwards")
    if "caregiver_id" in data:
        cg = care_jobs._caregiver_for(db, user, elder, data["caregiver_id"])
    else:
        # Kept from the series; if they have left, generate() reports each day as a clash.
        cg = care_jobs._caregiver_for(db, user, elder, series.caregiver_id, active_only=False)
    new = CareSeries(
        tenant_id=series.tenant_id,
        elder_id=series.elder_id,
        caregiver_id=cg.id if cg else None,
        title=(data.get("title") or series.title)[:200],
        tasks=data.get("tasks") if data.get("tasks") is not None else series.tasks,
        weekdays=",".join(str(d) for d in _parse_days(data["weekdays"])) if data.get("weekdays") else series.weekdays,
        time_hm=_parse_time(data["time"]) if data.get("time") else series.time_hm,
        duration_minutes=_duration(data.get("duration_minutes") or series.duration_minutes),
        start_date=from_date,
        end_date=series.end_date,
        status="active",
        previous_id=series.id,
        created_by_user_id=user.id,
    )
    # A visit on the split day that was edited on its own keeps its edits: it stays as it is
    # (moved into the new series so its day isn't doubled) and is reported as kept.
    kept_job = job if _edited_one(series, job) else None
    removed = _drop_scheduled(
        db, series, from_date=from_date, user=user, keep_ids={job.id} if kept_job else frozenset()
    )
    series.end_date = from_date - timedelta(days=1)
    if series.end_date < ist_today(now):
        series.status = "ended"
    db.add(new)
    db.flush()
    if kept_job is not None:
        kept_job.series_id = new.id
        db.flush()
    created, clashes = generate(db, new, now=now)
    care_jobs._notify_family(
        db, elder, "Regular visits changed", f"From {_date_label(from_date)}, regular visits: {_summary(new, cg)}."
    )
    db.commit()
    db.refresh(new)
    kept = [care_jobs.serialize(db, kept_job)] if kept_job is not None else []
    return _result(db, new, created, clashes, removed=removed, previous_id=series.id, kept=kept)


def end_series(db: Session, user: User, series_id: int, data: dict, *, now: datetime | None = None) -> dict:
    """End a series: after end_date (inclusive last day), or now (cancel what's left)."""
    now = now or datetime.now(timezone.utc)
    series, elder = _series_for(db, user, series_id)
    if series.status != "active":
        raise_bad_request("This series has already ended")
    today = ist_today(now)
    if data.get("end_date"):
        end = data["end_date"] if isinstance(data["end_date"], date) else date.fromisoformat(str(data["end_date"]))
        if end < today:
            raise_bad_request("Pick today or a later day")
        removed = _drop_scheduled(db, series, from_date=end + timedelta(days=1), user=user)
        series.end_date = end
        body = f"Regular visits ({_days_label(_days(series))}) end after {_date_label(end)}."
    else:
        removed = _drop_scheduled(db, series, after=now, user=user)
        series.end_date = today
        series.status = "ended"
        body = f"Regular visits ({_days_label(_days(series))}) have been stopped."
    if series.generated_until and series.end_date < series.generated_until:
        series.generated_until = series.end_date
    care_jobs._notify_family(db, elder, "Regular visits ending", body)
    db.commit()
    db.refresh(series)
    return {"series": serialize_series(db, series), "removed": removed}


# --- weekly roster ------------------------------------------------------------------


def _chip(db: Session, job: CareJob, names: dict[int, str]) -> dict:
    at = _aware(job.scheduled_at).astimezone(IST)
    end = at + timedelta(minutes=job.duration_minutes or DEFAULT_MINUTES)
    if job.elder_id not in names:
        e = db.get(Elder, job.elder_id)
        names[job.elder_id] = _name(e.first_name, e.last_name) if e else ""
    return {
        "id": job.id,
        "elder_id": job.elder_id,
        "elder_name": names[job.elder_id],
        "title": job.title,
        "kind": job.kind,
        "status": job.status,
        "start": at.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "scheduled_at": at.isoformat(),
        "duration_minutes": job.duration_minutes or DEFAULT_MINUTES,
        "caregiver_id": job.caregiver_id,
        "series_id": job.series_id,
    }


def weekly_roster(db: Session, user: User, week_of: date | None = None, *, now: datetime | None = None) -> dict:
    """Rows are caregivers, columns Mon–Sun (IST); unassigned visits get their own row."""
    week_of = week_of or ist_today(now)
    monday = week_of - timedelta(days=week_of.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    start = datetime.combine(monday, time(0, 0), tzinfo=IST).astimezone(timezone.utc)
    end = start + timedelta(days=7)
    tid = resolve_tenant_id(user)

    cq = db.query(Caregiver)
    if tid is not None:
        cq = cq.filter(Caregiver.tenant_id == tid)
    team_cg = team_caregiver_ids(db, user)
    if team_cg is not None:
        cq = cq.filter(Caregiver.id.in_(team_cg or {-1}))
    caregivers = [c for c in cq.order_by(Caregiver.first_name, Caregiver.last_name).all()]

    jq = db.query(CareJob).filter(
        CareJob.scheduled_at >= start, CareJob.scheduled_at < end, CareJob.status != "cancelled"
    )
    if tid is not None:
        jq = jq.filter(CareJob.tenant_id == tid)
    team_el = team_elder_ids(db, user)
    if team_el is not None:
        jq = jq.filter(CareJob.elder_id.in_(team_el or {-1}))
    jobs = jq.order_by(CareJob.scheduled_at).all()

    cg_ids = [c.id for c in caregivers]
    leave = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.caregiver_id.in_(cg_ids or [-1]),
            LeaveRequest.status.in_(("APPROVED", "PENDING")),
            LeaveRequest.start_date <= days[-1],
            LeaveRequest.end_date >= monday,
        )
        .all()
    )
    names: dict[int, str] = {}
    by_cell: dict[tuple[int | None, date], list[dict]] = {}
    other_team: dict[int, Caregiver] = {}
    for j in jobs:
        d = _aware(j.scheduled_at).astimezone(IST).date()
        key = j.caregiver_id
        if key is not None and key not in cg_ids and key not in other_team:
            ocg = db.get(Caregiver, key)
            if ocg is not None:
                other_team[key] = ocg  # covered by a caregiver outside this manager's team
            else:
                key = None
        by_cell.setdefault((key, d), []).append(_chip(db, j, names))

    def row(cg: Caregiver | None, *, other: bool = False) -> dict:
        cid = cg.id if cg else None
        cells = []
        for d in days:
            lv = next(
                (l for l in leave if cg and l.caregiver_id == cg.id and l.start_date <= d <= l.end_date), None
            )
            visits = by_cell.get((cid, d), [])
            if lv is not None and lv.status == "APPROVED":
                # Booked on a day the caregiver is on approved leave: flag for cover.
                visits = [
                    {**v, "needs_cover": v["status"] in ("requested", "scheduled", "on_the_way")}
                    for v in visits
                ]
            cells.append(
                {
                    "date": d.isoformat(),
                    "visits": visits,
                    "leave": {"id": lv.id, "status": lv.status, "type": lv.leave_type} if lv else None,
                }
            )
        return {
            "caregiver_id": cid,
            "name": (
                (f"Other team: {_name(cg.first_name, cg.last_name)}" if other else _name(cg.first_name, cg.last_name))
                if cg
                else "Not assigned"
            ),
            "other_team": other,
            "active": (cg.status or "ACTIVE").upper() not in INACTIVE_CAREGIVER if cg else True,
            "days": cells,
        }

    rows = [row(c) for c in caregivers]
    rows = [r for r in rows if r["active"] or any(c["visits"] for c in r["days"])]
    rows += [row(c, other=True) for c in sorted(other_team.values(), key=lambda c: (c.first_name, c.last_name))]
    unassigned = row(None)
    return {
        "week_start": monday.isoformat(),
        "days": [{"date": d.isoformat(), "label": _date_label(d)} for d in days],
        "caregivers": rows,
        "unassigned": unassigned if any(c["visits"] for c in unassigned["days"]) else None,
    }
