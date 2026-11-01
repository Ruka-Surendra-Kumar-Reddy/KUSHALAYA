"""AI room preview — "See it in their home".

Staff (prefix /home-safety/ai/preview): pick a room photo, products (preselected from the
assessment), a package; the render runs in the background (ai_render_queue) and the page
polls the job. Admins and managers (team-scoped) generate and approve; VIEWER reads.

Family (prefix /home-safety/family/ai-previews): approved, non-stub previews only, with
items and prices incl. GST, one "Request these fixes" request, and a one-page PDF.

Hazard-check integration: the ops page opens with
/kushalaya/ai-preview?assessment=<id>&photo=<documentId>&products=BTH-002,BTH-009
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_elder_portal, require_roles
from app.core.storage import get_storage
from app.livewell import ai_room_preview as rp
from app.livewell.ai_visualization_service import HomeSafetyAIVisualizationService as Svc
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.livewell.document_types import HOME_SAFETY_PHOTO
from app.models.document import Document
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/home-safety/ai/preview", tags=["Safe Home — AI room preview"])
family_router = APIRouter(prefix="/home-safety/family/ai-previews", tags=["Family — AI room preview"])

TIERS = [
    {"id": "essential", "name": "Essential"},
    {"id": "comfort", "name": "Comfort"},
    {"id": "premium", "name": "Premium"},
]
DISCLAIMER = (
    "Illustration made with AI from a room photo and checked by KushAlaya staff. "
    "Actual products, colours and positions may differ; final fitting is confirmed on site."
)


class PreviewCreate(BaseModel):
    assessment_id: str = Field(min_length=1, max_length=64)
    source_document_id: int
    room_type: str = Field(min_length=1, max_length=32)
    package_level: str = "comfort"
    product_codes: list[str] = Field(default_factory=list, max_length=12)
    force: bool = False


class PreviewReview(BaseModel):
    action: str
    notes: str | None = None


def _settings(db: Session, user: User) -> dict:
    ctx = Svc._load_job_context(db, user)
    return ctx.settings


def _tenant_id(db: Session, user: User) -> int:
    return Svc._tenant(db, user).id


def _job(db: Session, user: User, public_id: str) -> HomeSafetyAIJob:
    tid = _tenant_id(db, user)
    job = (
        db.query(HomeSafetyAIJob)
        .filter(HomeSafetyAIJob.tenant_id == tid, HomeSafetyAIJob.public_id == public_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="AI preview not found")
    rp.assert_job_in_team(db, user, job)
    return job


def _markers(job: HomeSafetyAIJob) -> list[dict]:
    """Numbered markers only where the QA step returned a real box — never invented."""
    qa = (Svc._preview_checks(job).get("qa") or {})
    return [
        {"n": i["n"], "product": i["product"], **i["box"]}
        for i in qa.get("items") or []
        if i.get("present") and isinstance(i.get("box"), dict)
    ]


def _view(db: Session, job: HomeSafetyAIJob, settings: dict | None = None) -> dict:
    pricing = rp.priced_items(db, job.tenant_id, Svc._explicit_product_codes(job))
    checks = Svc._preview_checks(job)
    qa = checks.get("qa") or {}
    present = {i["n"]: i for i in qa.get("items") or []}
    for item in pricing["items"]:
        q = present.get(item["n"])
        item["shown"] = None if q is None else bool(q.get("present"))
    return {
        "ai_job_id": job.public_id,
        "assessment_id": job.assessment_id,
        "elder_id": job.elder_id,
        "prospect_id": job.prospect_id,
        "room_type": job.room_type,
        "package_level": job.package_level,
        "source_document_id": job.source_document_id,
        "generated_document_id": job.generated_document_id,
        "before_url": f"/api/v1/home-safety/photos/{job.source_document_id}/image",
        "after_url": (
            f"/api/v1/home-safety/photos/{job.generated_document_id}/image"
            if job.generated_document_id
            else None
        ),
        "status": job.status,
        "review_status": job.review_status,
        "provider": job.provider,
        "is_stub": (job.provider or "") in ("local_stub", "stub"),
        "error_message": job.error_message if job.status in ("failed", "awaiting_provider") else None,
        "progress": rp.job_progress(job),
        "similarity_score": job.similarity_score,
        "similarity_min": checks.get("similarity_min"),
        "room_changed": bool(checks.get("room_changed")) or bool(qa.get("changes")),
        "qa_status": qa.get("status"),
        "missing": qa.get("missing") or [],
        "changes": qa.get("changes") or [],
        "markers": _markers(job),
        "render_attempts": job.render_attempts or 0,
        "regenerated_from": job.regenerated_from,
        "regenerations_left": rp.regenerations_left(db, job, settings or {}) if settings is not None else None,
        "created_at": job.created_at,
        "reviewed_at": job.reviewed_at,
        **pricing,
    }


def _assessment(db: Session, user: User, assessment_id: str) -> HomeSafetyAssessmentRecord:
    tid = _tenant_id(db, user)
    row = HomeSafetyCustomerLink.assessment_record(db, tid, assessment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if row.elder_id:
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, row.elder_id)
    return row


def _assessment_photos(db: Session, row: HomeSafetyAssessmentRecord) -> list[dict]:
    payload = row.payload or {}
    out: dict[int, dict] = {}
    for p in payload.get("photos") or []:
        if isinstance(p, dict) and p.get("documentId"):
            out[int(p["documentId"])] = {
                "document_id": int(p["documentId"]),
                "room_type": (p.get("roomType") or "").strip().lower(),
                "caption": p.get("caption") or "",
            }
    clauses = []
    if row.elder_id:
        clauses.append((Document.entity_type == "elder") & (Document.entity_id == row.elder_id))
    if row.prospect_id:
        clauses.append((Document.entity_type == "elder_prospect") & (Document.entity_id == row.prospect_id))
    if clauses:
        from sqlalchemy import or_

        docs = (
            db.query(Document)
            .filter(
                Document.tenant_id == row.tenant_id,
                Document.document_type == HOME_SAFETY_PHOTO,
                or_(*clauses),
            )
            .order_by(Document.id.desc())
            .limit(60)
            .all()
        )
        for d in docs:
            meta = d.ocr_extracted_json if isinstance(d.ocr_extracted_json, dict) else {}
            if meta.get("assessment_id") != row.assessment_id or d.id in out:
                continue
            out[d.id] = {
                "document_id": d.id,
                "room_type": str(meta.get("room_type") or "").lower(),
                "caption": str(meta.get("caption") or ""),
            }
    valid = {
        r[0]
        for r in db.query(Document.id)
        .filter(Document.id.in_(list(out) or [-1]), Document.tenant_id == row.tenant_id)
        .all()
    }
    return [
        {**p, "image_url": f"/api/v1/home-safety/photos/{p['document_id']}/image"}
        for p in out.values()
        if p["document_id"] in valid
    ]


# --- Staff -------------------------------------------------------------------------------


@router.get("/context")
def preview_context(
    assessment_id: str | None = Query(None),
    elder_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    """Everything the preview page needs: assessments, photos, recommended products per room,
    the catalog to add from, package tiers, caps and today's usage."""
    tid = _tenant_id(db, user)
    if not assessment_id and elder_id is None:
        raise HTTPException(status_code=400, detail="Pass assessment_id or elder_id")
    if elder_id is not None:
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder_id)
    rows = []
    if elder_id is not None:
        rows = (
            db.query(HomeSafetyAssessmentRecord)
            .filter(HomeSafetyAssessmentRecord.tenant_id == tid, HomeSafetyAssessmentRecord.elder_id == elder_id)
            .order_by(HomeSafetyAssessmentRecord.updated_at.desc())
            .all()
        )
    selected = _assessment(db, user, assessment_id) if assessment_id else None
    if selected is None and rows:
        done = [r for r in rows if r.status == "completed"]
        selected = (done or rows)[0]
    settings = _settings(db, user)
    base = {
        "assessments": [
            {
                "assessment_id": r.assessment_id,
                "status": r.status,
                "updated_at": r.updated_at,
                "completed_at": r.completed_at,
                "created_at": r.created_at,
                "assessor": str((r.payload or {}).get("assessorName") or "").strip() or None,
            }
            for r in rows
        ],
        "tiers": TIERS,
        "catalog": rp.catalog_for_picker(db, tid),
        "caps": {
            "max_photos": rp._int_setting(settings, "max_images_per_assessment", 3),
            "max_regenerations_per_tier": rp._int_setting(settings, "max_regenerations_per_tier", 2),
            "daily_cap": rp._int_setting(settings, "daily_render_cap", 30),
            "today": rp.renders_today(db, tid),
        },
        "provider": Svc._load_job_context(db, user).provider.name(),
    }
    if selected is None:
        return {**base, "assessment_id": None, "client": None, "photos": [], "recommended": {}}
    photos = _assessment_photos(db, selected)
    rooms = {p["room_type"] for p in photos if p["room_type"]} | {
        "bathroom", "bedroom", "kitchen", "living", "hallway", "entry"
    }
    payload = selected.payload or {}
    first = (payload.get("clientFirstName") or "").strip()
    if selected.elder_id:
        from app.models.elder import Elder

        e = db.query(Elder).filter(Elder.id == selected.elder_id).first()
        first = (e.first_name if e else "") or first
    return {
        **base,
        "assessment_id": selected.assessment_id,
        "assessment_status": selected.status,
        "client": {"elder_id": selected.elder_id, "prospect_id": selected.prospect_id, "first_name": first},
        "photos": photos,
        "recommended": {room: rp.recommended_codes(db, user, payload, room) for room in sorted(rooms)},
    }


@router.post("/jobs")
def create_preview(
    data: PreviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Queue one render (returns at once; poll GET /jobs/{id}). Reuses an identical result."""
    row = _assessment(db, user, data.assessment_id)
    tid = row.tenant_id
    pricing = rp.priced_items(db, tid, data.product_codes)
    unknown = [i["product_code"] for i in pricing["items"] if i["product_id"] is None]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown product code(s): {', '.join(unknown)}")
    if not pricing["items"]:
        raise HTTPException(status_code=400, detail="Pick at least one product to show")
    level = data.package_level.strip().lower()
    if level not in {t["id"] for t in TIERS}:
        raise HTTPException(status_code=400, detail="Unknown package")
    out = Svc.create_job(
        db,
        user,
        assessment_id=row.assessment_id,
        room_type=data.room_type.strip().lower(),
        package_level=level,
        source_document_id=data.source_document_id,
        approved_solution_ids=[],
        prospect_id=row.prospect_id,
        elder_id=row.elder_id,
        force=data.force,
        origin_session_id=SessionActivityService.session_id_from_request(request),
        approved_product_codes=[i["product_code"] for i in pricing["items"]],
        product_labels=[i["name"] for i in pricing["items"]],
        defer=True,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action="Started AI room preview",
        summary=f"AI preview {out['ai_job_id']} · {level} · photo #{data.source_document_id}",
        entity_type="assessment",
        entity_id=row.assessment_id,
        meta={"ai_job_id": out["ai_job_id"], "cache_hit": out.get("cache_hit")},
        commit=True,
    )
    job = _job(db, user, out["ai_job_id"])
    return {**_view(db, job, _settings(db, user)), "cache_hit": bool(out.get("cache_hit"))}


@router.get("/jobs")
def list_previews(
    assessment_id: str | None = Query(None),
    elder_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    tid = _tenant_id(db, user)
    q = db.query(HomeSafetyAIJob).filter(
        HomeSafetyAIJob.tenant_id == tid, HomeSafetyAIJob.status != "cancelled"
    )
    if assessment_id:
        q = q.filter(HomeSafetyAIJob.assessment_id == assessment_id)
    if elder_id is not None:
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder_id)
        q = q.filter(HomeSafetyAIJob.elder_id == elder_id)
    out = []
    for job in q.order_by(HomeSafetyAIJob.id.desc()).limit(60).all():
        try:
            rp.assert_job_in_team(db, user, job)
        except HTTPException:
            continue
        out.append(_view(db, job))
    return out


@router.get("/jobs/{public_id}")
def get_preview(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    job = _job(db, user, public_id)
    return _view(db, job, _settings(db, user))


@router.post("/jobs/{public_id}/review")
def review_preview(
    public_id: str,
    data: PreviewReview,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """approve | reject | regenerate (regenerate queues a new job, capped per package)."""
    _job(db, user, public_id)
    result = Svc.review_job(db, user, public_id, action=data.action, notes=data.notes, defer=True)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action=f"AI room preview {data.action}",
        summary=f"{data.action} on AI preview {public_id}",
        entity_type="ai_job",
        entity_id=public_id,
        commit=True,
    )
    job = _job(db, user, result["ai_job_id"])
    return _view(db, job, _settings(db, user))


def _image_bytes(db: Session, doc_id: int | None) -> bytes:
    if not doc_id:
        return b""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return b""
    try:
        data, _ = get_storage().read(doc.storage_key)
        return data
    except Exception:
        return b""


def _pdf_response(db: Session, job: HomeSafetyAIJob) -> Response:
    pricing = rp.priced_items(db, job.tenant_id, Svc._explicit_product_codes(job))
    room = (job.room_type or "Room").replace("_", " ").title()
    pdf = rp.build_preview_pdf(
        title="KushAlaya · Safer home preview",
        first_name=rp.client_first_name(db, job),
        room_label=f"{room} · {(job.package_level or '').title()} package",
        before=_image_bytes(db, job.source_document_id),
        after=_image_bytes(db, job.generated_document_id),
        pricing=pricing,
        disclaimer=DISCLAIMER,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="kushalaya-preview-{job.public_id}.pdf"'},
    )


def _image_response(db: Session, job: HomeSafetyAIJob) -> Response:
    data = _image_bytes(db, job.generated_document_id)
    if not data:
        raise HTTPException(status_code=404, detail="No image yet")
    ext, mime = ("png", "image/png") if data[:8] == b"\x89PNG\r\n\x1a\n" else ("jpg", "image/jpeg")
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="kushalaya-preview-{job.public_id}.{ext}"'},
    )


@router.get("/jobs/{public_id}/pdf")
def preview_pdf(public_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    job = _job(db, user, public_id)
    if not job.generated_document_id:
        raise HTTPException(status_code=400, detail="The preview is not ready yet")
    return _pdf_response(db, job)


@router.get("/jobs/{public_id}/download")
def preview_download(public_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _image_response(db, _job(db, user, public_id))


@router.get("/usage")
def preview_usage(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    """Owner dashboard card: AI images this month and estimated provider cost (paise)."""
    return rp.usage_summary(db, _tenant_id(db, user), _settings(db, user))


# --- Family -------------------------------------------------------------------------------


def _family_jobs(db: Session, user: User) -> list[HomeSafetyAIJob]:
    from app.livewell.family_visualizations import list_approved_visualizations_for_elder
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    rows = list_approved_visualizations_for_elder(db, tenant_id=elder.tenant_id, elder_id=elder.id)
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    jobs = {
        j.public_id: j
        for j in db.query(HomeSafetyAIJob)
        .filter(HomeSafetyAIJob.tenant_id == elder.tenant_id, HomeSafetyAIJob.public_id.in_(ids))
        .all()
    }
    return [jobs[i] for i in ids if i in jobs]


def _family_view(db: Session, job: HomeSafetyAIJob) -> dict:
    pricing = rp.priced_items(db, job.tenant_id, Svc._explicit_product_codes(job))
    room = (job.room_type or "Room").replace("_", " ").title()
    return {
        "id": job.public_id,
        "label": f"{room} · {(job.package_level or '').title()}",
        "room_type": job.room_type,
        "package_level": job.package_level,
        "before_url": f"/api/v1/home-safety/family/photos/{job.source_document_id}/image",
        "after_url": f"/api/v1/home-safety/family/photos/{job.generated_document_id}/image",
        "markers": _markers(job),
        "reviewed_at": job.reviewed_at,
        "items": [
            {k: i[k] for k in ("n", "product_id", "product_code", "name", "price_with_gst_paise", "priced")}
            for i in pricing["items"]
        ],
        "total_paise": pricing["total_paise"],
        "gst_paise": pricing["gst_paise"],
        "all_priced": pricing["all_priced"],
        "disclaimer": DISCLAIMER,
    }


def _family_job(db: Session, user: User, public_id: str) -> HomeSafetyAIJob:
    for job in _family_jobs(db, user):
        if job.public_id == public_id:
            return job
    raise HTTPException(status_code=404, detail="Preview not found")


@family_router.get("")
def family_previews(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    """Approved, real (non-stub) AI previews for the linked family member."""
    return [_family_view(db, j) for j in _family_jobs(db, user)]


class FamilyFixRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


@family_router.post("/{public_id}/request")
def family_request_fixes(
    public_id: str,
    body: FamilyFixRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_elder_portal),
):
    """ONE service request carrying every product in the preview (ids and codes)."""
    from app.livewell.family_service_requests import FamilyServiceRequestService

    job = _family_job(db, user, public_id)
    pricing = rp.priced_items(db, job.tenant_id, Svc._explicit_product_codes(job))
    ids = [i["product_id"] for i in pricing["items"] if i["product_id"]]
    note = f"From AI room preview {job.public_id} ({(job.room_type or '').replace('_', ' ')})."
    if body.notes:
        note = f"{body.notes.strip()}\n{note}"
    result = FamilyServiceRequestService.create_bundle_for_family(db, user, product_ids=ids, notes=note)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action="Requested fixes from AI preview",
        summary=f"Requested {len(ids)} item(s) from preview {job.public_id}",
        entity_type="service_request",
        meta={"ai_job_id": job.public_id, "product_codes": [i["product_code"] for i in pricing["items"]]},
        commit=True,
    )
    return result


@family_router.get("/{public_id}/pdf")
def family_preview_pdf(public_id: str, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return _pdf_response(db, _family_job(db, user, public_id))


@family_router.get("/{public_id}/download")
def family_preview_download(public_id: str, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return _image_response(db, _family_job(db, user, public_id))
