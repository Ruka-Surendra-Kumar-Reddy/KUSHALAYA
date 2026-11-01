import json
from datetime import datetime

from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.core.rbac import (
    ADMIN_ROLES,
    CARE_MANAGER,
    assert_tenant_access,
    resolve_tenant_id,
)
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.document import Document
from app.models.elder import Elder
from app.models.user import User
from app.schemas.document import (
    ALLOWED_MIME_TYPES,
    DOCUMENT_TYPES,
    ENTITY_TYPES,
    VERIFICATION_STATUSES,
    VerifyDocumentRequest,
)
from app.core.config import settings
from app.services.audit_service import AuditService

# Maps approved document types to caregiver verification fields
CAREGIVER_VERIFICATION_MAP = {
    "POLICE_VERIFICATION": "police_verification_status",
    "AADHAAR": "background_check_status",
    "PAN": "background_check_status",
    "PASSPORT": "background_check_status",
    "DRIVING_LICENSE": "background_check_status",
    "EMPLOYMENT_PROOF": None,
    "NURSING_CERTIFICATE": None,
    "FIRST_AID_CERTIFICATE": None,
    "CPR_CERTIFICATE": None,
    "OTHER_CERTIFICATE": None,
    "CERTIFICATE": None,
    "PHOTO": None,
}


class DocumentService:

    @staticmethod
    def _resolve_entity_tenant(
        db: Session,
        entity_type: str,
        entity_id: int,
    ) -> int:
        if entity_type == "caregiver":
            row = db.query(Caregiver).filter(Caregiver.id == entity_id).first()
        elif entity_type == "elder":
            row = db.query(Elder).filter(Elder.id == entity_id).first()
        elif entity_type == "elder_prospect":
            from app.models.elder_prospect import ElderProspect

            row = (
                db.query(ElderProspect)
                .filter(ElderProspect.id == entity_id)
                .first()
            )
        elif entity_type == "caregiver_prospect":
            row = (
                db.query(CaregiverProspect)
                .filter(CaregiverProspect.id == entity_id)
                .first()
            )
        elif entity_type == "tenant":
            from app.models.tenant import Tenant

            row = db.query(Tenant).filter(Tenant.id == entity_id).first()
        else:
            raise_bad_request(f"Invalid entity_type: {entity_type}")
        if not row:
            raise_not_found(f"{entity_type} not found")
        if entity_type == "tenant":
            return row.id
        return row.tenant_id

    @staticmethod
    def upload(
        db: Session,
        user: User,
        entity_type: str,
        entity_id: int,
        document_type: str,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> Document:
        entity_type = entity_type.lower()
        document_type = document_type.upper()

        if entity_type not in ENTITY_TYPES:
            raise_bad_request(f"entity_type must be one of: {', '.join(ENTITY_TYPES)}")
        if document_type not in DOCUMENT_TYPES:
            raise_bad_request(f"document_type must be one of: {', '.join(DOCUMENT_TYPES)}")
        allowed = set(ALLOWED_MIME_TYPES)
        if document_type == "RESUME":
            allowed.add("text/plain")
            allowed.add(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        if content_type not in allowed:
            raise_bad_request("File type not allowed. Use PDF, JPEG, or PNG.")

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise_bad_request(f"File exceeds {settings.MAX_UPLOAD_MB} MB limit")

        tenant_id = DocumentService._resolve_entity_tenant(db, entity_type, entity_id)
        assert_tenant_access(user, tenant_id)
        from app.core.team_scope import assert_entity_in_team

        assert_entity_in_team(db, user, entity_type, entity_id)

        storage = get_storage()
        storage_key, storage_url = storage.save(
            tenant_id,
            entity_type,
            entity_id,
            file_name,
            content,
            content_type,
        )

        doc = Document(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            document_type=document_type,
            document_name=file_name,
            file_name=file_name,
            storage_key=storage_key,
            storage_url=storage_url,
            mime_type=content_type,
            file_size_bytes=len(content),
            verification_status="PENDING",
            uploaded_by_user_id=user.id,
        )
        db.add(doc)
        db.flush()
        AuditService.log(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            entity_type="document",
            entity_id=doc.id,
            action="document_uploaded",
            new_value={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "document_type": document_type,
                "file_name": file_name,
            },
        )
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def list_for_entity(
        db: Session,
        user: User,
        entity_type: str,
        entity_id: int,
    ) -> list[Document]:
        entity_type = entity_type.lower()
        tenant_id = DocumentService._resolve_entity_tenant(db, entity_type, entity_id)
        assert_tenant_access(user, tenant_id)
        from app.core.team_scope import assert_entity_in_team

        assert_entity_in_team(db, user, entity_type, entity_id)

        return (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
            )
            .order_by(Document.uploaded_at.desc())
            .all()
        )

    @staticmethod
    def list_pending(db: Session, user: User, limit: int = 50) -> list[Document]:
        query = db.query(Document).filter(
            Document.verification_status == "PENDING"
        )
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Document.tenant_id == tid)
        from app.core.team_scope import entity_in_team, is_scoped_manager

        rows = query.order_by(Document.uploaded_at.asc()).limit(limit * 4 if is_scoped_manager(user) else limit).all()
        if is_scoped_manager(user):
            rows = [d for d in rows if entity_in_team(db, user, d.entity_type, d.entity_id)][:limit]
        return rows

    @staticmethod
    def get_document(db: Session, document_id: int, user: User) -> Document:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise_not_found("Document not found")
        assert_tenant_access(user, doc.tenant_id)
        from app.core.team_scope import assert_entity_in_team

        assert_entity_in_team(db, user, doc.entity_type, doc.entity_id)
        return doc

    @staticmethod
    def read_file(db: Session, document_id: int, user: User) -> tuple[bytes, str, str]:
        doc = DocumentService.get_document(db, document_id, user)
        AuditService.log(
            db,
            tenant_id=doc.tenant_id,
            user_id=user.id,
            entity_type="document",
            entity_id=doc.id,
            action="document_downloaded",
            new_value={"file_name": doc.file_name},
        )
        db.commit()
        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return content, mime or doc.mime_type or "application/octet-stream", doc.file_name

    @staticmethod
    def verify(
        db: Session,
        document_id: int,
        data: VerifyDocumentRequest,
        user: User,
    ) -> Document:
        if user.role not in ADMIN_ROLES | {CARE_MANAGER}:
            raise HTTPException(status_code=403, detail="Cannot verify documents")

        status = data.status.upper()
        if status not in {"APPROVED", "REJECTED"}:
            raise_bad_request("status must be APPROVED or REJECTED")
        if status == "REJECTED" and not data.rejection_reason:
            raise_bad_request("rejection_reason is required when rejecting")

        doc = DocumentService.get_document(db, document_id, user)
        if doc.verification_status != "PENDING":
            raise_bad_request("Document is already verified")

        doc.verification_status = status
        doc.verified_at = datetime.utcnow()
        doc.verified_by_user_id = user.id
        doc.rejection_reason = data.rejection_reason if status == "REJECTED" else None

        if status == "APPROVED" and doc.entity_type == "caregiver":
            DocumentService._sync_caregiver_verification(db, doc)

        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def _sync_caregiver_verification(db: Session, doc: Document) -> None:
        caregiver = (
            db.query(Caregiver)
            .filter(Caregiver.id == doc.entity_id)
            .first()
        )
        if not caregiver:
            return

        field = CAREGIVER_VERIFICATION_MAP.get(doc.document_type)
        if field:
            setattr(caregiver, field, "VERIFIED")

        attrs = dict(caregiver.custom_attributes or {})
        verified_docs = set(attrs.get("verified_documents", []))
        verified_docs.add(doc.document_type)
        attrs["verified_documents"] = sorted(verified_docs)
        caregiver.custom_attributes = attrs
        db.add(caregiver)

    @staticmethod
    def _detach_livewell_document_refs(db: Session, document_id: int) -> None:
        """Clear LiveWell FKs so a photo/concept document can be deleted."""
        from app.models.home_safety_ai_job import HomeSafetyAIJob
        from app.models.home_safety_vision_analysis import HomeSafetyVisionAnalysis

        (
            db.query(HomeSafetyAIJob)
            .filter(HomeSafetyAIJob.generated_document_id == document_id)
            .update(
                {
                    HomeSafetyAIJob.generated_document_id: None,
                    HomeSafetyAIJob.generated_image_url: None,
                },
                synchronize_session=False,
            )
        )
        # source_document_id is NOT NULL — remove jobs built from this photo.
        (
            db.query(HomeSafetyAIJob)
            .filter(HomeSafetyAIJob.source_document_id == document_id)
            .delete(synchronize_session=False)
        )
        (
            db.query(HomeSafetyVisionAnalysis)
            .filter(HomeSafetyVisionAnalysis.document_id == document_id)
            .delete(synchronize_session=False)
        )

    @staticmethod
    def delete_document(db: Session, document_id: int, user: User) -> None:
        if user.role not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="Only admins can delete documents")

        doc = DocumentService.get_document(db, document_id, user)
        AuditService.log(
            db,
            tenant_id=doc.tenant_id,
            user_id=user.id,
            entity_type="document",
            entity_id=doc.id,
            action="document_deleted",
            old_value={"file_name": doc.file_name, "document_type": doc.document_type},
        )
        DocumentService._detach_livewell_document_refs(db, document_id)
        storage = get_storage()
        try:
            storage.delete(doc.storage_key)
        except Exception:
            pass
        db.delete(doc)
        db.commit()

    @staticmethod
    def run_ocr(db: Session, document_id: int, user: User) -> Document:
        from app.services.document_intelligence_service import DocumentIntelligenceService

        doc = DocumentService.get_document(db, document_id, user)
        content, mime, _ = DocumentService.read_file(db, document_id, user)

        ocr_payload = DocumentIntelligenceService.extract_identity(
            content,
            mime,
            doc.document_type,
        )
        qr_payload = DocumentIntelligenceService.extract_qr_stub(doc.document_type)

        doc.ocr_extracted_json = ocr_payload
        doc.qr_extracted_json = qr_payload
        doc.qr_validation_status = qr_payload.get("status", "PENDING")
        doc.extraction_timestamp = datetime.utcnow()

        AuditService.log(
            db,
            tenant_id=doc.tenant_id,
            user_id=user.id,
            entity_type="document",
            entity_id=doc.id,
            action="document_ocr",
            new_value={"provider": ocr_payload.get("provider")},
        )
        db.commit()
        db.refresh(doc)
        return doc
