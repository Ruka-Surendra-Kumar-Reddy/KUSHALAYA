"""Safe Home visits — stored on elder custom_attributes.safe_home.visits (not caregiver attendance)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.care_stability import (
    BASELINE_VISIT_TYPE,
    baseline_minimum_ok,
    build_visit_summary_from_checkin,
    checkin_for_baseline_visit,
    compute_care_status,
    compute_stability_score,
    family_status_report,
    get_baseline,
    is_baseline_established,
    normalize_checkin,
    publish_wellness_from_visit,
    save_care_status,
    set_baseline,
)
from app.livewell.family_care_hub import open_sos_incident_count
from app.models.elder import Elder
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

VISIT_TYPES = (
    "Baseline profile",
    "Home safety assessment",
    "Wellness visit",
    "Wellness check-in",
    "Modification follow-up",
    "Product installation",
    "Other",
)


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _new_visit_id() -> str:
    return f"hsv_{uuid.uuid4().hex[:12]}"


def _normalize_location(raw) -> dict | None:
    """Where the visit was logged from (browser geolocation on the staff device)."""
    if not isinstance(raw, dict):
        return None
    try:
        lat = float(raw.get("lat"))
        lng = float(raw.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    out: dict = {"lat": round(lat, 6), "lng": round(lng, 6)}
    try:
        if raw.get("accuracy_m") is not None:
            out["accuracy_m"] = max(0, int(float(raw.get("accuracy_m"))))
    except (TypeError, ValueError):
        pass
    captured = _parse_dt(raw.get("captured_at"))
    out["captured_at"] = (captured or datetime.now(timezone.utc)).isoformat()
    for key in ("distance_from_home_m", "home_radius_m"):
        try:
            if raw.get(key) is not None:
                out[key] = int(float(raw.get(key)))
        except (TypeError, ValueError):
            pass
    if raw.get("at_home") is not None:
        out["at_home"] = bool(raw.get("at_home"))
    return out


def _normalize_staff_feedback(raw) -> dict | None:
    """Care manager feedback about the visit and household. Staff-only, never sent to families."""
    if not isinstance(raw, dict):
        return None
    try:
        rating = max(1, min(5, int(raw.get("rating"))))
    except (TypeError, ValueError):
        return None
    at = _parse_dt(raw.get("at"))
    return {
        "rating": rating,
        "comment": str(raw.get("comment") or "").strip()[:1000],
        "by_name": str(raw.get("by_name") or "").strip()[:200],
        "by_user_id": raw.get("by_user_id"),
        "at": (at or datetime.now(timezone.utc)).isoformat(),
    }


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return int(round(2 * 6371000 * asin(sqrt(a))))


def _stamp_distance_from_home(db: Session, elder: Elder, location: dict | None) -> dict | None:
    """Compare the captured point with the registered home of the client, when one is set."""
    if not location:
        return location
    from app.models.elder_location import ElderLocation

    home = db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first()
    if not home:
        return location
    out = dict(location)
    distance = _haversine_m(out["lat"], out["lng"], float(home.latitude), float(home.longitude))
    radius = int(home.radius_meters or 100)
    out["distance_from_home_m"] = distance
    out["home_radius_m"] = radius
    # Allow for GPS error: a phone indoors is often 30-50 m off.
    out["at_home"] = distance <= radius + int(out.get("accuracy_m") or 0)
    return out


def normalize_visit(raw: dict) -> dict:
    concerns = raw.get("concerns") or []
    if isinstance(concerns, str):
        concerns = [c.strip() for c in concerns.split("\n") if c.strip()]
    else:
        concerns = [str(c).strip() for c in concerns if str(c).strip()]

    photo_ids: list[int] = []
    for pid in raw.get("photo_ids") or []:
        try:
            photo_ids.append(int(pid))
        except (TypeError, ValueError):
            pass

    duration = raw.get("duration_minutes")
    try:
        duration_minutes = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_minutes = None

    visit_type = str(raw.get("visit_type", "Wellness visit")).strip()
    if visit_type not in VISIT_TYPES:
        visit_type = "Other"

    visited_at = _parse_dt(raw.get("visited_at")) or datetime.now(timezone.utc)

    experience_rating = raw.get("experience_rating")
    try:
        experience_rating = int(experience_rating) if experience_rating is not None else None
        if experience_rating is not None:
            experience_rating = max(1, min(5, experience_rating))
    except (TypeError, ValueError):
        experience_rating = None

    rated_at = _parse_dt(raw.get("rated_at"))
    checkin = normalize_checkin(raw.get("checkin"))
    family_message = str(raw.get("family_message") or "").strip()[:2000]
    if not family_message and checkin:
        family_message = str(
            checkin.get("family_message") or checkin.get("care_manager_note") or ""
        ).strip()[:2000]
    if checkin and family_message:
        checkin = dict(checkin)
        checkin["family_message"] = family_message
        if not checkin.get("care_manager_note"):
            checkin["care_manager_note"] = family_message

    stability = raw.get("stability_score")
    try:
        stability_score = int(stability) if stability is not None else None
        if stability_score is not None:
            stability_score = max(0, min(100, stability_score))
    except (TypeError, ValueError):
        stability_score = None
    stability_meta = raw.get("stability") if isinstance(raw.get("stability"), dict) else None

    return {
        "id": str(raw.get("id") or _new_visit_id()),
        "visit_type": visit_type,
        "visited_at": visited_at.isoformat(),
        "staff_name": str(raw.get("staff_name", "")).strip(),
        "partner_id": str(raw.get("partner_id", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "wellness_notes": str(raw.get("wellness_notes", "")).strip(),
        "family_message": family_message,
        "concerns": concerns,
        "recommendations": str(raw.get("recommendations", "")).strip(),
        "photo_ids": photo_ids,
        "duration_minutes": duration_minutes,
        "status": str(raw.get("status", "completed")).strip() or "completed",
        "experience_rating": experience_rating,
        "experience_comment": str(raw.get("experience_comment", "")).strip(),
        "rated_at": rated_at.isoformat() if rated_at else None,
        "created_at": (_parse_dt(raw.get("created_at")) or datetime.now(timezone.utc)).isoformat(),
        "checkin": checkin,
        "stability_score": stability_score,
        "stability": stability_meta,
        "location": _normalize_location(raw.get("location")),
        "staff_feedback": _normalize_staff_feedback(raw.get("staff_feedback")),
    }


def _safe_home_block(elder: Elder) -> dict:
    attrs = elder.custom_attributes or {}
    block = attrs.get("safe_home")
    if not isinstance(block, dict):
        block = {}
    return block


def _visits_raw(elder: Elder) -> list[dict]:
    block = _safe_home_block(elder)
    rows = block.get("visits")
    if not isinstance(rows, list):
        return []
    return rows


def _save_visits(db: Session, elder: Elder, visits: list[dict]) -> None:
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {})
    block["visits"] = visits
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    db.refresh(elder)


def _partner_name_map(db: Session, tenant_id: int) -> dict[str, str]:
    from app.livewell.config_keys import SUPPLIERS_KEY
    from app.models.tenant import Tenant

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return {}
    stored = (tenant.workflow_config or {}).get(SUPPLIERS_KEY) or {}
    return {
        str(s.get("id")): str(s.get("name") or "")
        for s in (stored.get("suppliers") or [])
        if isinstance(s, dict) and s.get("id")
    }


def visit_to_family_response(
    visit: dict,
    *,
    tenant_id: int,
    partner_names: dict[str, str] | None = None,
    staff: bool = False,
) -> dict:
    """Shape a stored visit for the API. staff=True adds what families must not
    see (the care manager feedback about the household) and staff photo URLs."""
    photo_base = "/api/v1/home-safety/photos" if staff else "/api/v1/home-safety/family/photos"
    photo_urls = [
        f"{photo_base}/{pid}/image"
        for pid in visit.get("photo_ids") or []
    ]
    partner_id = visit.get("partner_id") or None
    names = partner_names or {}
    rated = visit.get("experience_rating") is not None
    status = visit.get("status", "completed")
    return {
        "id": visit["id"],
        "visit_type": visit["visit_type"],
        "visited_at": _parse_dt(visit["visited_at"]) or datetime.now(timezone.utc),
        "staff_name": visit.get("staff_name") or None,
        "partner_id": partner_id or None,
        "partner_name": names.get(partner_id) if partner_id else None,
        "summary": visit.get("summary", ""),
        "wellness_notes": visit.get("wellness_notes", ""),
        "family_message": visit.get("family_message") or None,
        "concerns": list(visit.get("concerns") or []),
        "recommendations": visit.get("recommendations", ""),
        "photo_ids": list(visit.get("photo_ids") or []),
        "photo_urls": photo_urls,
        "duration_minutes": visit.get("duration_minutes"),
        "status": status,
        "experience_rating": visit.get("experience_rating"),
        "experience_comment": visit.get("experience_comment") or None,
        "rated_at": _parse_dt(visit.get("rated_at")),
        "can_rate": (not rated) and status == "completed",
        "checkin": visit.get("checkin"),
        "stability_score": visit.get("stability_score"),
        "stability": visit.get("stability"),
        "location": visit.get("location") if staff else None,
        "staff_feedback": visit.get("staff_feedback") if staff else None,
    }


class HomeSafetyVisitService:

    @staticmethod
    def _elder_for_staff(db: Session, user: User, elder_id: int) -> Elder:
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        tid = resolve_tenant_id(user)
        if tid is not None and elder.tenant_id != tid:
            raise_not_found("Elder not found")
        return elder

    @staticmethod
    def list_for_elder(db: Session, user: User, elder_id: int, *, days: int = 90) -> list[dict]:
        elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
        return HomeSafetyVisitService._list_visits(db, elder, days=days, staff=True)

    @staticmethod
    def create_for_elder(db: Session, user: User, elder_id: int, payload: dict) -> dict:
        elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
        attrs = dict(elder.custom_attributes or {})
        block = dict(attrs.get("safe_home") or {})
        needs_baseline = not is_baseline_established(block.get("care_baseline"))

        visit = normalize_visit(payload)
        # Feedback is added afterwards by a named staff member, never at creation.
        visit["staff_feedback"] = None
        visit["location"] = _stamp_distance_from_home(db, elder, visit.get("location"))
        baseline_payload = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else None

        # First completed visit establishes the personal baseline profile.
        if visit.get("status") == "completed" and needs_baseline:
            if not baseline_minimum_ok(baseline_payload):
                raise_bad_request(
                    "First visit must capture a baseline profile "
                    "(typical mobility, wake time, or baseline notes)."
                )
            visit["visit_type"] = BASELINE_VISIT_TYPE
            if not visit.get("checkin"):
                visit["checkin"] = checkin_for_baseline_visit()
            else:
                ci = dict(visit["checkin"])
                ci["mobility_vs_normal"] = "same"
                ci["mood_vs_normal"] = "same"
                ci["eating_vs_normal"] = "same"
                if ci.get("mobility") in ("slight_decline", "significant_decline"):
                    ci["mobility"] = "normal_for_them"
                visit["checkin"] = normalize_checkin(ci)
            if not visit["summary"]:
                visit["summary"] = (
                    "Baseline profile visit — established this person's normal pattern."
                )
            note = (baseline_payload or {}).get("notes") or ""
            if note and not visit["wellness_notes"]:
                visit["wellness_notes"] = str(note).strip()[:2000]

        checkin = visit.get("checkin")
        if checkin and not visit["summary"]:
            visit["summary"] = build_visit_summary_from_checkin(checkin, visit.get("summary") or "")
        if checkin and checkin.get("care_manager_note") and not visit["wellness_notes"]:
            visit["wellness_notes"] = checkin["care_manager_note"]
        if not visit.get("family_message"):
            visit["family_message"] = (
                (checkin.get("family_message") if checkin else "")
                or (checkin.get("care_manager_note") if checkin else "")
                or ""
            )
        if visit.get("family_message") and checkin:
            checkin = dict(checkin)
            checkin["family_message"] = visit["family_message"]
            if not checkin.get("care_manager_note"):
                checkin["care_manager_note"] = visit["family_message"]
            visit["checkin"] = checkin
        if visit.get("family_message") and not visit["wellness_notes"]:
            visit["wellness_notes"] = visit["family_message"]
        if (
            not visit["summary"]
            and not visit["wellness_notes"]
            and not checkin
            and not baseline_payload
        ):
            raise_bad_request(
                "Summary, wellness notes, structured check-in, or baseline required"
            )

        # Centered stability score: 50 on baseline visit; later visits can rise or fall.
        baseline_just_set = bool(
            visit.get("status") == "completed" and needs_baseline and baseline_payload
        )
        if visit.get("status") == "completed" and (checkin or baseline_just_set):
            stability = compute_stability_score(
                checkin,
                is_baseline_visit=baseline_just_set
                or visit.get("visit_type") == BASELINE_VISIT_TYPE,
            )
            visit["stability"] = stability
            visit["stability_score"] = stability.get("score")

        visits = [normalize_visit(v) for v in _visits_raw(elder)]
        visits.append(visit)
        visits.sort(key=lambda v: v["visited_at"], reverse=True)
        block["visits"] = visits

        if visit.get("status") == "completed" and needs_baseline and baseline_payload:
            set_baseline(block, baseline_payload, source_visit_id=visit["id"])

        if visit.get("status") == "completed" and visit.get("stability_score") is not None:
            history = list(block.get("stability_score_history") or [])
            if not isinstance(history, list):
                history = []
            history.insert(
                0,
                {
                    "visit_id": visit["id"],
                    "visited_at": visit["visited_at"],
                    "score": visit["stability_score"],
                    "delta_from_baseline": (visit.get("stability") or {}).get("delta_from_baseline"),
                    "band": (visit.get("stability") or {}).get("band"),
                },
            )
            block["stability_score_history"] = history[:60]

        if visit.get("status") == "completed" and checkin:
            publish_wellness_from_visit(block, visit)

        open_reqs = 0
        for req in block.get("service_requests") or []:
            if isinstance(req, dict) and str(req.get("status") or "") in (
                "requested",
                "confirmed",
            ):
                open_reqs += 1
        hub = block.get("family_hub") if isinstance(block.get("family_hub"), dict) else {}
        incidents = hub.get("incidents") if isinstance(hub.get("incidents"), list) else []
        open_incidents = open_sos_incident_count(incidents)
        from app.livewell.care_stability import get_baseline as _get_baseline

        status = compute_care_status(
            visits=visits,
            open_service_requests=open_reqs,
            open_incidents=open_incidents,
            baseline=_get_baseline(block),
        )
        save_care_status(block, status)

        attrs["safe_home"] = block
        elder.custom_attributes = attrs
        flag_modified(elder, "custom_attributes")
        loc = visit.get("location") or {}
        if loc.get("distance_from_home_m") is not None:
            from app.livewell.visit_location import alert_away, is_away

            if is_away(loc["distance_from_home_m"], loc.get("accuracy_m")):
                alert_away(db, elder, f"visit_loc:hsv:{visit['id']}", "Visit", loc["distance_from_home_m"])
        db.commit()
        db.refresh(elder)

        names = _partner_name_map(db, elder.tenant_id)
        return visit_to_family_response(
            visit, tenant_id=elder.tenant_id, partner_names=names, staff=True
        )

    @staticmethod
    def _list_visits(db: Session, elder: Elder, *, days: int, staff: bool = False) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        names = _partner_name_map(db, elder.tenant_id)
        out = []
        for raw in _visits_raw(elder):
            visit = normalize_visit(raw)
            visited = _parse_dt(visit["visited_at"])
            if visited and visited < cutoff:
                continue
            out.append(
                visit_to_family_response(
                    visit, tenant_id=elder.tenant_id, partner_names=names, staff=staff
                )
            )
        out.sort(key=lambda v: v["visited_at"], reverse=True)
        return out

    @staticmethod
    def _update_visit(db: Session, user: User, elder_id: int, visit_id: str, mutate) -> dict:
        elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
        visits = [normalize_visit(v) for v in _visits_raw(elder)]
        found = next((v for v in visits if v["id"] == visit_id), None)
        if not found:
            raise_not_found("Visit not found")
        mutate(found, elder)
        _save_visits(db, elder, visits)
        names = _partner_name_map(db, elder.tenant_id)
        return visit_to_family_response(
            found, tenant_id=elder.tenant_id, partner_names=names, staff=True
        )

    @staticmethod
    def add_staff_feedback(
        db: Session, user: User, elder_id: int, visit_id: str, *, rating: int, comment: str = ""
    ) -> dict:
        """Care manager feedback on a completed visit (how the visit and the household went)."""

        def mutate(visit: dict, _elder: Elder) -> None:
            if visit.get("status") != "completed":
                raise_bad_request("Only completed visits can get feedback")
            parts = (getattr(user, "first_name", ""), getattr(user, "last_name", ""))
            name = " ".join(part for part in parts if part).strip() or user.email
            visit["staff_feedback"] = _normalize_staff_feedback(
                {"rating": rating, "comment": comment, "by_name": name, "by_user_id": user.id}
            )

        return HomeSafetyVisitService._update_visit(db, user, elder_id, visit_id, mutate)

    @staticmethod
    def attach_photos(
        db: Session, user: User, elder_id: int, visit_id: str, photo_ids: list[int]
    ) -> dict:
        """Add already-uploaded photos (POST /home-safety/photos with elder_id) to a visit."""
        from app.models.document import Document

        def mutate(visit: dict, elder: Elder) -> None:
            wanted = [int(p) for p in photo_ids][:30]
            if not wanted:
                raise_bad_request("No photos given")
            owned = {
                d.id
                for d in db.query(Document)
                .filter(
                    Document.id.in_(wanted),
                    Document.tenant_id == elder.tenant_id,
                    Document.entity_type == "elder",
                    Document.entity_id == elder.id,
                )
                .all()
            }
            if len(owned) != len(set(wanted)):
                raise_bad_request("A photo does not belong to this client")
            merged = list(visit.get("photo_ids") or [])
            for pid in wanted:
                if pid not in merged:
                    merged.append(pid)
            visit["photo_ids"] = merged[:40]

        return HomeSafetyVisitService._update_visit(db, user, elder_id, visit_id, mutate)

    @staticmethod
    def list_for_family(db: Session, user: User, *, days: int = 60) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        visits = HomeSafetyVisitService._list_visits(db, elder, days=days)
        if visits:
            return visits
        return HomeSafetyVisitService._demo_visits(db, elder)

    @staticmethod
    def list_upcoming_for_family(db: Session, user: User, *, limit: int = 20) -> list[dict]:
        """Visits scheduled for the future (or status scheduled/planned)."""
        elder = ElderPortalService.get_linked_elder(db, user)
        names = _partner_name_map(db, elder.tenant_id)
        now = datetime.now(timezone.utc)
        out = []
        for raw in _visits_raw(elder):
            visit = normalize_visit(raw)
            status = str(visit.get("status") or "").lower()
            visited = _parse_dt(visit["visited_at"])
            is_upcoming = status in ("scheduled", "planned", "upcoming") or (
                visited is not None and visited >= now and status != "cancelled"
            )
            if not is_upcoming:
                continue
            out.append(
                visit_to_family_response(visit, tenant_id=elder.tenant_id, partner_names=names)
            )
        out.sort(key=lambda v: v["visited_at"])
        return out[:limit]

    @staticmethod
    def get_for_family(db: Session, user: User, visit_id: str) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        names = _partner_name_map(db, elder.tenant_id)
        for raw in _visits_raw(elder):
            visit = normalize_visit(raw)
            if visit["id"] == visit_id:
                return visit_to_family_response(
                    visit, tenant_id=elder.tenant_id, partner_names=names
                )
        for demo in HomeSafetyVisitService._demo_visits_raw(elder):
            if demo["id"] == visit_id:
                return visit_to_family_response(
                    demo, tenant_id=elder.tenant_id, partner_names=names
                )
        raise_not_found("Visit not found")

    @staticmethod
    def rate_experience_for_family(
        db: Session,
        user: User,
        visit_id: str,
        *,
        rating: int,
        comment: str = "",
    ) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        if visit_id.startswith("hsv-demo-"):
            raise_bad_request("Demo visits cannot be rated")
        rating = max(1, min(5, int(rating)))
        visits = [normalize_visit(v) for v in _visits_raw(elder)]
        found = None
        for visit in visits:
            if visit["id"] == visit_id:
                found = visit
                break
        if not found:
            raise_not_found("Visit not found")
        if found.get("experience_rating") is not None:
            raise_bad_request("This visit has already been rated")
        if found.get("status") != "completed":
            raise_bad_request("Only completed visits can be rated")

        found["experience_rating"] = rating
        found["experience_comment"] = str(comment or "").strip()[:1000]
        found["rated_at"] = datetime.now(timezone.utc).isoformat()
        _save_visits(db, elder, visits)

        partner_id = found.get("partner_id") or ""
        if partner_id:
            from app.livewell.partner_rating_service import recompute_partner_rolling_rating

            recompute_partner_rolling_rating(db, elder.tenant_id, partner_id)

        names = _partner_name_map(db, elder.tenant_id)
        return visit_to_family_response(found, tenant_id=elder.tenant_id, partner_names=names)

    @staticmethod
    def last_visit_at(elder: Elder) -> datetime | None:
        visits = _visits_raw(elder)
        if visits:
            parsed = [_parse_dt(normalize_visit(v)["visited_at"]) for v in visits]
            parsed = [p for p in parsed if p]
            if parsed:
                return max(parsed)
        demos = HomeSafetyVisitService._demo_visits_raw(elder)
        if demos:
            return _parse_dt(demos[0]["visited_at"])
        return None

    @staticmethod
    def visit_count(elder: Elder) -> int:
        if _visits_raw(elder):
            return len(_visits_raw(elder))
        return len(HomeSafetyVisitService._demo_visits_raw(elder))

    @staticmethod
    def care_status_for_elder(db: Session, elder: Elder, *, persist: bool = False) -> dict:
        from app.livewell.care_stability import get_baseline

        block = _safe_home_block(elder)
        visits = [normalize_visit(v) for v in _visits_raw(elder)]
        open_reqs = 0
        for req in block.get("service_requests") or []:
            if isinstance(req, dict) and str(req.get("status") or "") in (
                "requested",
                "confirmed",
            ):
                open_reqs += 1
        hub = block.get("family_hub") if isinstance(block.get("family_hub"), dict) else {}
        incidents = hub.get("incidents") if isinstance(hub.get("incidents"), list) else []
        open_incidents = open_sos_incident_count(incidents)
        # Completed care jobs (KushLife visits) are confirmed contact too.
        last_contact = None
        try:
            from sqlalchemy import func

            from app.models.care_job import CareJob

            last_contact = (
                db.query(func.max(CareJob.completed_at))
                .filter(CareJob.elder_id == elder.id, CareJob.status == "completed")
                .scalar()
            )
        except Exception:  # noqa: BLE001 - status must still compute
            last_contact = None
        status = compute_care_status(
            visits=visits,
            open_service_requests=open_reqs,
            open_incidents=open_incidents,
            baseline=get_baseline(block),
            last_contact_at=last_contact,
        )
        report = family_status_report(
            status,
            senior_name=f"{elder.first_name} {elder.last_name}".strip(),
        )
        report["baseline"] = get_baseline(block)
        if persist:
            attrs = dict(elder.custom_attributes or {})
            block = dict(attrs.get("safe_home") or {})
            save_care_status(block, status)
            attrs["safe_home"] = block
            elder.custom_attributes = attrs
            flag_modified(elder, "custom_attributes")
            db.commit()
        # Parse confirmed_at for API
        confirmed = _parse_dt(report.get("confirmed_at"))
        computed = _parse_dt(report.get("computed_at"))
        report["confirmed_at"] = confirmed
        report["computed_at"] = computed
        return report

    @staticmethod
    def get_baseline_for_elder(db: Session, user: User, elder_id: int) -> dict:
        from app.livewell.care_stability import get_baseline

        elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
        base = get_baseline(_safe_home_block(elder))
        updated = _parse_dt(base.get("updated_at"))
        return {**base, "updated_at": updated}

    @staticmethod
    def put_baseline_for_elder(db: Session, user: User, elder_id: int, payload: dict) -> dict:
        from app.livewell.care_stability import get_baseline, set_baseline

        elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
        attrs = dict(elder.custom_attributes or {})
        block = dict(attrs.get("safe_home") or {})
        set_baseline(block, payload)
        attrs["safe_home"] = block
        elder.custom_attributes = attrs
        flag_modified(elder, "custom_attributes")
        db.commit()
        db.refresh(elder)
        base = get_baseline(block)
        return {**base, "updated_at": _parse_dt(base.get("updated_at"))}

    @staticmethod
    def _demo_visits_raw(elder: Elder) -> list[dict]:
        name = f"{elder.first_name} {elder.last_name}".strip()
        now = datetime.now(timezone.utc)
        return [
            normalize_visit(
                {
                    "id": "hsv-demo-1",
                    "visit_type": "Wellness visit",
                    "visited_at": (now - timedelta(days=7)).isoformat(),
                    "staff_name": "Safe Home nurse",
                    "summary": f"Routine wellness visit for {name}. Vitals stable.",
                    "wellness_notes": "Hydration good. BP 128/82. Mobility independent with walker.",
                    "concerns": ["Mild stiffness in mornings"],
                    "recommendations": "Continue gentle stretching before breakfast.",
                    "duration_minutes": 45,
                    "status": "completed",
                }
            ),
            normalize_visit(
                {
                    "id": "hsv-demo-2",
                    "visit_type": "Home safety assessment",
                    "visited_at": (now - timedelta(days=28)).isoformat(),
                    "staff_name": "Safe Home assessor",
                    "summary": "Initial 100-point home safety assessment completed.",
                    "wellness_notes": "Family present during walkthrough.",
                    "concerns": ["Bathroom grab bars needed", "Hallway lighting dim at night"],
                    "recommendations": "Install grab bars and motion night lights (see catalog).",
                    "duration_minutes": 90,
                    "status": "completed",
                }
            ),
        ]

    @staticmethod
    def _demo_visits(db: Session, elder: Elder) -> list[dict]:
        names = _partner_name_map(db, elder.tenant_id)
        return [
            visit_to_family_response(v, tenant_id=elder.tenant_id, partner_names=names)
            for v in HomeSafetyVisitService._demo_visits_raw(elder)
        ]
