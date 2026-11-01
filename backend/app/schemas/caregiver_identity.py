from datetime import date, datetime

from pydantic import BaseModel, Field


IDENTITY_STATUSES = frozenset({"PENDING", "SUBMITTED", "VERIFIED", "REJECTED"})


class DocumentExtractionUpdate(BaseModel):
    ocr_extracted_json: dict | None = None
    qr_extracted_json: dict | None = None
    qr_validation_status: str | None = None
    document_name: str | None = None


class IdentityConfirmRequest(BaseModel):
    """User-reviewed identity (Phase B — manual confirm before OCR automation)."""

    full_name: str
    gender: str | None = None
    date_of_birth: date | None = None
    mobile_number: str | None = None
    email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    postal_code: str | None = None
    aadhaar_number: str | None = Field(
        default=None,
        description="Full Aadhaar accepted once at confirm; only last4 stored",
    )
    aadhaar_vid: str | None = None
    primary_aadhaar_document_id: int | None = None
    identity_consent: bool = False
    notes: str | None = None


class IdentityDocumentSummary(BaseModel):
    id: int
    document_type: str
    document_name: str | None
    file_name: str
    verification_status: str
    uploaded_at: datetime
    has_ocr: bool
    has_qr: bool

    model_config = {"from_attributes": True}


class CaregiverIdentityResponse(BaseModel):
    caregiver_id: int
    ocr_hints: dict = Field(
        default_factory=dict,
        description="Suggested values from document OCR JSON (manual review)",
    )
    full_name: str | None
    gender: str | None
    date_of_birth: date | None
    mobile_number: str | None
    email: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    district: str | None
    state: str | None
    postal_code: str | None
    aadhaar_masked: str | None
    aadhaar_last4: str | None
    aadhaar_vid: str | None
    verification_status: str
    qr_validation_status: str | None
    user_confirmed_at: datetime | None
    verified_at: datetime | None
    identity_consent_at: datetime | None
    primary_aadhaar_document_id: int | None
    documents: list[IdentityDocumentSummary] = []
