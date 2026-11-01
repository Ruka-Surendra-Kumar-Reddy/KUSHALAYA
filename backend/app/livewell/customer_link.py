"""Resolve and validate prospect/elder ownership for SafeHome artifacts."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.document_types import HOME_SAFETY_PHOTO
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord


class HomeSafetyCustomerLink:

    @staticmethod
    def customer_from_document(doc: Document) -> tuple[int | None, int | None]:
        if doc.entity_type == "elder":
            return None, doc.entity_id
        if doc.entity_type == "elder_prospect":
            return doc.entity_id, None
        return None, None

    @staticmethod
    def validate_prospect(db: Session, tenant_id: int, prospect_id: int) -> ElderProspect:
        row = (
            db.query(ElderProspect)
            .filter(
                ElderProspect.id == prospect_id,
                ElderProspect.tenant_id == tenant_id,
            )
            .first()
        )
        if not row:
            raise_bad_request("Prospect not found for this organization")
        return row

    @staticmethod
    def validate_elder(db: Session, tenant_id: int, elder_id: int) -> Elder:
        row = (
            db.query(Elder)
            .filter(Elder.id == elder_id, Elder.tenant_id == tenant_id)
            .first()
        )
        if not row:
            raise_bad_request("Client not found for this organization")
        return row

    @staticmethod
    def assessment_record(
        db: Session,
        tenant_id: int,
        assessment_id: str,
    ) -> HomeSafetyAssessmentRecord | None:
        if not assessment_id.strip():
            return None
        return (
            db.query(HomeSafetyAssessmentRecord)
            .filter(
                HomeSafetyAssessmentRecord.tenant_id == tenant_id,
                HomeSafetyAssessmentRecord.assessment_id == assessment_id.strip(),
            )
            .first()
        )

    @staticmethod
    def assessment_customer_ids(row: HomeSafetyAssessmentRecord | None) -> tuple[int | None, int | None]:
        if not row:
            return None, None
        prospect_id = row.prospect_id
        elder_id = row.elder_id
        payload = row.payload or {}
        if prospect_id is None:
            raw = payload.get("prospectId")
            prospect_id = int(raw) if raw is not None else None
        if elder_id is None:
            raw = payload.get("elderId")
            elder_id = int(raw) if raw is not None else None
        return prospect_id, elder_id

    @staticmethod
    def resolve_customer(
        db: Session,
        tenant_id: int,
        *,
        prospect_id: int | None = None,
        elder_id: int | None = None,
        assessment_id: str | None = None,
        source_document_id: int | None = None,
        require: bool = True,
    ) -> tuple[int | None, int | None]:
        resolved_prospect = prospect_id
        resolved_elder = elder_id

        if assessment_id:
            row = HomeSafetyCustomerLink.assessment_record(db, tenant_id, assessment_id)
            a_prospect, a_elder = HomeSafetyCustomerLink.assessment_customer_ids(row)
            if resolved_prospect is None:
                resolved_prospect = a_prospect
            if resolved_elder is None:
                resolved_elder = a_elder

        if source_document_id:
            doc = (
                db.query(Document)
                .filter(
                    Document.id == source_document_id,
                    Document.tenant_id == tenant_id,
                    Document.document_type == HOME_SAFETY_PHOTO,
                )
                .first()
            )
            if not doc:
                raise_not_found("Assessment photo not found")
            d_prospect, d_elder = HomeSafetyCustomerLink.customer_from_document(doc)
            if resolved_prospect is None:
                resolved_prospect = d_prospect
            if resolved_elder is None:
                resolved_elder = d_elder

        if resolved_prospect is not None:
            HomeSafetyCustomerLink.validate_prospect(db, tenant_id, resolved_prospect)
        if resolved_elder is not None:
            HomeSafetyCustomerLink.validate_elder(db, tenant_id, resolved_elder)

        if resolved_prospect and resolved_elder:
            prospect = (
                db.query(ElderProspect)
                .filter(ElderProspect.id == resolved_prospect)
                .first()
            )
            if prospect and prospect.converted_elder_id and prospect.converted_elder_id != resolved_elder:
                raise_bad_request("Prospect and client record do not match")

        if require and not resolved_prospect and not resolved_elder:
            raise_bad_request(
                "Link this assessment to a prospect client before saving photos or AI prompts"
            )

        return resolved_prospect, resolved_elder

    @staticmethod
    def assert_same_customer(
        *,
        prospect_id: int | None,
        elder_id: int | None,
        other_prospect_id: int | None,
        other_elder_id: int | None,
        label: str = "artifact",
    ) -> None:
        if prospect_id and other_prospect_id and prospect_id != other_prospect_id:
            raise_bad_request(f"{label} belongs to a different prospect client")
        if elder_id and other_elder_id and elder_id != other_elder_id:
            raise_bad_request(f"{label} belongs to a different client")

    @staticmethod
    def assert_photo_belongs_to_customer(
        db: Session,
        tenant_id: int,
        document_id: int,
        *,
        prospect_id: int | None,
        elder_id: int | None,
    ) -> Document:
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
            raise_not_found("Assessment photo not found")
        d_prospect, d_elder = HomeSafetyCustomerLink.customer_from_document(doc)
        HomeSafetyCustomerLink.assert_same_customer(
            prospect_id=prospect_id,
            elder_id=elder_id,
            other_prospect_id=d_prospect,
            other_elder_id=d_elder,
            label="Photo",
        )
        return doc

    @staticmethod
    def sync_assessment_customer_columns(
        row: HomeSafetyAssessmentRecord,
        payload: dict,
    ) -> tuple[int | None, int | None]:
        raw_prospect = payload.get("prospectId")
        raw_elder = payload.get("elderId")
        prospect_id = int(raw_prospect) if raw_prospect is not None else None
        elder_id = int(raw_elder) if raw_elder is not None else None
        row.prospect_id = prospect_id
        row.elder_id = elder_id
        return prospect_id, elder_id

    @staticmethod
    def validate_assessment_photos(
        db: Session,
        tenant_id: int,
        *,
        photos: list[dict],
        prospect_id: int | None,
        elder_id: int | None,
    ) -> None:
        if not prospect_id and not elder_id:
            return
        for photo in photos or []:
            document_id = photo.get("documentId")
            if not document_id:
                continue
            HomeSafetyCustomerLink.assert_photo_belongs_to_customer(
                db,
                tenant_id,
                int(document_id),
                prospect_id=prospect_id,
                elder_id=elder_id,
            )

    @staticmethod
    def backfill_ai_jobs_for_assessment(
        db: Session,
        tenant_id: int,
        assessment_id: str,
        *,
        prospect_id: int | None,
        elder_id: int | None,
    ) -> None:
        if not prospect_id and not elder_id:
            return
        jobs = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == assessment_id,
            )
            .all()
        )
        for job in jobs:
            if prospect_id and not job.prospect_id:
                job.prospect_id = prospect_id
            if elder_id and not job.elder_id:
                job.elder_id = elder_id
