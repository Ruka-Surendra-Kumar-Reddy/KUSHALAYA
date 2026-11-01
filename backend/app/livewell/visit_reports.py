"""Visit reports, the "know them" card and the spotted → fixed hazard loop.

From the Care Manager Trust Playbook and the per-visit review (2026-10-03):
- After every visit the family gets a report: the KushLife check (Safe / Steady /
  Settled / Connected), the caregiver's note and photos.
- Each client has a "know them" card (approach, likes, things to avoid, routine)
  the caregiver reads before knocking.
- A caregiver who spots a new hazard flags it on the visit; it lands on the
  manager's dashboard, becomes an order and an install, and closes as "fixed".
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request, raise_not_found
from app.models.care_job import CareJob
from app.models.commerce import Order, Product
from app.models.elder import Elder

CHECKS = ("safe", "steady", "settled", "connected")
KNOW_THEM_FIELDS = ("approach", "likes", "avoid", "routine", "notes")
HAZARD_STATUSES = ("spotted", "ordered", "fixed", "dismissed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attrs(elder: Elder) -> dict:
    return dict(elder.custom_attributes or {})


def _save(db: Session, elder: Elder, attrs: dict) -> None:
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")


# --- Know them card ----------------------------------------------------------------


def know_them(elder: Elder) -> dict:
    card = _attrs(elder).get("know_them") or {}
    return {f: str(card.get(f) or "") for f in KNOW_THEM_FIELDS} | {"updated_at": card.get("updated_at")}


def save_know_them(db: Session, elder: Elder, data: dict) -> dict:
    attrs = _attrs(elder)
    card = {f: str(data.get(f) or "").strip()[:1500] for f in KNOW_THEM_FIELDS}
    card["updated_at"] = _now()
    attrs["know_them"] = card
    _save(db, elder, attrs)
    db.commit()
    return know_them(elder)


# --- Hazards (spotted → fixed) -----------------------------------------------------


def _hazards(elder: Elder) -> list[dict]:
    sh = _attrs(elder).get("safe_home") or {}
    rows = sh.get("hazards")
    return [dict(r) for r in rows] if isinstance(rows, list) else []


def _save_hazards(db: Session, elder: Elder, rows: list[dict]) -> None:
    attrs = _attrs(elder)
    sh = dict(attrs.get("safe_home") or {})
    sh["hazards"] = rows[-200:]
    attrs["safe_home"] = sh
    _save(db, elder, attrs)


def list_hazards(elder: Elder) -> list[dict]:
    return sorted(_hazards(elder), key=lambda h: h.get("spotted_at") or "", reverse=True)


def add_hazard(db: Session, elder: Elder, *, note: str, product_id: int | None, job_id: int | None, by: str) -> dict:
    product_name = ""
    if product_id:
        p = db.get(Product, product_id)
        if not p or p.tenant_id != elder.tenant_id:
            raise_bad_request("Product not found")
        product_name = p.name
    h = {
        "id": uuid.uuid4().hex[:10],
        "note": (note or "").strip()[:500],
        "product_id": product_id,
        "product_name": product_name,
        "status": "spotted",
        "spotted_at": _now(),
        "spotted_by": by,
        "job_id": job_id,
        "order_id": None,
        "fixed_at": None,
    }
    rows = _hazards(elder)
    rows.append(h)
    _save_hazards(db, elder, rows)
    from app.livewell.email_notifications import email_staff

    name = f"{elder.first_name} {elder.last_name}".strip()
    fix = f" Suggested fix: {product_name}." if product_name else ""
    email_staff(
        db, elder, "hazard", f"Hazard spotted — {name}", f"{h['note'] or 'A new hazard'} (spotted by {by}).{fix}",
        path=f"/kushalaya/customers/{elder.id}?tab=assessments",
    )
    from app.livewell.family_notify import notify_family

    try:
        notify_family(
            db,
            elder,
            "Safety concern found at home",
            f"During a visit our team noticed: {h['note'] or 'something that could cause a fall or injury'}."
            + (f"\nA fix we suggest: {product_name}." if product_name else "")
            + "\nYour care manager will talk it through with you.",
            event="safety",
            path="/safety",
        )
    except Exception:  # a failed notice must never lose the hazard
        import logging

        logging.getLogger(__name__).exception("hazard_family_notify_failed elder=%s", elder.id)
    return h


def set_hazard(db: Session, elder: Elder, hazard_id: str, status: str, order_id: int | None = None) -> dict:
    if status not in HAZARD_STATUSES:
        raise_bad_request("Unknown status")
    rows = _hazards(elder)
    for h in rows:
        if h["id"] == hazard_id:
            h["status"] = status
            if order_id is not None:
                h["order_id"] = order_id
            if status == "fixed":
                h["fixed_at"] = _now()
            _save_hazards(db, elder, rows)
            db.commit()
            return h
    raise_not_found("Hazard not found")


def close_hazards_for_order(db: Session, elder: Elder, order_id: int) -> int:
    rows = _hazards(elder)
    n = 0
    for h in rows:
        if h.get("order_id") == order_id and h["status"] != "fixed":
            h["status"] = "fixed"
            h["fixed_at"] = _now()
            n += 1
    if n:
        _save_hazards(db, elder, rows)
    return n


# --- Visit report ------------------------------------------------------------------


def complete_with_report(db: Session, user, job_id: int, data: dict, *, completed_at=None, live: bool = True) -> dict:
    """Caregiver finishes a visit or install: KushLife check, note, optional hazard."""
    from app.livewell.care_jobs import _caregiver_job, _notify_family, serialize

    job: CareJob = _caregiver_job(db, user, job_id)
    if job.kind == "assessment":
        raise_bad_request("Finish the assessment instead")
    if job.status != "checked_in":
        raise_bad_request("Check in first")
    from app.livewell import kushlife

    record = kushlife.build_record(data)  # every visit must answer all four KushLife checks
    checks = kushlife.plain_checks(record)
    note = (data.get("note") or "").strip()[:2000]
    elder = db.get(Elder, job.elder_id)
    report = dict(job.report or {})
    report.update({"checks": checks, "kushlife": record, "note": note})
    # Who did the visit, kept on the report so the family still sees a name if
    # the job is later unassigned.
    by_name = (getattr(user, "first_name", "") or "").strip()
    if by_name:
        report.setdefault("caregiver_name", by_name)
    from app.livewell.visit_checklist import family_lines, record_results

    # Per-client checklist (#99): saved even when items are unticked (the app asks first).
    checklist = record_results(elder, data.get("checklist"))
    if checklist:
        report["checklist"] = checklist
    hazard = data.get("hazard") or None
    if hazard and (hazard.get("note") or hazard.get("product_id")):
        h = add_hazard(
            db,
            elder,
            note=hazard.get("note") or "",
            product_id=hazard.get("product_id"),
            job_id=job.id,
            by=f"{user.first_name} {user.last_name}".strip(),
        )
        report["hazard_ids"] = [*report.get("hazard_ids", []), h["id"]]
    job.report = report
    flag_modified(job, "report")
    job.status = "completed"
    job.completed_at = completed_at or datetime.now(timezone.utc)
    job.caregiver_note = note
    from app.livewell.care_jobs import record_location

    # Where the report was sent from (the caregiver route requires it; staff may have none).
    record_location(db, job, "checkout", data.get("latitude"), data.get("longitude"), data.get("accuracy"))

    # An installation for an order closes the order and the hazards it fixed.
    if job.kind == "install" and (job.request_id or "").startswith("order-"):
        try:
            order = db.get(Order, int(job.request_id.split("-", 1)[1]))
        except ValueError:
            order = None
        if order and order.elder_id == elder.id:
            order.status = "completed"
            close_hazards_for_order(db, elder, order.id)

    changed = [
        kushlife.LABELS[k]
        + (f" ({', '.join(kushlife.CHIPS_FLAT[c].lower() for c in record['checks'][k]['chips'])})"
           if record["checks"][k]["chips"] else "")
        for k in kushlife.CHECKS
        if checks[k] == "concern"
    ]
    noted = kushlife.noted_text(kushlife.record_changes(record))
    summary = (
        f"KushLife changed: {'; '.join(changed)}."
        if changed
        # "All four as usual" only when the carer noted nothing (slept poorly, ate less…).
        else f"KushLife: noted {noted}." if noted else "KushLife: all four checks as usual."
    )
    if checklist:
        summary = f"{summary} {family_lines(checklist)}"
    _notify_family(db, elder, f"{job.title} report", f"{summary} {note}".strip(), "report")
    from app.livewell.care_jobs import _notify_staff_done

    _notify_staff_done(db, elder, f"{job.title} completed", f"{summary} {note}".strip())
    db.commit()
    db.refresh(job)
    try:
        if live:
            kushlife.after_visit(db, elder, job, record)
    except Exception:  # a flag email must never undo the saved visit
        import logging

        db.rollback()
        logging.getLogger(__name__).exception("kushlife_flags_failed job=%s", job.id)
    return serialize(db, job)


def photo_urls(report: dict | None, *, family: bool) -> list[str]:
    base = "/api/v1/home-safety/family/photos" if family else "/api/v1/home-safety/photos"
    return [f"{base}/{pid}/image" for pid in (report or {}).get("photo_ids") or []]


FAMILY_HIDDEN_KEY = "family_hidden"  # in Document.ocr_extracted_json (the photo's metadata bag)


def is_family_hidden(doc) -> bool:
    """Staff marked this photo internal: the family must never list or fetch it."""
    meta = getattr(doc, "ocr_extracted_json", None)
    return bool(isinstance(meta, dict) and meta.get(FAMILY_HIDDEN_KEY))


def _staff_photo(db: Session, user, document_id: int):
    """A home-safety photo in the caller's tenant (and team, for client photos), else 404."""
    from app.core.rbac import assert_tenant_access, resolve_tenant_id
    from app.core.team_scope import assert_elder_in_team
    from app.livewell.document_types import HOME_SAFETY_PHOTO
    from app.models.document import Document

    tid = resolve_tenant_id(user)
    doc = db.get(Document, document_id)
    if tid is None or doc is None or doc.document_type != HOME_SAFETY_PHOTO or doc.tenant_id != tid:
        raise_not_found("Photo not found")
    assert_tenant_access(user, doc.tenant_id)
    if doc.entity_type == "elder":
        assert_elder_in_team(db, user, doc.entity_id)
    return doc


def photo_family_visibility(db: Session, user, document_id: int) -> dict:
    doc = _staff_photo(db, user, document_id)
    return {"document_id": doc.id, "family_hidden": is_family_hidden(doc)}


def set_photo_family_hidden(db: Session, user, document_id: int, hidden: bool) -> dict:
    """Staff: keep a photo internal (hidden=True) or show it to the family again."""
    doc = _staff_photo(db, user, document_id)
    meta = dict(doc.ocr_extracted_json) if isinstance(doc.ocr_extracted_json, dict) else {}
    if hidden:
        meta[FAMILY_HIDDEN_KEY] = True
    else:
        meta.pop(FAMILY_HIDDEN_KEY, None)
    doc.ocr_extracted_json = meta
    flag_modified(doc, "ocr_extracted_json")
    db.commit()
    return {"document_id": doc.id, "family_hidden": bool(hidden)}


def family_photo_items(db: Session, elder: Elder, photo_ids) -> list[dict]:
    """Photos from one visit that this family may see: [{id, caption, taken_at, url}].

    Each id goes through the same check as the family image endpoint
    (``family_may_read_document``: same tenant, a home-safety photo of *this*
    elder), so an id that points anywhere else is dropped, never exposed.
    """
    from app.livewell.family_visualizations import family_may_read_document
    from app.models.document import Document

    out: list[dict] = []
    for raw in list(photo_ids or [])[:40]:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if not family_may_read_document(db, elder_id=elder.id, tenant_id=elder.tenant_id, document_id=pid):
            continue
        doc = db.get(Document, pid)
        if doc is None or is_family_hidden(doc):
            continue
        caption = (doc.document_name or "").strip()
        out.append({
            "id": pid,
            "caption": "" if caption == "Home safety photo" else caption,  # upload's default label
            "taken_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "url": f"/api/v1/home-safety/family/photos/{pid}/image",
        })
    return out


def log_past_visit(db: Session, user, data: dict) -> dict:
    """Record a visit that already happened: one completed job with its report.

    Unlike booking, the family gets only the report (no "scheduled" / "arrived"
    messages for something in the past).
    """
    from app.livewell.care_jobs import KIND_LABEL, _aware, _caregiver_for, _elder_for

    elder = _elder_for(db, user, int(data["elder_id"]))
    when = _aware(data.get("visited_at"))
    now = datetime.now(timezone.utc)
    if when is None:
        raise_bad_request("Pick when the visit happened")
    if when > now:
        raise_bad_request("That time is in the future — book it on Schedule instead")
    cg = _caregiver_for(db, user, elder, data.get("caregiver_id"))
    job = CareJob(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind="visit",
        title=(data.get("title") or KIND_LABEL["visit"]).strip()[:200],
        location=(elder.address or "")[:500],
        scheduled_at=when,
        duration_minutes=data.get("duration_minutes"),
        caregiver_id=cg.id if cg else None,
        status="checked_in",
        checked_in_at=when,
        staff_note="Logged after the visit",
    )
    db.add(job)
    db.flush()
    # Logged after the fact: dated when it happened; live flags only if it was in the last day.
    # Logged afterwards (usually from the office): where it was typed is not where the
    # visit happened, so no location is stored and no "away from home" alert is raised.
    data = {k: v for k, v in data.items() if k not in ("latitude", "longitude", "accuracy")}
    out = complete_with_report(db, user, job.id, data, completed_at=when, live=(now - when).total_seconds() < 86400)
    out["completed_at"] = when.isoformat()
    return out
