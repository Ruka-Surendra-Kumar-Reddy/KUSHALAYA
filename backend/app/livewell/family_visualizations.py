"""Approved AI before/after visuals for the family portal."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.livewell.document_types import HOME_SAFETY_AI_CONCEPT
from app.models.document import Document
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_ai_job import HomeSafetyAIJob


def _job_is_stub(job: HomeSafetyAIJob, concept_doc: Document | None) -> bool:
    provider = (job.provider or "").strip().lower()
    if provider in ("local_stub", "stub"):
        return True
    if concept_doc is not None:
        meta = concept_doc.ocr_extracted_json if isinstance(concept_doc.ocr_extracted_json, dict) else {}
        if meta.get("is_stub") is True:
            return True
    return False


def _elder_matches_job(db: Session, elder_id: int, job: HomeSafetyAIJob) -> bool:
    if job.elder_id == elder_id:
        return True
    if job.prospect_id:
        prospect = (
            db.query(ElderProspect)
            .filter(ElderProspect.id == job.prospect_id)
            .first()
        )
        if prospect and prospect.converted_elder_id == elder_id:
            return True
    return False


def list_approved_visualizations_for_elder(
    db: Session,
    *,
    tenant_id: int,
    elder_id: int,
    limit: int = 24,
) -> list[dict]:
    """Human-approved, non-stub concept pairs visible to family."""
    jobs = (
        db.query(HomeSafetyAIJob)
        .filter(
            HomeSafetyAIJob.tenant_id == tenant_id,
            HomeSafetyAIJob.review_status == "approved",
            HomeSafetyAIJob.status == "completed",
            HomeSafetyAIJob.generated_document_id.isnot(None),
            HomeSafetyAIJob.source_document_id.isnot(None),
        )
        .order_by(HomeSafetyAIJob.id.desc())
        .limit(limit * 3)
        .all()
    )

    out: list[dict] = []
    from app.livewell.ai_visualization_service import HomeSafetyAIVisualizationService

    for job in jobs:
        if not _elder_matches_job(db, elder_id, job):
            continue
        concept = (
            db.query(Document)
            .filter(Document.id == job.generated_document_id)
            .first()
        )
        if not concept or concept.document_type != HOME_SAFETY_AI_CONCEPT:
            continue
        if _job_is_stub(job, concept):
            continue
        room = (job.room_type or "Room").replace("_", " ").title()
        package = (job.package_level or "").replace("_", " ").title()
        label = f"{room}" + (f" · {package}" if package else "")
        product_labels = HomeSafetyAIVisualizationService._job_product_labels(job)
        product_codes = HomeSafetyAIVisualizationService._job_product_codes(job)
        out.append(
            {
                "id": job.public_id,
                "room_type": job.room_type,
                "package_level": job.package_level,
                "label": label,
                "before_document_id": job.source_document_id,
                "after_document_id": job.generated_document_id,
                "before_url": f"/api/v1/home-safety/family/photos/{job.source_document_id}/image",
                "after_url": f"/api/v1/home-safety/family/photos/{job.generated_document_id}/image",
                "reviewed_at": job.reviewed_at,
                "assessment_id": job.assessment_id,
                "product_labels": product_labels,
                "product_codes": product_codes,
            }
        )
        if len(out) >= limit:
            break
    return out


def family_may_read_document(db: Session, *, elder_id: int, tenant_id: int, document_id: int) -> bool:
    """True if document is an assessment photo for the elder OR an approved concept pair image."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or doc.tenant_id != tenant_id:
        return False

    from app.livewell.document_types import HOME_SAFETY_PHOTO

    if doc.document_type == HOME_SAFETY_PHOTO:
        from app.livewell.visit_reports import is_family_hidden

        if is_family_hidden(doc):  # staff marked it internal
            return False
        if doc.entity_type == "elder" and doc.entity_id == elder_id:
            return True
        if doc.entity_type == "elder_prospect":
            prospect = (
                db.query(ElderProspect)
                .filter(ElderProspect.id == doc.entity_id)
                .first()
            )
            if prospect and prospect.converted_elder_id == elder_id:
                return True
        # Also allow if used as before-image on an approved family visualization
        job = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.source_document_id == document_id,
                HomeSafetyAIJob.review_status == "approved",
                HomeSafetyAIJob.status == "completed",
            )
            .first()
        )
        return bool(job and _elder_matches_job(db, elder_id, job))

    if doc.document_type == HOME_SAFETY_AI_CONCEPT:
        job = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.generated_document_id == document_id,
                HomeSafetyAIJob.review_status == "approved",
                HomeSafetyAIJob.status == "completed",
            )
            .first()
        )
        if not job or not _elder_matches_job(db, elder_id, job):
            return False
        return not _job_is_stub(job, doc)

    return False
