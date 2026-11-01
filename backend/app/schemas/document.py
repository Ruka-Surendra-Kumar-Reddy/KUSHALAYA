from datetime import datetime

from pydantic import BaseModel, Field


DOCUMENT_TYPES = frozenset({
    "AADHAAR",
    "PAN",
    "PASSPORT",
    "DRIVING_LICENSE",
    "POLICE_VERIFICATION",
    "EMPLOYMENT_PROOF",
    "NURSING_CERTIFICATE",
    "FIRST_AID_CERTIFICATE",
    "CPR_CERTIFICATE",
    "OTHER_CERTIFICATE",
    "CERTIFICATE",
    "PHOTO",
    "HOME_SAFETY_PHOTO",
    "HOME_SAFETY_AI_CONCEPT",
    "HOME_SAFETY_CATALOG_IMAGE",
    "HOME_SAFETY_SIGNED_DOC",
    "LW_SERVICE_AGREEMENT",
    "LW_PRIVACY_DPDP_CONSENT",
    "LW_PHOTO_VIDEO_AI_CONSENT",
    "LW_HEALTH_EMERGENCY_AUTH",
    "LW_HOME_ASSESSMENT_CONSENT",
    "LW_QUOTE_ACCEPTANCE",
    "LW_WORK_COMPLETION_CERT",
    "RESUME",
    # Client document vault (ops client profile → Documents).
    "LW_EMERGENCY_INFO_SHEET",
    "LW_FAMILY_MEDICAL",
    "LW_FAMILY_PRESCRIPTION",
    "LW_FAMILY_INSURANCE",
    "LW_FAMILY_IDENTITY",
    "LW_FAMILY_OTHER",
    "LW_STAFF_ONLY",
})

ENTITY_TYPES = frozenset({
    "caregiver",
    "elder",
    "elder_prospect",
    "caregiver_prospect",
    "tenant",
})

VERIFICATION_STATUSES = frozenset({"PENDING", "APPROVED", "REJECTED"})

ALLOWED_MIME_TYPES = frozenset({
    "application/pdf",
    "image/jpeg",
    "image/png",
})


class DocumentResponse(BaseModel):
    id: int
    tenant_id: int | None = None
    entity_type: str
    entity_id: int
    document_type: str
    document_name: str | None = None
    file_name: str
    mime_type: str | None
    file_size_bytes: int | None
    verification_status: str
    rejection_reason: str | None
    verified_at: datetime | None
    uploaded_at: datetime
    has_ocr: bool = False
    has_qr: bool = False
    qr_validation_status: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_document(cls, doc) -> "DocumentResponse":
        return cls(
            id=doc.id,
            tenant_id=doc.tenant_id,
            entity_type=doc.entity_type,
            entity_id=doc.entity_id,
            document_type=doc.document_type,
            document_name=doc.document_name,
            file_name=doc.file_name,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            verification_status=doc.verification_status,
            rejection_reason=doc.rejection_reason,
            verified_at=doc.verified_at,
            uploaded_at=doc.uploaded_at,
            has_ocr=bool(doc.ocr_extracted_json),
            has_qr=bool(doc.qr_extracted_json),
            qr_validation_status=doc.qr_validation_status,
        )


class VerifyDocumentRequest(BaseModel):
    status: str = Field(description="APPROVED or REJECTED")
    rejection_reason: str | None = None
