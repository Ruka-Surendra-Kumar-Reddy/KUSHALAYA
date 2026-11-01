"""Where a visit was logged from: check-in / check-out point on the care job,
its distance from the client's home pin, and a staff alert when it is far away.

The caregiver app must send a location (caregiver-portal routes call
``require``). Ops staff may be at the office, so their location is optional and
a missing one is simply stored as no location (null).
"""

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.staff_alert import StaffAlert
from app.models.user import User

# A check-in / check-out farther than this from the home pin alerts the care manager
# and admins. The phone's reported accuracy is added on top (capped, so a very
# rough fix cannot hide a real mismatch).
AWAY_FROM_HOME_METERS = 300
MAX_ACCURACY_ALLOWANCE_METERS = 200

EVENTS = {"checkin": "Check-in", "checkout": "Check-out"}
_NEED = {
    "checkin": "Turn on location to check in. Allow location for this app in your phone settings, then try again.",
    "checkout": "Turn on location to finish the visit. Allow location for this app in your phone settings, then try again.",
}


def require(lat: float | None, lng: float | None, event: str) -> None:
    """Caregiver app: no location, no check-in / check-out."""
    if lat is None or lng is None:
        raise_bad_request(_NEED[event])


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6_371_000 * asin(min(1.0, sqrt(a)))


def distance_label(meters: float) -> str:
    return f"{int(round(meters / 10.0) * 10)} m" if meters < 1000 else f"{meters / 1000:.1f} km"


def is_away(distance_m: float, accuracy_m: float | None) -> bool:
    allowance = min(max(accuracy_m or 0.0, 0.0), MAX_ACCURACY_ALLOWANCE_METERS)
    return distance_m > AWAY_FROM_HOME_METERS + allowance


def _home(db: Session, elder_id: int) -> tuple[float, float] | None:
    from app.livewell.care_jobs import home_point

    pin = home_point(db, elder_id)
    return (pin["lat"], pin["lng"]) if pin else None


def record(
    db: Session,
    job: CareJob,
    event: str,
    lat: float | None,
    lng: float | None,
    accuracy: float | None = None,
) -> None:
    """Store the point on the job (null = no location) and alert staff if it is far from home.

    The caller commits.
    """
    if lat is None or lng is None:
        lat = lng = accuracy = None
    if event == "checkin":
        job.checkin_lat, job.checkin_lng, job.checkin_accuracy_m = lat, lng, accuracy
    else:
        job.checkout_lat, job.checkout_lng, job.checkout_accuracy_m = lat, lng, accuracy
    if lat is None:
        return
    home = _home(db, job.elder_id)
    if home is None:  # no pin: the point is kept, nothing to compare with
        return
    meters = haversine_m(lat, lng, *home)
    if not is_away(meters, accuracy):
        return
    elder = db.get(Elder, job.elder_id)
    if elder is not None:
        if job.id is None:
            db.flush()
        alert_away(db, elder, f"visit_loc:{job.id}:{event}", EVENTS[event], meters, job_id=job.id)


def _possessive(elder: Elder) -> str:
    g = (elder.gender or "").strip().lower()
    return "her" if g in ("f", "female", "woman") else "his" if g in ("m", "male", "man") else "their"


def recipients(db: Session, elder: Elder) -> list[User]:
    """The client's care manager and every active admin of the agency."""
    q = db.query(User).filter(User.tenant_id == elder.tenant_id, User.status == "ACTIVE")
    rows = q.filter(User.role == "TENANT_ADMIN").all()
    if elder.manager_user_id:
        rows += q.filter(User.id == elder.manager_user_id).all()
    return list({u.id: u for u in rows}.values())


def alert_away(
    db: Session, elder: Elder, key: str, what: str, meters: float, *, job_id: int | None = None
) -> int:
    """One closable ops notice per recipient (plus the staff email rule). Returns rows added.

    ``key`` names the job and event; each user's row is ``<key>:<user id>``, so a
    repeat call adds nothing (dedupe_key is unique across all rows).
    """
    from app.livewell.email_notifications import email_staff, staff_path

    name = f"{elder.first_name or ''} {elder.last_name or ''}".strip() or "the client"
    title = f"{what} away from home"
    body = f"{what} for {name} was {distance_label(meters)} from {_possessive(elder)} home."
    path = staff_path(elder, "timeline")
    users = recipients(db, elder)
    keys = {u.id: f"{key}:{u.id}"[:200] for u in users}
    taken = {
        k
        for (k,) in db.query(StaffAlert.dedupe_key).filter(StaffAlert.dedupe_key.in_(list(keys.values()) or ["-"]))
    }
    added = 0
    for u in users:
        if keys[u.id] in taken:
            continue
        db.add(
            StaffAlert(
                tenant_id=elder.tenant_id,
                user_id=u.id,
                elder_id=elder.id,
                job_id=job_id,
                kind="visit_location",
                title=title,
                body=body,
                path=path,
                dedupe_key=keys[u.id],
            )
        )
        added += 1
    if added:
        db.flush()
        email_staff(db, elder, "visit_location", f"{title} — {name}", body, path=path)
    return added


# --- staff view ----------------------------------------------------------------


def _point(lat, lng, acc, home) -> dict | None:
    if lat is None or lng is None:
        return None
    out = {"lat": lat, "lng": lng, "accuracy_m": acc, "distance_m": None, "away": None}
    if home is not None:
        meters = haversine_m(lat, lng, *home)
        out["distance_m"] = int(round(meters))
        out["away"] = is_away(meters, acc)
    return out


def view(db: Session, job: CareJob) -> dict:
    """Staff only (never the family): check-in / check-out points and distance from home."""
    home = _home(db, job.elder_id)
    return {
        "has_home_pin": home is not None,
        "checkin": _point(job.checkin_lat, job.checkin_lng, job.checkin_accuracy_m, home),
        "checkout": _point(job.checkout_lat, job.checkout_lng, job.checkout_accuracy_m, home),
    }


# --- open alerts for the signed-in staff user ------------------------------------


def list_open(db: Session, user: User, limit: int = 20) -> list[dict]:
    rows = (
        db.query(StaffAlert)
        .filter(StaffAlert.user_id == user.id, StaffAlert.dismissed_at.is_(None))
        .order_by(StaffAlert.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "title": r.title,
            "body": r.body,
            "path": r.path,
            "job_id": r.job_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def dismiss(db: Session, user: User, alert_id: int) -> dict:
    row = db.get(StaffAlert, alert_id)
    if row is None or row.user_id != user.id:
        raise_not_found("Alert not found")
    if row.dismissed_at is None:
        row.dismissed_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}
