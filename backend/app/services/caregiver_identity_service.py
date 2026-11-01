from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.identity_utils import aadhaar_last4, mask_aadhaar
from app.core.rbac import assert_tenant_access
from app.core.responses import raise_bad_request, raise_not_found
from app.models.caregiver import Caregiver
from app.models.caregiver_identity import CaregiverIdentity
from app.models.document import Document
from app.models.user import User
from app.schemas.caregiver_identity import (
    DocumentExtractionUpdate,
    IdentityConfirmRequest,
    IdentityDocumentSummary,
)
from app.services.audit_service import AuditService


class CaregiverIdentityService:

    @staticmethod
    def _get_caregiver(db: Session, caregiver_id: int, user: User) -> Caregiver:
        caregiver = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        if not caregiver:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, caregiver.tenant_id)
        return caregiver

    @staticmethod
    def get_identity(db: Session, caregiver_id: int, user: User) -> dict:
        caregiver = CaregiverIdentityService._get_caregiver(db, caregiver_id, user)
        identity = (
            db.query(CaregiverIdentity)
            .filter(CaregiverIdentity.caregiver_id == caregiver.id)
            .first()
        )

        docs = (
            db.query(Document)
            .filter(
                Document.entity_type == "caregiver",
                Document.entity_id == caregiver.id,
            )
            .order_by(Document.uploaded_at.desc())
            .all()
        )

        doc_summaries = [
            IdentityDocumentSummary(
                id=d.id,
                document_type=d.document_type,
                document_name=d.document_name,
                file_name=d.file_name,
                verification_status=d.verification_status,
                uploaded_at=d.uploaded_at,
                has_ocr=bool(d.ocr_extracted_json),
                has_qr=bool(d.qr_extracted_json),
            )
            for d in docs
        ]

        ocr_hints = CaregiverIdentityService._ocr_hints_from_documents(docs)

        if identity:
            out = CaregiverIdentityService._identity_dict(identity, doc_summaries)
            out["ocr_hints"] = ocr_hints
            return out

        out = CaregiverIdentityService._draft_from_caregiver(
            caregiver,
            doc_summaries,
        )
        out["ocr_hints"] = ocr_hints
        return out

    @staticmethod
    def _draft_from_caregiver(caregiver: Caregiver, docs: list) -> dict:
        return {
            "caregiver_id": caregiver.id,
            "full_name": f"{caregiver.first_name} {caregiver.last_name}".strip(),
            "gender": None,
            "date_of_birth": None,
            "mobile_number": caregiver.phone,
            "email": caregiver.email,
            "address_line1": None,
            "address_line2": None,
            "city": None,
            "district": None,
            "state": None,
            "postal_code": None,
            "aadhaar_masked": mask_aadhaar(caregiver.aadhaar_number),
            "aadhaar_last4": aadhaar_last4(caregiver.aadhaar_number),
            "aadhaar_vid": None,
            "verification_status": "PENDING",
            "qr_validation_status": None,
            "user_confirmed_at": None,
            "verified_at": None,
            "identity_consent_at": None,
            "primary_aadhaar_document_id": CaregiverIdentityService._latest_aadhaar_doc_id(
                docs
            ),
            "documents": docs,
        }

    @staticmethod
    def _ocr_hints_from_documents(docs: list) -> dict:
        for d in sorted(docs, key=lambda x: x.uploaded_at, reverse=True):
            if d.document_type == "AADHAAR" and d.ocr_extracted_json:
                return dict(d.ocr_extracted_json)
        return {}

    @staticmethod
    def _latest_aadhaar_doc_id(docs: list) -> int | None:
        for d in sorted(docs, key=lambda x: x.uploaded_at, reverse=True):
            if d.document_type == "AADHAAR":
                return d.id
        return None

    @staticmethod
    def _identity_dict(identity: CaregiverIdentity, docs: list) -> dict:
        masked = (
            f"XXXX-XXXX-{identity.aadhaar_last4}"
            if identity.aadhaar_last4
            else None
        )
        return {
            "caregiver_id": identity.caregiver_id,
            "full_name": identity.full_name,
            "gender": identity.gender,
            "date_of_birth": identity.date_of_birth,
            "mobile_number": identity.mobile_number,
            "email": identity.email,
            "address_line1": identity.address_line1,
            "address_line2": identity.address_line2,
            "city": identity.city,
            "district": identity.district,
            "state": identity.state,
            "postal_code": identity.postal_code,
            "aadhaar_masked": masked,
            "aadhaar_last4": identity.aadhaar_last4,
            "aadhaar_vid": identity.aadhaar_vid,
            "verification_status": identity.verification_status,
            "qr_validation_status": identity.qr_validation_status,
            "user_confirmed_at": identity.user_confirmed_at,
            "verified_at": identity.verified_at,
            "identity_consent_at": identity.identity_consent_at,
            "primary_aadhaar_document_id": identity.primary_aadhaar_document_id,
            "documents": docs,
            "ocr_hints": {},
        }

    @staticmethod
    def confirm_identity(
        db: Session,
        caregiver_id: int,
        data: IdentityConfirmRequest,
        user: User,
    ) -> dict:
        if not data.identity_consent:
            raise_bad_request("identity_consent is required to submit identity")

        caregiver = CaregiverIdentityService._get_caregiver(db, caregiver_id, user)
        last4 = aadhaar_last4(data.aadhaar_number)

        identity = (
            db.query(CaregiverIdentity)
            .filter(CaregiverIdentity.caregiver_id == caregiver.id)
            .first()
        )
        if not identity:
            identity = CaregiverIdentity(
                tenant_id=caregiver.tenant_id,
                caregiver_id=caregiver.id,
            )
            db.add(identity)

        identity.full_name = data.full_name.strip()
        identity.gender = data.gender
        identity.date_of_birth = data.date_of_birth
        identity.mobile_number = data.mobile_number
        identity.email = data.email
        identity.address_line1 = data.address_line1
        identity.address_line2 = data.address_line2
        identity.city = data.city
        identity.district = data.district
        identity.state = data.state
        identity.postal_code = data.postal_code
        identity.aadhaar_last4 = last4
        identity.aadhaar_vid = data.aadhaar_vid
        identity.primary_aadhaar_document_id = data.primary_aadhaar_document_id
        identity.verification_status = "SUBMITTED"
        identity.user_confirmed_at = datetime.now(timezone.utc)
        identity.identity_consent_at = identity.user_confirmed_at
        identity.notes = data.notes

        if data.primary_aadhaar_document_id:
            doc = db.query(Document).filter(Document.id == data.primary_aadhaar_document_id).first()
            if not doc or doc.entity_id != caregiver.id:
                raise_bad_request("Invalid primary_aadhaar_document_id")

        parts = data.full_name.strip().split(None, 1)
        caregiver.first_name = parts[0]
        caregiver.last_name = parts[1] if len(parts) > 1 else ""
        caregiver.phone = data.mobile_number or caregiver.phone
        caregiver.email = data.email or caregiver.email
        caregiver.aadhaar_number = mask_aadhaar(data.aadhaar_number) or caregiver.aadhaar_number

        AuditService.log(
            db,
            tenant_id=caregiver.tenant_id,
            user_id=user.id,
            entity_type="caregiver",
            entity_id=caregiver.id,
            action="identity_confirmed",
            new_value={
                "verification_status": "SUBMITTED",
                "aadhaar_last4": last4,
            },
        )

        db.commit()
        db.refresh(identity)
        return CaregiverIdentityService.get_identity(db, caregiver_id, user)

    @staticmethod
    def update_document_extraction(
        db: Session,
        document_id: int,
        data: DocumentExtractionUpdate,
        user: User,
    ) -> Document:
        from app.services.document_service import DocumentService

        doc = DocumentService.get_document(db, document_id, user)
        if doc.entity_type != "caregiver":
            raise_bad_request("Extraction updates apply to caregiver documents only")

        if data.ocr_extracted_json is not None:
            doc.ocr_extracted_json = data.ocr_extracted_json
        if data.qr_extracted_json is not None:
            doc.qr_extracted_json = data.qr_extracted_json
        if data.qr_validation_status is not None:
            doc.qr_validation_status = data.qr_validation_status
        if data.document_name is not None:
            doc.document_name = data.document_name
        doc.extraction_timestamp = datetime.now(timezone.utc)

        AuditService.log(
            db,
            tenant_id=doc.tenant_id,
            user_id=user.id,
            entity_type="document",
            entity_id=doc.id,
            action="extraction_updated",
            new_value={"document_type": doc.document_type},
        )
        db.commit()
        db.refresh(doc)
        return doc
