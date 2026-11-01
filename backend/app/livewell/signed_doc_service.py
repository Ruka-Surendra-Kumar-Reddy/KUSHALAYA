"""Wet-signed customer document scans — linked to elder/prospect + assessment."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.livewell.document_types import SIGNED_DOC_FORM_CODES
from app.models.document import Document
from app.models.user import User
from app.services.document_service import DocumentService

TEMPLATE_VERSION = "2026.07-HYD"


class HomeSafetySignedDocService:

    @staticmethod
    def upload(
        db: Session,
        user: User,
        *,
        file_name: str,
        content: bytes,
        content_type: str,
        form_code: str,
        assessment_id: str | None,
        prospect_id: int | None,
        elder_id: int | None,
        notes: str | None = None,
        signed_at: str | None = None,
    ) -> Document:
        form_code = (form_code or "").strip().upper()
        if form_code not in SIGNED_DOC_FORM_CODES:
            raise_bad_request(
                f"form_code must be one of: {', '.join(sorted(SIGNED_DOC_FORM_CODES))}"
            )
        if not prospect_id and not elder_id:
            raise_bad_request("prospect_id or elder_id is required")

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

        if elder_id:
            entity_type = "elder"
            entity_id = elder_id
        else:
            entity_type = "elder_prospect"
            entity_id = prospect_id  # type: ignore[assignment]

        # The assessment link is kept in metadata, not in the visible name.
        label = form_code.replace("_", " ").title()[:255]

        doc = DocumentService.upload(
            db,
            user,
            entity_type,
            entity_id,
            form_code,
            file_name,
            content,
            content_type,
        )
        doc.document_name = label
        doc.verification_status = "APPROVED"
        doc.verified_at = datetime.now(timezone.utc)
        meta: dict = {
            "form_code": form_code,
            "template_version": TEMPLATE_VERSION,
            "signature_method": "paper_scan",
            "signature_status": "captured",
            "packet": HomeSafetySignedDocService.packet_for(form_code),
        }
        if assessment_id:
            meta["assessment_id"] = assessment_id
        if notes and notes.strip():
            meta["notes"] = notes.strip()[:2000]
        if signed_at and signed_at.strip():
            meta["signed_at"] = signed_at.strip()
        else:
            meta["signed_at"] = datetime.now(timezone.utc).isoformat()
        meta["assessor_user_id"] = user.id
        doc.ocr_extracted_json = meta
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def packet_for(form_code: str) -> str:
        if form_code in {
            "LW_SERVICE_AGREEMENT",
            "LW_PRIVACY_DPDP_CONSENT",
            "LW_PHOTO_VIDEO_AI_CONSENT",
            "LW_HEALTH_EMERGENCY_AUTH",
        }:
            return "enrollment"
        if form_code == "LW_HOME_ASSESSMENT_CONSENT":
            return "assessment"
        if form_code == "LW_QUOTE_ACCEPTANCE":
            return "installation"
        if form_code == "LW_WORK_COMPLETION_CERT":
            return "completion"
        return "other"

    @staticmethod
    def list_for_assessment(
        db: Session,
        user: User,
        *,
        assessment_id: str,
    ) -> list[Document]:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        assert_tenant_access(user, tid)

        rows = (
            db.query(Document)
            .filter(
                Document.tenant_id == tid,
                Document.document_type.in_(SIGNED_DOC_FORM_CODES),
            )
            .order_by(Document.uploaded_at.desc())
            .limit(200)
            .all()
        )
        matched: list[Document] = []
        for doc in rows:
            meta = doc.ocr_extracted_json if isinstance(doc.ocr_extracted_json, dict) else {}
            if meta.get("assessment_id") == assessment_id:
                matched.append(doc)
        return matched

    @staticmethod
    def read_for_staff(
        db: Session,
        user: User,
        document_id: int,
    ) -> tuple[bytes, str, str]:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_not_found("Document not found")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if (
            not doc
            or doc.tenant_id != tid
            or doc.document_type not in SIGNED_DOC_FORM_CODES
        ):
            raise_not_found("Document not found")
        assert_tenant_access(user, doc.tenant_id)
        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return (
            content,
            mime or doc.mime_type or "application/octet-stream",
            doc.file_name,
        )

    @staticmethod
    def to_dict(doc: Document) -> dict:
        meta = doc.ocr_extracted_json if isinstance(doc.ocr_extracted_json, dict) else {}
        return {
            "id": doc.id,
            "document_type": doc.document_type,
            "form_code": meta.get("form_code") or doc.document_type,
            "document_name": doc.document_name or doc.file_name,
            "file_name": doc.file_name,
            "mime_type": doc.mime_type,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "template_version": meta.get("template_version"),
            "signature_method": meta.get("signature_method"),
            "signature_status": meta.get("signature_status"),
            "signed_at": meta.get("signed_at"),
            "assessment_id": meta.get("assessment_id"),
            "notes": meta.get("notes"),
            "packet": meta.get("packet"),
            "url": f"/api/v1/home-safety/signed-docs/{doc.id}/file",
        }
