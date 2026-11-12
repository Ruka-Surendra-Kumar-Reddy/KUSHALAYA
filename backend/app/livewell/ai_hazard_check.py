"""AI room hazard check — start (cached / capped), run in the background, staff decide.

Flow: start_check() creates a job row (or reuses a cached result for the same image),
the API schedules run_check() as a background task, the page polls get_check().
Nothing is applied silently: every hazard waits for a staff Confirm / Not right.
Confirming writes the rating into a draft assessment with attribution; on a finished
assessment (or a client-page check) it is kept and carried into the next reassessment.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.core.team_scope import assert_elder_in_team, team_elder_ids
from app.livewell.ai_config_service import get_ai_settings
from app.livewell.ai_hazard_catalog import (
    SEVERITY_ORDER,
    build_catalog,
    catalog_hash,
    codes_for_room,
    products_for_solution,
    room_label,
)
from app.livewell.ai_hazard_provider import (
    HazardProviderError,
    get_hazard_provider,
    strip_image_metadata,
)
from app.livewell.ai_usage import provider_calls_today, record_ai_usage
from app.livewell.document_types import HOME_SAFETY_PHOTO
from app.livewell.stored_config import read_stored_config
from app.models.ai_hazard_check import AiHazardCheck, AiHazardFeedback
from app.models.document import Document
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

FEATURE = "hazard_check"
DEFAULT_DAILY_CAP = 100
STAGE_QUEUED = "Getting ready…"
STAGE_READING = "Reading photo…"
STAGE_CHECKING = "Checking hazards…"
STAGE_DONE = "Done"
RATING_RISK = "unsafe"  # shown as "Risk"
RATING_ATTENTION = "acceptable"  # shown as "Needs attention"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_name(user: User) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or (user.email or "staff")


def _tenant(db: Session, user: User) -> Tenant:
    tid = resolve_tenant_id(user)
    if tid is None:
        raise_bad_request("Tenant required")
    tenant = db.get(Tenant, tid)
    if not tenant:
        raise_bad_request("Tenant not found")
    assert_tenant_access(user, tenant.id)
    return tenant


# --- configuration -------------------------------------------------------------


def tenant_catalog(tenant: Tenant) -> dict[str, dict]:
    from app.livewell.scoring import effective_rubric
    from app.livewell.solution_service import DEFAULT_SOLUTIONS

    stored = read_stored_config(tenant.workflow_config or {})
    solutions = (stored.get("solutions") or {}).get("solutions") or DEFAULT_SOLUTIONS.get("solutions") or []
    categories, _src = effective_rubric(tenant.workflow_config or {})
    labels = {
        str(item.get("id")): str(item.get("label") or "")
        for cat in categories
        for item in cat.get("items") or []
        if item.get("id")
    }
    vmap = (stored.get("ai_config") or {}).get("vision_finding_map") or []
    return build_catalog(vision_finding_map=vmap, solutions=solutions, rubric_labels=labels)


def tenant_thresholds(tenant: Tenant) -> dict:
    stored = read_stored_config(tenant.workflow_config or {})
    s = get_ai_settings(stored.get("ai_config") or {})
    return {
        "high": int(s.get("vision_auto_apply_confidence_min") or 85),
        "check": int(s.get("vision_assessor_confirm_min") or 60),
        "daily_cap": int(s.get("hazard_check_daily_cap") or DEFAULT_DAILY_CAP),
    }


def _band(conf: int, th: dict) -> str:
    if conf >= th["high"]:
        return "high"
    if conf >= th["check"]:
        return "check"
    return "low"


# --- access --------------------------------------------------------------------


def _photo(db: Session, tenant_id: int, document_id: int) -> Document:
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.document_type == HOME_SAFETY_PHOTO,
        )
        .first()
    )
    if not doc:
        raise_not_found("Photo not found")
    return doc


def _customer_of(doc: Document) -> tuple[int | None, int | None]:
    if doc.entity_type == "elder":
        return doc.entity_id, None
    if doc.entity_type == "elder_prospect":
        return None, doc.entity_id
    return None, None


def _assert_scope(db: Session, user: User, elder_id: int | None) -> None:
    if elder_id is not None:
        assert_elder_in_team(db, user, elder_id)


def _get_row(db: Session, user: User, public_id: str) -> AiHazardCheck:
    tenant = _tenant(db, user)
    row = (
        db.query(AiHazardCheck)
        .filter(AiHazardCheck.tenant_id == tenant.id, AiHazardCheck.public_id == public_id)
        .first()
    )
    if not row:
        raise_not_found("Room check not found")
    _assert_scope(db, user, row.elder_id)
    return row


# --- start / run ---------------------------------------------------------------


def _fresh_hazards(hazards: list[dict]) -> list[dict]:
    keep = ("n", "code", "confidence", "band", "box", "evidence", "room")
    return [{**{k: h.get(k) for k in keep}, "decision": "pending"} for h in hazards or []]


def start_check(
    db: Session,
    user: User,
    *,
    document_id: int,
    room_type: str | None = None,
    assessment_id: str | None = None,
    force: bool = False,
) -> tuple[AiHazardCheck, bool]:
    """Returns (row, needs_run). needs_run is False for cache hits and in-flight jobs."""
    tenant = _tenant(db, user)
    doc = _photo(db, tenant.id, document_id)
    elder_id, prospect_id = _customer_of(doc)
    _assert_scope(db, user, elder_id)
    meta = doc.ocr_extracted_json or {}
    room = (room_type or meta.get("room_type") or "").strip().lower() or None
    assessment = (assessment_id or meta.get("assessment_id") or "").strip() or None

    try:
        raw, _mime = get_storage().read(doc.storage_key)
    except HTTPException:
        raise
    except Exception:
        raw = b""
    if not raw:
        raise_bad_request("Could not read this photo. Please upload it again.")
    sha = hashlib.sha256(raw).hexdigest()

    catalog = tenant_catalog(tenant)
    codes = codes_for_room(catalog, room)
    if not codes:
        raise_bad_request("No hazards are set up for this room type.")
    chash = catalog_hash(codes)

    base = db.query(AiHazardCheck).filter(
        AiHazardCheck.tenant_id == tenant.id,
        AiHazardCheck.sha256 == sha,
        AiHazardCheck.catalog_hash == chash,
    )
    # A check already running for this photo: just follow it.
    running = (
        base.filter(AiHazardCheck.document_id == doc.id, AiHazardCheck.status.in_(("queued", "running")))
        .order_by(AiHazardCheck.id.desc())
        .first()
    )
    if running:
        return running, False

    if not force:
        same_doc = (
            base.filter(AiHazardCheck.document_id == doc.id, AiHazardCheck.status == "succeeded")
            .order_by(AiHazardCheck.id.desc())
            .first()
        )
        if same_doc:
            if assessment and not same_doc.assessment_id:
                same_doc.assessment_id = assessment
                db.commit()
            return same_doc, False
        earlier = base.filter(AiHazardCheck.status == "succeeded").order_by(AiHazardCheck.id.desc()).first()
        if earlier:
            row = AiHazardCheck(
                public_id=f"HZC-{secrets.token_hex(5).upper()}",
                tenant_id=tenant.id,
                document_id=doc.id,
                elder_id=elder_id,
                prospect_id=prospect_id,
                assessment_id=assessment,
                room_type=room,
                sha256=sha,
                catalog_hash=chash,
                provider=earlier.provider,
                model_version=earlier.model_version,
                cache_hit=True,
                status="succeeded",
                stage=STAGE_DONE,
                hazards=_fresh_hazards(earlier.hazards or []),
                notes=earlier.notes,
                created_by_user_id=user.id,
                finished_at=_now(),
            )
            db.add(row)
            db.flush()
            record_ai_usage(
                db, tenant_id=tenant.id, feature=FEATURE, provider=row.provider, model=row.model_version,
                cache_hit=True, user_id=user.id, ref=row.public_id,
            )
            db.commit()
            db.refresh(row)
            return row, False

    provider = get_hazard_provider()
    if not provider.is_configured():
        raise_bad_request("AI checks are not switched on for this server yet.")
    th = tenant_thresholds(tenant)
    if provider_calls_today(db, tenant.id, FEATURE) >= th["daily_cap"]:
        raise HTTPException(
            status_code=429,
            detail=f"Today's limit of {th['daily_cap']} AI room checks is used up. It resets at midnight.",
        )

    row = AiHazardCheck(
        public_id=f"HZC-{secrets.token_hex(5).upper()}",
        tenant_id=tenant.id,
        document_id=doc.id,
        elder_id=elder_id,
        prospect_id=prospect_id,
        assessment_id=assessment,
        room_type=room,
        sha256=sha,
        catalog_hash=chash,
        provider=provider.name(),
        model_version=provider.model_version(),
        cache_hit=False,
        status="queued",
        stage=STAGE_QUEUED,
        hazards=[],
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def run_check(session_factory: Callable[[], Session], check_id: int) -> None:
    """Background job: clean the image, ask the model, store validated hazards."""
    db = session_factory()
    try:
        row = db.get(AiHazardCheck, check_id)
        if not row or row.status not in ("queued", "running"):
            return
        row.status, row.stage = "running", STAGE_READING
        db.commit()

        tenant = db.get(Tenant, row.tenant_id)
        doc = db.get(Document, row.document_id)
        catalog = tenant_catalog(tenant)
        th = tenant_thresholds(tenant)
        codes = codes_for_room(catalog, row.room_type)
        provider = get_hazard_provider()
        try:
            raw, _mime = get_storage().read(doc.storage_key)
            clean = strip_image_metadata(raw)
        except Exception:
            logger.exception("Hazard check %s: could not read image", row.public_id)
            row.status, row.stage = "failed", None
            row.error_message = "Could not read this photo. Try a JPG or PNG photo."
            row.finished_at = _now()
            db.commit()
            return

        row.stage = STAGE_CHECKING
        db.commit()
        try:
            result = provider.detect(clean, [catalog[c] for c in codes])
        except HazardProviderError as exc:
            row.status, row.stage = "failed", None
            row.error_message = str(exc)
            row.finished_at = _now()
            record_ai_usage(
                db, tenant_id=row.tenant_id, feature=FEATURE, provider=provider.name(),
                model=provider.model_version(), status="failed", user_id=row.created_by_user_id, ref=row.public_id,
            )
            db.commit()
            return

        allowed = set(codes)
        hazards: list[dict] = []
        for det in result.hazards:
            if det.code not in allowed:  # second guard; the provider already filters
                continue
            h = catalog[det.code]
            hazards.append(
                {
                    "code": det.code,
                    "confidence": int(det.confidence),
                    "band": _band(int(det.confidence), th),
                    "box": det.box,
                    "evidence": det.evidence,
                    "room": row.room_type or (h["rooms"][0] if h["rooms"] else None),
                    "decision": "pending",
                }
            )
        hazards.sort(key=lambda x: (SEVERITY_ORDER.get(catalog[x["code"]]["severity"], 9), -x["confidence"]))
        for i, h in enumerate(hazards, start=1):
            h["n"] = i
        if result.rejected_codes:
            logger.info("Hazard check %s dropped unknown codes: %s", row.public_id, result.rejected_codes[:10])
        row.hazards = hazards
        row.notes = result.notes
        row.model_version = result.model
        row.provider = result.provider
        row.status, row.stage = "succeeded", STAGE_DONE
        row.finished_at = _now()
        record_ai_usage(
            db, tenant_id=row.tenant_id, feature=FEATURE, provider=result.provider, model=result.model,
            user_id=row.created_by_user_id, ref=row.public_id,
        )
        db.commit()
    except Exception:
        logger.exception("Hazard check %s crashed", check_id)
        db.rollback()
        row = db.get(AiHazardCheck, check_id)
        if row and row.status in ("queued", "running"):
            row.status, row.stage = "failed", None
            row.error_message = "Something went wrong while checking. Please try again."
            row.finished_at = _now()
            db.commit()
    finally:
        db.close()


# --- read ----------------------------------------------------------------------


def _catalog_products(db: Session) -> list[dict]:
    from app.livewell.global_catalog_store import ensure_global_catalog_dict

    try:
        return list((ensure_global_catalog_dict(db) or {}).get("products") or [])
    except Exception:
        db.rollback()
        return []


def check_to_dict(
    row: AiHazardCheck,
    catalog: dict[str, dict],
    products: list[dict] | None,
) -> dict:
    hazards = []
    for h in row.hazards or []:
        d = catalog.get(h.get("code"))
        if not d:
            continue  # code switched off since the check ran
        room = h.get("room") or row.room_type
        hazards.append(
            {
                **h,
                "label": d["label"],
                "room": room,
                "room_label": room_label(room),
                "severity": d["severity"],
                "severity_label": d["severity_label"],
                "solution_id": d["solution_id"],
                "solution_name": d["solution_name"],
                "rubric_item_id": d["rubric_item_id"],
                "question": d["question"],
                "products": products_for_solution(products or [], d["solution_id"]) if products is not None else [],
            }
        )
    return {
        "id": row.public_id,
        "document_id": row.document_id,
        "elder_id": row.elder_id,
        "prospect_id": row.prospect_id,
        "assessment_id": row.assessment_id,
        "room_type": row.room_type,
        "room_label": room_label(row.room_type),
        "status": row.status,
        "stage": row.stage,
        "cache_hit": bool(row.cache_hit),
        "model": row.model_version,
        "hazards": hazards,
        "notes": row.notes,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "shared_with_family_at": row.shared_with_family_at.isoformat() if row.shared_with_family_at else None,
    }


def get_check(db: Session, user: User, public_id: str) -> dict:
    row = _get_row(db, user, public_id)
    tenant = db.get(Tenant, row.tenant_id)
    products = _catalog_products(db) if row.status == "succeeded" else []
    return check_to_dict(row, tenant_catalog(tenant), products)


def room_summary(checks: list[dict]) -> dict:
    """Confirmed hazards per room: [{room, label, hazards, urgent}], plus totals."""
    rooms: dict[str, dict] = {}
    seen: set[tuple] = set()
    pending = 0
    for c in checks:
        for h in c.get("hazards") or []:
            if h.get("decision") == "pending" and h.get("band") != "low":
                pending += 1
            if h.get("decision") != "confirmed":
                continue
            key = (c.get("document_id"), h.get("code"))
            if key in seen:
                continue
            seen.add(key)
            room = h.get("room") or "other"
            r = rooms.setdefault(room, {"room": room, "label": room_label(room), "hazards": 0, "urgent": 0})
            r["hazards"] += 1
            if h.get("severity") == "urgent":
                r["urgent"] += 1
    ordered = sorted(rooms.values(), key=lambda r: (-r["urgent"], -r["hazards"], r["label"]))
    return {
        "rooms": ordered,
        "total_confirmed": sum(r["hazards"] for r in ordered),
        "total_urgent": sum(r["urgent"] for r in ordered),
        "pending": pending,
    }


def list_checks(
    db: Session,
    user: User,
    *,
    assessment_id: str | None = None,
    elder_id: int | None = None,
    document_id: int | None = None,
    recent: bool = False,
) -> dict:
    tenant = _tenant(db, user)
    q = db.query(AiHazardCheck).filter(AiHazardCheck.tenant_id == tenant.id)
    if elder_id is not None:
        _assert_scope(db, user, elder_id)
        q = q.filter(AiHazardCheck.elder_id == elder_id)
    if assessment_id:
        q = q.filter(AiHazardCheck.assessment_id == assessment_id)
    if document_id is not None:
        q = q.filter(AiHazardCheck.document_id == document_id)
    if not (assessment_id or elder_id is not None or document_id is not None or recent):
        raise_bad_request("assessment_id, elder_id or document_id is required")
    team = team_elder_ids(db, user)
    rows = q.order_by(AiHazardCheck.id.desc()).limit(200).all()
    # Latest check per photo only.
    latest: dict[int, AiHazardCheck] = {}
    for r in rows:
        if team is not None and r.elder_id is not None and r.elder_id not in team:
            continue
        latest.setdefault(r.document_id, r)
    catalog = tenant_catalog(tenant)
    products = _catalog_products(db)
    checks = [check_to_dict(r, catalog, products) for r in latest.values()]
    if recent:  # Room checks → History: name each client
        from app.models.elder import Elder

        ids = {c["elder_id"] for c in checks if c["elder_id"]}
        names = {e.id: f"{e.first_name} {e.last_name or ''}".strip() for e in db.query(Elder).filter(Elder.id.in_(ids)).all()} if ids else {}
        for c in checks:
            c["elder_name"] = names.get(c["elder_id"])
    return {"checks": checks, "summary": room_summary(checks)}


def set_shared(db: Session, user: User, public_id: str, shared: bool) -> dict:
    """Show (or stop showing) this check's confirmed hazards on the family portal."""
    row = _get_row(db, user, public_id)
    if shared and row.elder_id is None:
        raise_bad_request("This photo is not linked to a client yet.")
    row.shared_with_family_at = _now() if shared else None
    row.shared_by_user_id = user.id if shared else None
    db.commit()
    db.refresh(row)
    return check_to_dict(row, tenant_catalog(_tenant(db, user)), None)


# --- decide --------------------------------------------------------------------


def _apply_to_assessment(
    db: Session,
    tenant_id: int,
    assessment_id: str | None,
    rubric_item_id: str,
    rating: str,
    note: str,
    source: dict,
) -> bool:
    """Write the rating into a draft assessment. Finished assessments are locked: no write."""
    if not assessment_id or not rubric_item_id:
        return False
    rec = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(
            HomeSafetyAssessmentRecord.tenant_id == tenant_id,
            HomeSafetyAssessmentRecord.assessment_id == assessment_id,
        )
        .first()
    )
    if not rec or rec.status == "completed":
        return False
    payload = dict(rec.payload or {})
    ratings = dict(payload.get("ratings") or {})
    notes = dict(payload.get("itemNotes") or {})
    sources = dict(payload.get("aiHazardSources") or {})
    ratings[rubric_item_id] = rating
    existing = str(notes.get(rubric_item_id) or "").strip()
    if note not in existing:
        notes[rubric_item_id] = f"{existing}\n{note}".strip() if existing else note
    sources[rubric_item_id] = source
    payload["ratings"], payload["itemNotes"], payload["aiHazardSources"] = ratings, notes, sources
    rec.payload = payload
    return True


def decide(
    db: Session,
    user: User,
    public_id: str,
    n: int,
    *,
    decision: str,
    rating: str | None = None,
) -> dict:
    row = _get_row(db, user, public_id)
    if row.status != "succeeded":
        raise_bad_request("This check has not finished yet.")
    tenant = db.get(Tenant, row.tenant_id)
    catalog = tenant_catalog(tenant)
    hazards = [dict(h) for h in (row.hazards or [])]
    target = next((h for h in hazards if int(h.get("n") or 0) == int(n)), None)
    if not target:
        raise_not_found("Hazard not found")
    if decision not in ("confirm", "reject"):
        raise_bad_request("decision must be confirm or reject")
    d = catalog.get(target["code"]) or {}
    who = _user_name(user)
    at = _now().isoformat()
    applied = False
    if decision == "confirm":
        if rating not in (None, RATING_RISK, RATING_ATTENTION):
            raise_bad_request("rating must be unsafe (Risk) or acceptable (Needs attention)")
        chosen = rating or (RATING_ATTENTION if d.get("severity") == "watch" else RATING_RISK)
        note = f"AI-checked, confirmed by {who}"
        target.update({"decision": "confirmed", "rating": chosen, "decided_by": who, "decided_at": at,
                       "source": note})
        if d.get("rubric_item_id"):
            applied = _apply_to_assessment(
                db, row.tenant_id, row.assessment_id, d["rubric_item_id"], chosen, note,
                {"check_id": row.public_id, "code": target["code"], "confirmed_by": who, "at": at},
            )
            if applied:
                target["applied_to"] = row.assessment_id
    else:
        target.update({"decision": "rejected", "decided_by": who, "decided_at": at, "rating": None})
        target.pop("applied_to", None)
    row.hazards = hazards
    db.add(
        AiHazardFeedback(
            tenant_id=row.tenant_id,
            check_id=row.id,
            hazard_code=target["code"],
            decision="accepted" if decision == "confirm" else "rejected",
            confidence=int(target.get("confidence") or 0),
            model_version=row.model_version,
            user_id=user.id,
        )
    )
    db.commit()
    db.refresh(row)
    out = check_to_dict(row, catalog, _catalog_products(db))
    out["applied_to_assessment"] = applied
    return out


def carry_over(db: Session, user: User, assessment_id: str) -> dict:
    """Confirmed hazards from this client's earlier checks, written into a draft reassessment."""
    tenant = _tenant(db, user)
    rec = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(
            HomeSafetyAssessmentRecord.tenant_id == tenant.id,
            HomeSafetyAssessmentRecord.assessment_id == assessment_id,
        )
        .first()
    )
    if not rec or not rec.elder_id:
        return {"applied": []}
    _assert_scope(db, user, rec.elder_id)
    if rec.status == "completed":
        raise_bad_request("This assessment is finished. Reopen it to add hazards.")
    catalog = tenant_catalog(tenant)
    rows = (
        db.query(AiHazardCheck)
        .filter(
            AiHazardCheck.tenant_id == tenant.id,
            AiHazardCheck.elder_id == rec.elder_id,
            AiHazardCheck.status == "succeeded",
        )
        .all()
    )
    applied: list[dict] = []
    for row in rows:
        if row.assessment_id == assessment_id:
            continue
        hazards = [dict(h) for h in (row.hazards or [])]
        changed = False
        for h in hazards:
            d = catalog.get(h.get("code")) or {}
            if h.get("decision") != "confirmed" or h.get("applied_to") or not d.get("rubric_item_id"):
                continue
            note = h.get("source") or f"AI-checked, confirmed by {h.get('decided_by') or 'staff'}"
            rating = h.get("rating") or RATING_RISK
            if _apply_to_assessment(
                db, tenant.id, assessment_id, d["rubric_item_id"], rating, note,
                {"check_id": row.public_id, "code": h["code"], "confirmed_by": h.get("decided_by"),
                 "at": h.get("decided_at")},
            ):
                h["applied_to"] = assessment_id
                changed = True
                applied.append({"rubric_item_id": d["rubric_item_id"], "rating": rating, "note": note,
                                "label": d["label"], "room_label": room_label(h.get("room"))})
        if changed:
            row.hazards = hazards
    db.commit()
    return {"applied": applied}


def pending_carry_over(db: Session, user: User, elder_id: int, exclude_assessment: str | None = None) -> list[dict]:
    """Confirmed hazards not yet in any assessment (for the 'add to this reassessment' prompt)."""
    data = list_checks(db, user, elder_id=elder_id)
    out = []
    for c in data["checks"]:
        if exclude_assessment and c.get("assessment_id") == exclude_assessment:
            continue
        for h in c["hazards"]:
            if h.get("decision") == "confirmed" and not h.get("applied_to") and h.get("rubric_item_id"):
                out.append({"check_id": c["id"], "n": h["n"], "label": h["label"], "room_label": h["room_label"],
                            "severity_label": h["severity_label"]})
    return out


# --- family --------------------------------------------------------------------


def family_hazards(db: Session, elder_id: int, tenant_id: int) -> dict:
    """Confirmed hazards only, in plain words. No confidence, boxes or staff names."""
    tenant = db.get(Tenant, tenant_id)
    catalog = tenant_catalog(tenant)
    rows = (
        db.query(AiHazardCheck)
        .filter(
            AiHazardCheck.tenant_id == tenant_id,
            AiHazardCheck.elder_id == elder_id,
            AiHazardCheck.status == "succeeded",
            AiHazardCheck.shared_with_family_at.isnot(None),
        )
        .order_by(AiHazardCheck.id.desc())
        .all()
    )
    seen: set[tuple] = set()
    items: list[dict] = []
    for r in rows:
        for h in r.hazards or []:
            d = catalog.get(h.get("code"))
            if not d or h.get("decision") != "confirmed":
                continue
            room = h.get("room") or r.room_type
            key = (room, h["code"])
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "room_label": room_label(room),
                    "label": d["label"],
                    "severity_label": d["severity_label"],
                    "suggestion": d["solution_name"],
                }
            )
    items.sort(key=lambda i: ({"Urgent": 0, "Soon": 1}.get(i["severity_label"], 2), i["room_label"]))
    return {"hazards": items, "total": len(items)}
