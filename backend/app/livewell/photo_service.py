"""Home safety assessment photos — linked to elder or prospect for family app."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.user import User
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.livewell.document_types import HOME_SAFETY_AI_CONCEPT, HOME_SAFETY_PHOTO

STAFF_IMAGE_TYPES = frozenset({HOME_SAFETY_PHOTO, HOME_SAFETY_AI_CONCEPT})
from app.services.document_service import DocumentService
from app.services.elder_portal_service import ElderPortalService


class HomeSafetyPhotoService:

    @staticmethod
    def _auto_approve_family_photo(doc: Document) -> None:
        doc.verification_status = "APPROVED"
        doc.verified_at = datetime.now(timezone.utc)

    @staticmethod
    def upload(
        db: Session,
        user: User,
        *,
        file_name: str,
        content: bytes,
        content_type: str,
        caption: str | None,
        assessment_id: str | None,
        prospect_id: int | None,
        elder_id: int | None,
        room_type: str | None = None,
    ) -> Document:
        if not prospect_id and not elder_id:
            raise_bad_request("prospect_id or elder_id is required")

        from app.core.rbac import resolve_tenant_id

        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")

        if assessment_id:
            row = HomeSafetyCustomerLink.assessment_record(db, tid, assessment_id)
            a_prospect, a_elder = HomeSafetyCustomerLink.assessment_customer_ids(row)
            if a_prospect or a_elder:
                HomeSafetyCustomerLink.assert_same_customer(
                    prospect_id=prospect_id,
                    elder_id=elder_id,
                    other_prospect_id=a_prospect,
                    other_elder_id=a_elder,
                    label="Assessment",
                )

        if prospect_id:
            HomeSafetyCustomerLink.validate_prospect(db, tid, prospect_id)
        if elder_id:
            HomeSafetyCustomerLink.validate_elder(db, tid, elder_id)

        entity_type: str
        entity_id: int
        if elder_id:
            entity_type = "elder"
            entity_id = elder_id
        else:
            entity_type = "elder_prospect"
            entity_id = prospect_id  # type: ignore[assignment]

        # The assessment link lives in the document metadata below; the id is
        # not appended to the visible name any more.
        label = (caption or "Home safety photo").strip()[:255]

        doc = DocumentService.upload(
            db,
            user,
            entity_type,
            entity_id,
            HOME_SAFETY_PHOTO,
            file_name,
            content,
            content_type,
        )
        doc.document_name = label
        meta: dict = {}
        if assessment_id:
            meta["assessment_id"] = assessment_id
        if room_type:
            meta["room_type"] = room_type.strip().lower()
        if meta:
            doc.ocr_extracted_json = meta
        HomeSafetyPhotoService._auto_approve_family_photo(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def _prospect_ids_for_elder(db: Session, elder_id: int) -> list[int]:
        rows = (
            db.query(ElderProspect.id)
            .filter(ElderProspect.converted_elder_id == elder_id)
            .all()
        )
        return [r[0] for r in rows]

    @staticmethod
    def photo_metadata(doc: Document) -> dict:
        raw = doc.ocr_extracted_json
        return dict(raw) if isinstance(raw, dict) else {}

    @staticmethod
    def list_for_elder(db: Session, elder_id: int, *, limit: int = 100) -> list[Document]:
        from sqlalchemy import and_, or_

        prospect_ids = HomeSafetyPhotoService._prospect_ids_for_elder(db, elder_id)
        query = db.query(Document).filter(
            Document.document_type == HOME_SAFETY_PHOTO,
            Document.verification_status == "APPROVED",
        )
        clauses = [and_(Document.entity_type == "elder", Document.entity_id == elder_id)]
        if prospect_ids:
            clauses.append(
                and_(
                    Document.entity_type == "elder_prospect",
                    Document.entity_id.in_(prospect_ids),
                )
            )
        query = query.filter(or_(*clauses))
        return query.order_by(Document.uploaded_at.desc()).limit(limit).all()

    @staticmethod
    def list_for_family_user(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        docs = HomeSafetyPhotoService.list_for_elder(db, elder.id)
        return [
            {
                "id": d.id,
                "caption": d.document_name or d.file_name,
                "url": f"/api/v1/home-safety/family/photos/{d.id}/image",
                "taken_at": d.uploaded_at,
                "source": "assessment",
                "room_type": HomeSafetyPhotoService.photo_metadata(d).get("room_type"),
            }
            for d in docs
        ]

    @staticmethod
    def read_for_family_user(
        db: Session,
        user: User,
        document_id: int,
    ) -> tuple[bytes, str, str]:
        from app.livewell.family_visualizations import family_may_read_document

        elder = ElderPortalService.get_linked_elder(db, user)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise_not_found("Photo not found")

        if not family_may_read_document(
            db,
            elder_id=elder.id,
            tenant_id=elder.tenant_id,
            document_id=document_id,
        ):
            raise_not_found("Photo not found")

        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return (
            content,
            mime or doc.mime_type or "application/octet-stream",
            doc.file_name,
        )

    @staticmethod
    def read_for_staff(
        db: Session,
        user: User,
        document_id: int,
    ) -> tuple[bytes, str, str]:
        from app.core.rbac import assert_tenant_access, resolve_tenant_id

        tid = resolve_tenant_id(user)
        if tid is None:
            raise_not_found("Photo not found")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if (
            not doc
            or doc.document_type not in STAFF_IMAGE_TYPES
            or doc.tenant_id != tid
        ):
            raise_not_found("Photo not found")
        assert_tenant_access(user, doc.tenant_id)
        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return (
            content,
            mime or doc.mime_type or "application/octet-stream",
            doc.file_name,
        )

    @staticmethod
    def prospect_elder_id(db: Session, prospect_id: int) -> int | None:
        row = (
            db.query(ElderProspect.converted_elder_id)
            .filter(ElderProspect.id == prospect_id)
            .first()
        )
        return row[0] if row else None

    @staticmethod
    def delete_for_assessment(
        db: Session,
        *,
        tenant_id: int,
        assessment_id: str,
        payload: dict | None = None,
    ) -> None:
        """Delete assessment photos/concepts from DB and object storage.

        Also removes AI jobs and vision analyses that reference those assets so
        foreign keys do not block document deletion.
        """
        from app.models.home_safety_ai_job import HomeSafetyAIJob
        from app.models.home_safety_vision_analysis import HomeSafetyVisionAnalysis

        payload_doc_ids: set[int] = set()
        for photo in (payload or {}).get("photos") or []:
            raw_id = photo.get("documentId") if isinstance(photo, dict) else None
            if raw_id is None:
                continue
            try:
                payload_doc_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue

        candidates = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.document_type.in_(
                    [HOME_SAFETY_PHOTO, HOME_SAFETY_AI_CONCEPT]
                ),
            )
            .all()
        )
        to_delete = [
            doc
            for doc in candidates
            if doc.id in payload_doc_ids
            or HomeSafetyPhotoService.photo_metadata(doc).get("assessment_id")
            == assessment_id
        ]
        doc_ids = [doc.id for doc in to_delete]

        (
            db.query(HomeSafetyVisionAnalysis)
            .filter(
                HomeSafetyVisionAnalysis.tenant_id == tenant_id,
                HomeSafetyVisionAnalysis.assessment_id == assessment_id,
            )
            .delete(synchronize_session=False)
        )
        if doc_ids:
            (
                db.query(HomeSafetyVisionAnalysis)
                .filter(HomeSafetyVisionAnalysis.document_id.in_(doc_ids))
                .delete(synchronize_session=False)
            )

        (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == assessment_id,
            )
            .delete(synchronize_session=False)
        )
        if doc_ids:
            (
                db.query(HomeSafetyAIJob)
                .filter(HomeSafetyAIJob.generated_document_id.in_(doc_ids))
                .update(
                    {
                        HomeSafetyAIJob.generated_document_id: None,
                        HomeSafetyAIJob.generated_image_url: None,
                    },
                    synchronize_session=False,
                )
            )
            (
                db.query(HomeSafetyAIJob)
                .filter(HomeSafetyAIJob.source_document_id.in_(doc_ids))
                .delete(synchronize_session=False)
            )

        storage = get_storage()
        for doc in to_delete:
            try:
                storage.delete(doc.storage_key)
            except Exception:
                pass
            db.delete(doc)
