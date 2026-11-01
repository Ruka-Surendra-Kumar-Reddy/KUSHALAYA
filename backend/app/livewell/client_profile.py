"""Everything staff need about one client, in one read (ops client profile page).

Composes existing services rather than storing anything new: personal record,
family circle, visits, wallet + receipts, service requests, incidents, devices,
documents and the family message thread.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.family_devices import devices_for_elder
from app.livewell.family_receipts import FamilyReceiptService, _service_requests
from app.livewell.visit_service import HomeSafetyVisitService
from app.livewell.wallet_service import WalletService
from app.models.document import Document
from app.models.family_wallet import WalletTransaction
from app.models.incident import Incident
from app.models.tenant import Tenant
from app.models.user import User


def _iso(value) -> str | None:
    """Naive datetimes are stored as UTC; say so, or browsers read them as local time."""
    from datetime import datetime, timezone

    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat() if value is not None else None


def _short_name(u) -> str:
    """'Priya R.' for the header line."""
    if not u:
        return ""
    last = (u.last_name or "").strip()
    return f"{(u.first_name or '').strip()} {last[:1] + '.' if last else ''}".strip()


def _person(elder) -> dict:
    return {
        "id": elder.id,
        "first_name": elder.first_name,
        "last_name": elder.last_name,
        "date_of_birth": _iso(elder.date_of_birth),
        "gender": elder.gender,
        "phone": elder.phone,
        "address": elder.address,
        "emergency_contact_name": elder.emergency_contact_name,
        "emergency_contact_phone": elder.emergency_contact_phone,
        "medical_conditions": elder.medical_conditions,
        "allergies": elder.allergies,
        "mobility_status": elder.mobility_status,
        "care_level": elder.care_level,
        "status": elder.status,
        "created_at": _iso(elder.created_at),
    }


def _home_location(db: Session, elder) -> dict | None:
    from app.models.elder_location import ElderLocation

    home = db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first()
    if not home:
        return None
    return {
        "lat": float(home.latitude),
        "lng": float(home.longitude),
        "radius_m": int(home.radius_meters or 100),
    }


def _address_point(elder) -> dict | None:
    """Where the saved address geocoded to when the client was saved (no new lookup here)."""
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    try:
        lat, lng = float(attrs["latitude"]), float(attrs["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"lat": lat, "lng": lng}


def set_home_location(
    db: Session, user: User, elder_id: int, *, lat: float, lng: float, radius_m: int = 100
) -> dict:
    """Save where the client lives. Visits logged afterwards are checked against it."""
    from app.models.elder_location import ElderLocation

    elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
    home = db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first()
    if home is None:
        home = ElderLocation(tenant_id=elder.tenant_id, elder_id=elder.id)
        db.add(home)
    home.latitude = round(float(lat), 6)
    home.longitude = round(float(lng), 6)
    home.radius_meters = float(max(30, min(1000, int(radius_m))))
    db.commit()
    return _home_location(db, elder)


def build_client_profile(db: Session, user: User, elder_id: int) -> dict:
    # Tenant check lives in one place: the visit service's staff lookup.
    elder = HomeSafetyVisitService._elder_for_staff(db, user, elder_id)
    block = dict((elder.custom_attributes or {}).get("safe_home") or {})

    from app.livewell.family_contacts import list_contacts

    # Logins + circle contacts without a login, each with phone / channel / timezone / level (K2 #88).
    family = [{**c, "id": c["user_id"]} for c in list_contacts(db, elder) if c["has_login"]]

    visits = HomeSafetyVisitService._list_visits(db, elder, days=730, staff=True)
    rated = [v["experience_rating"] for v in visits if v.get("experience_rating")]
    staff_rated = [v["staff_feedback"]["rating"] for v in visits if v.get("staff_feedback")]

    wallet = WalletService.get_or_create(db, elder)
    tenant = db.query(Tenant).filter(Tenant.id == elder.tenant_id).first()
    requests = _service_requests(elder)
    entries = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(100)
        .all()
    )
    payer_ids = {e.created_by_user_id for e in entries if e.created_by_user_id}
    payers = (
        {u.id: u for u in db.query(User).filter(User.id.in_(list(payer_ids))).all()}
        if payer_ids
        else {}
    )
    receipts = [
        FamilyReceiptService._serialize(
            e, elder=elder, tenant=tenant, requests=requests, payer=payers.get(e.created_by_user_id)
        )
        for e in entries
    ]

    incidents = (
        db.query(Incident)
        .filter(Incident.tenant_id == elder.tenant_id, Incident.elder_id == elder.id)
        .order_by(Incident.opened_at.desc())
        .limit(30)
        .all()
    )
    documents = (
        db.query(Document)
        .filter(
            Document.tenant_id == elder.tenant_id,
            Document.entity_type == "elder",
            Document.entity_id == elder.id,
        )
        .order_by(Document.uploaded_at.desc())
        .limit(60)
        .all()
    )
    messages = FamilyCareHubService.list_messages_for_staff(elder)

    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    assessments = [
        {
            "id": r.assessment_id,
            "status": r.status,
            "score": (r.payload or {}).get("independenceScore"),
            "assessor": (r.payload or {}).get("assessorName") or "",
            "completed_at": _iso(r.completed_at) if getattr(r, "completed_at", None) else None,
            "updated_at": _iso(r.updated_at),
        }
        for r in db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder.id)
        .order_by(HomeSafetyAssessmentRecord.updated_at.desc())
        .all()
    ]

    return {
        "person": _person(elder),
        "manager_user_id": elder.manager_user_id,
        "manager_name": _short_name(db.get(User, elder.manager_user_id)) if elder.manager_user_id else "",
        "reassessment": _reassessment(db, elder),
        "assessments": assessments,
        "home_location": _home_location(db, elder),
        "address_point": _address_point(elder),
        "safety_score": block.get("safety_score"),
        "score_band": _latest_band(db, elder),
        "care_pathway": block.get("care_pathway"),
        "care_status": HomeSafetyVisitService.care_status_for_elder(db, elder),
        "family": family,
        "visits": visits,
        "feedback": {
            "family_average": round(sum(rated) / len(rated), 1) if rated else None,
            "family_count": len(rated),
            "staff_average": round(sum(staff_rated) / len(staff_rated), 1) if staff_rated else None,
            "staff_count": len(staff_rated),
        },
        "wallet": {
            "balance_minor": wallet.balance_minor,
            "currency": wallet.currency,
            "status": wallet.status,
        },
        "receipts": receipts,
        "service_requests": sorted(
            requests.values(), key=lambda r: str(r.get("created_at") or ""), reverse=True
        ),
        "incidents": [
            {
                "id": i.id,
                "kind": i.kind,
                "severity": i.severity,
                "status": i.status,
                "opened_at": _iso(i.opened_at),
                "resolved_at": _iso(i.resolved_at),
                "outcome": i.outcome,
                "note": i.note,
            }
            for i in incidents
        ],
        "devices": devices_for_elder(db, elder),
        "documents": [
            {
                "id": d.id,
                "document_type": d.document_type,
                "name": d.document_name or d.file_name,
                "mime_type": d.mime_type,
                "uploaded_at": _iso(d.uploaded_at),
                "is_photo": (d.mime_type or "").startswith("image/"),
            }
            for d in documents
        ],
        "messages": {"count": len(messages), "latest": messages[-3:]},
    }


def _reassessment(db, elder):
    from app.livewell.reassessment import due_info

    return due_info(db, elder)


def _risk_rules(tenant) -> list | None:
    """The tenant's own risk bands (Settings → rule engine), as assessment_service uses them."""
    from app.livewell.stored_config import read_stored_config

    cfg = read_stored_config((tenant.workflow_config if tenant else None) or {}).get("rule_engine") or {}
    return cfg.get("risk_rules") or None


def _band(score: int | None, payload: dict, rules: list | None = None) -> str | None:
    """'Good', or 'High risk — 2 critical findings' when a critical item caps the band."""
    if score is None:
        return None
    from app.livewell.rule_engine_defaults import BAND_DISPLAY, risk_band_for_score

    crit = payload.get("criticalFindings") or payload.get("critical_findings") or []
    n = len(crit) if isinstance(crit, list) else 0
    band = risk_band_for_score(int(score), rules, critical_unsafe=n > 0)
    key = str(band.get("band") or "").lower()
    label = BAND_DISPLAY.get(key, (str(band.get("label") or "") or None,))[0]
    if n and key in ("high", "critical"):
        return f"{'High risk' if key == 'high' else label} — {n} critical finding{'' if n == 1 else 's'}"
    return label


# Assessment record status → the two states staff see.
STATUS_WORD = {"completed": "Completed", "draft": "In progress", "in_progress": "In progress"}


def _status_key(status: str | None) -> str:
    return "completed" if status == "completed" else "in_progress"


def _record_score(r) -> int | None:
    p = r.payload if isinstance(r.payload, dict) else {}
    v = r.server_score if r.server_score is not None else p.get("independenceScore")
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _area_scores(payload: dict, categories) -> dict[str, int]:
    from app.livewell import scoring
    from app.livewell.score_explain import _area

    try:
        result = scoring.score_assessment(payload, categories)
    except Exception:  # noqa: BLE001 — a malformed old payload just has no areas
        return {}
    return {_area(d.get("title")): int(d.get("score") or 0) for d in result.get("domain_scores") or []}


def client_assessments(db: Session, elder) -> dict:
    """Every assessment for one client (newest first), open assessment jobs, and a
    comparison of the latest two completed ones (the three areas that moved most)."""
    from app.livewell import scoring
    from app.models.care_job import CareJob
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    records = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder.id)
        .order_by(HomeSafetyAssessmentRecord.updated_at.desc())
        .limit(50)
        .all()
    )
    jobs = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id == elder.id,
            CareJob.kind == "assessment",
            CareJob.status.notin_(("cancelled", "missed", "completed")),
        )
        .order_by(CareJob.scheduled_at)
        .all()
    )
    job_by_assessment = {j.assessment_id: j for j in jobs if j.assessment_id}
    user_ids = {r.created_by_user_id for r in records if r.created_by_user_id}
    names = (
        {u.id: f"{u.first_name} {u.last_name}".strip() for u in db.query(User).filter(User.id.in_(list(user_ids))).all()}
        if user_ids
        else {}
    )

    rules = _risk_rules(db.get(Tenant, elder.tenant_id))
    rows = []
    for r in records:
        p = r.payload if isinstance(r.payload, dict) else {}
        score = _record_score(r) if r.status == "completed" else None
        job = job_by_assessment.get(r.assessment_id)
        when = r.completed_at or r.updated_at or r.created_at
        rows.append(
            {
                "id": r.assessment_id,
                "status": _status_key(r.status),
                "date": _iso(when),
                "score": score,
                "band": _band(score, p, rules),
                "assessor": str(p.get("assessorName") or "").strip() or names.get(r.created_by_user_id) or "",
                "job_id": job.id if job else None,
                "change": None,
            }
        )
    rows.sort(key=lambda x: x["date"] or "", reverse=True)
    rows.sort(key=lambda x: x["status"] == "completed")  # drafts first, then completed newest first
    for x in rows:
        x["status_label"] = STATUS_WORD[x["status"]]
    done = [x for x in rows if x["status"] == "completed" and x["score"] is not None]
    for newer, older in zip(done, done[1:]):
        newer["change"] = newer["score"] - older["score"]

    compare = None
    completed = [r for r in records if r.status == "completed" and isinstance(r.payload, dict)]
    if len(completed) >= 2:
        completed.sort(key=lambda r: r.completed_at or r.updated_at, reverse=True)
        tenant = db.get(Tenant, elder.tenant_id)
        categories, _src = scoring.effective_rubric(tenant.workflow_config if tenant else None)
        now_a, before_a = _area_scores(completed[0].payload, categories), _area_scores(completed[1].payload, categories)
        moved = [
            {"area": k, "before": before_a[k], "now": now_a[k], "change": now_a[k] - before_a[k]}
            for k in now_a
            if k in before_a and now_a[k] != before_a[k]
        ]
        moved.sort(key=lambda m: -abs(m["change"]))
        compare = {
            "now": {"id": completed[0].assessment_id, "score": _record_score(completed[0]), "date": _iso(completed[0].completed_at or completed[0].updated_at)},
            "before": {"id": completed[1].assessment_id, "score": _record_score(completed[1]), "date": _iso(completed[1].completed_at or completed[1].updated_at)},
            "areas": moved[:3],
        }

    linked = {r.assessment_id for r in records}
    return {
        "assessments": rows,
        "booked": [
            {
                "job_id": j.id,
                "scheduled_at": _iso(j.scheduled_at),
                "status": j.status,
                "title": j.title,
                "started": j.status == "checked_in",
            }
            for j in jobs
            if not (j.assessment_id and j.assessment_id in linked)
        ],
        "compare": compare,
    }


def _latest_band(db: Session, elder) -> str | None:
    """Band for the header, from the latest completed assessment and the tenant's rules."""
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord as Rec

    r = (
        db.query(Rec)
        .filter(Rec.elder_id == elder.id, Rec.status == "completed")
        .order_by(Rec.completed_at.desc().nullslast(), Rec.id.desc())
        .first()
    )
    if not r:
        return None
    return _band(_record_score(r), r.payload if isinstance(r.payload, dict) else {}, _risk_rules(db.get(Tenant, elder.tenant_id)))
