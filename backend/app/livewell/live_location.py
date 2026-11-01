"""Live "on the way" location for a care visit (FIX_TODO item 115).

While a caregiver is on the way, the field app sends its position about every
30 s. Only the latest point per job is kept (care_job_live_locations), with its
time and accuracy; the row is deleted when the job leaves "on the way".

Who sees it:
- the caregiver (their own job only) — they send it;
- the family, for their own parent's job, only while it is on the way; after
  arrival they see "Arrived at 10:02" and no position;
- staff, for jobs of clients in their team (ops Schedule / Dashboard);
- anyone holding the tracking link sent to the family (/track/<token>): a signed,
  per-trip link that shows the position only while on the way, then "Arrived".

A care manager can share too, from the ops Visits page (browser location).

ETA is rough on purpose: straight-line distance at 25 km/h city speed.
"""

import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import CAREGIVER
from app.core.responses import raise_bad_request, raise_not_found
from app.models.care_job import CareJob
from app.models.care_job_live_location import CareJobLiveLocation
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User

IST = timezone(timedelta(hours=5, minutes=30))
CITY_KMH = 25.0
STALE_AFTER = timedelta(minutes=3)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def eta_minutes(km: float) -> int:
    """Whole minutes at city speed, at least 1."""
    return max(1, math.ceil(km / CITY_KMH * 60))


def eta_label(km: float) -> str:
    if km < 0.15:
        return "almost there"
    return f"about {eta_minutes(km)} min"


def home_coords(db: Session, elder: Elder | None) -> tuple[float, float] | None:
    """The client's home: the geofence point if set, else the geocoded address."""
    if not elder:
        return None
    from app.models.elder_location import ElderLocation

    home = db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first()
    if home:
        return float(home.latitude), float(home.longitude)
    attrs = elder.custom_attributes or {}
    try:
        lat, lng = attrs.get("latitude"), attrs.get("longitude")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    except (TypeError, ValueError):
        pass
    return None


def clear(db: Session, job_id: int) -> None:
    """Forget the caregiver's position for this job (no commit)."""
    db.query(CareJobLiveLocation).filter(CareJobLiveLocation.job_id == job_id).delete(
        synchronize_session=False
    )


def record(
    db: Session,
    user: User,
    job_id: int,
    *,
    lat: float,
    lng: float,
    accuracy: float | None = None,
    now: datetime | None = None,
) -> dict:
    """Save the caregiver's latest position. Only their own job, only while on the way.

    A checked-in job answers {"tracking": False} so the app stops sending.
    """
    from app.livewell.care_jobs import _caregiver_job

    job = _caregiver_job(db, user, job_id)  # 404 unless it is the caller's job
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        raise_bad_request("That location doesn't look right")
    if job.status == "checked_in":
        clear(db, job.id)
        db.commit()
        return {"tracking": False, "status": job.status}
    if job.status != "on_the_way":
        raise_bad_request("Location is only shared while you are on the way")
    now = now or datetime.now(timezone.utc)
    row = db.get(CareJobLiveLocation, job.id)
    if row is None:
        row = CareJobLiveLocation(job_id=job.id, tenant_id=job.tenant_id)
        db.add(row)
    row.caregiver_id = job.caregiver_id
    row.shared_by_user_id = None if user.role == CAREGIVER else user.id
    row.latitude, row.longitude = round(float(lat), 6), round(float(lng), 6)
    row.accuracy_m = round(float(accuracy), 1) if accuracy is not None else None
    row.updated_at = now
    db.commit()
    return {"tracking": True, "status": job.status, **(view(db, job, now=now) or {})}


def _arrived_label(dt: datetime | None) -> str:
    dt = _aware(dt)
    if not dt:
        return "Arrived"
    return "Arrived at " + dt.astimezone(IST).strftime("%I:%M %p").lstrip("0")


def view(db: Session, job: CareJob, *, now: datetime | None = None) -> dict | None:
    """Live block for a job that is on the way, or None. Never returns a position
    for any other status, or one sent before a reassignment."""
    if job.status != "on_the_way":
        return None
    now = now or datetime.now(timezone.utc)
    elder = db.get(Elder, job.elder_id)
    home = home_coords(db, elder)
    row = db.get(CareJobLiveLocation, job.id)
    token = track_token(job)
    out: dict = {
        "state": "on_the_way",
        "caregiver_first_name": _traveller_name(db, job, row),
        "track_path": f"/track/{token}" if token else None,
        "home": {"lat": home[0], "lng": home[1]} if home else None,
        "destination": job.location or ((elder.address if elder else "") or ""),
        "position": None,
        "updated_at": None,
        "stale": True,
        "distance_km": None,
        "eta_minutes": None,
        "eta_label": "",
    }
    if not row or row.caregiver_id != job.caregiver_id:
        return out
    updated = _aware(row.updated_at)
    out["position"] = {"lat": row.latitude, "lng": row.longitude, "accuracy_m": row.accuracy_m}
    out["updated_at"] = updated.isoformat() if updated else None
    out["stale"] = not updated or now - updated > STALE_AFTER
    if home:
        km = haversine_km(row.latitude, row.longitude, home[0], home[1])
        out["distance_km"] = round(km, 2)
        out["eta_minutes"] = 0 if km < 0.15 else eta_minutes(km)
        out["eta_label"] = eta_label(km)
    return out


def _traveller_name(db: Session, job: CareJob, row: CareJobLiveLocation | None = None) -> str:
    """Who is coming: the staff member sharing from the web, else the caregiver,
    else the care manager the visit is assigned to."""
    if row is not None and row.shared_by_user_id:
        u = db.get(User, row.shared_by_user_id)
        if u and u.first_name:
            return u.first_name
    if job.caregiver_id:
        cg = db.get(Caregiver, job.caregiver_id)
        if cg and cg.first_name:
            return cg.first_name
    if job.assignee_user_id:
        u = db.get(User, job.assignee_user_id)
        if u and u.first_name:
            return u.first_name
    return "Your caregiver"


# --- Tracking link (no login) ------------------------------------------------------
# One link per trip: signed over the job and the moment it went "on the way", so a
# new trip gets a new link and old links never show a later journey.
TRACK_ARRIVED_FOR = timedelta(hours=6)


def _track_sig(job_id: int, started_at: datetime) -> str:
    msg = f"track:{job_id}:{_aware(started_at).isoformat()}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:24]


def track_token(job: CareJob) -> str | None:
    if job.status != "on_the_way" or not job.started_at:
        return None
    return f"{job.id}-{_track_sig(job.id, job.started_at)}"


def public_track(db: Session, token: str, *, now: datetime | None = None) -> dict:
    """What the tracking link shows, only while on the way: who is coming, where they
    are, a rough ETA and the home point the map draws the route to. Never the address
    text, the client's name or anything else about them."""
    now = now or datetime.now(timezone.utc)
    job_part, _, sig = (token or "").partition("-")
    job = db.get(CareJob, int(job_part)) if job_part.isdigit() else None
    if not job or not job.started_at or not sig or not hmac.compare_digest(sig, _track_sig(job.id, job.started_at)):
        raise_not_found("This tracking link isn't valid")
    name = _traveller_name(db, job, db.get(CareJobLiveLocation, job.id))
    base = {"name": name, "title": job.title or "Care visit"}
    if job.status == "on_the_way":
        live = view(db, job, now=now) or {}
        return {
            **base,
            "state": "on_the_way",
            "name": live.get("caregiver_first_name") or name,
            "position": live.get("position"),
            "home": live.get("home"),
            "updated_at": live.get("updated_at"),
            "stale": live.get("stale", True),
            "eta_minutes": live.get("eta_minutes"),
            "eta_label": live.get("eta_label", ""),
        }
    arrived = _aware(job.checked_in_at)
    if job.status in ("checked_in", "completed") and arrived and now - arrived <= TRACK_ARRIVED_FOR:
        return {**base, "state": "arrived", "arrived_label": _arrived_label(arrived)}
    return {**base, "state": "ended"}


def family_live(db: Session, user: User, *, now: datetime | None = None) -> dict:
    """The family's live visit card: their own parent's job that is on the way,
    or one that arrived in the last 3 hours ("Arrived at 10:02", no map)."""
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    now = now or datetime.now(timezone.utc)
    moving = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder.id, CareJob.status == "on_the_way")
        .order_by(CareJob.started_at.desc().nullslast(), CareJob.id.desc())
        .first()
    )
    if moving:
        live = view(db, moving, now=now) or {}
        return {"live": {**live, "job_id": moving.id, "title": moving.title or "Care visit"}}
    arrived = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id == elder.id,
            CareJob.status == "checked_in",
            CareJob.checked_in_at >= now - timedelta(hours=3),
        )
        .order_by(CareJob.checked_in_at.desc())
        .first()
    )
    if arrived:
        cg = db.get(Caregiver, arrived.caregiver_id) if arrived.caregiver_id else None
        return {
            "live": {
                "state": "arrived",
                "job_id": arrived.id,
                "title": arrived.title or "Care visit",
                "caregiver_first_name": (cg.first_name if cg else "") or "Your caregiver",
                "arrived_at": _aware(arrived.checked_in_at).isoformat(),
                "arrived_label": _arrived_label(arrived.checked_in_at),
            }
        }
    return {"live": None}
