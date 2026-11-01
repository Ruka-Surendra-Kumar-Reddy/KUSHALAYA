from datetime import date, datetime

from pydantic import BaseModel, Field


class QualificationPackResponse(BaseModel):
    id: int
    qualification_pack_code: str
    qualification_name: str
    sector_skill_council: str
    nsqf_level: int | None
    description: str | None
    status: str

    model_config = {"from_attributes": True}


class TrainingProgramResponse(BaseModel):
    id: int
    code: str
    name: str
    qualification_pack_code: str | None
    description: str | None
    status: str

    model_config = {"from_attributes": True}


class CertificationCreate(BaseModel):
    certification_name: str
    issuing_body: str
    qualification_pack_code: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    certificate_number: str | None = None
    certificate_url: str | None = None
    document_id: int | None = None


class CertificationUpdate(BaseModel):
    certification_name: str | None = None
    issuing_body: str | None = None
    qualification_pack_code: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    certificate_number: str | None = None
    certificate_url: str | None = None
    verification_status: str | None = None


class CertificationResponse(BaseModel):
    id: int
    caregiver_id: int
    certification_name: str
    qualification_pack_code: str | None
    issuing_body: str
    issue_date: date | None
    expiry_date: date | None
    certificate_number: str | None
    certificate_url: str | None
    document_id: int | None
    verification_status: str
    is_expired: bool = False

    model_config = {"from_attributes": True}


class EnrollmentResponse(BaseModel):
    id: int
    program_id: int
    program_code: str
    program_name: str
    status: str
    assessment_score: float | None

    model_config = {"from_attributes": True}


class EnrollProgramRequest(BaseModel):
    program_code: str


class CompleteProgramRequest(BaseModel):
    assessment_score: float | None = Field(default=None, ge=0, le=100)


class ReadinessBreakdown(BaseModel):
    verification: float
    training: float
    assessment: float
    practical: float
    conduct: float


class ReadinessResponse(BaseModel):
    caregiver_id: int
    readiness_score: float
    readiness_band: str
    breakdown: ReadinessBreakdown
    recommendations: list[str] = []


class EmployabilityResponse(BaseModel):
    caregiver_id: int
    employability_score: float
    recognized_certification: float
    readiness_component: float
    verification_component: float
    experience: float
    language: float
    market_demand: float


class MarketplaceCaregiver(BaseModel):
    id: int
    first_name: str
    last_name: str
    years_experience: int | None
    readiness_score: float
    readiness_band: str
    employability_score: float
    verification_status_summary: str
    languages: list[str] = []


class AcademyStubUpdate(BaseModel):
    """Phase A: manager attestation for practical/conduct until full LMS."""
    practical_score: float | None = Field(default=None, ge=0, le=20)
    conduct_score: float | None = Field(default=None, ge=0, le=10)
