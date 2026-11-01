from datetime import datetime

from pydantic import BaseModel, Field


class PipelineStagesResponse(BaseModel):
    elder_stages: list[str]
    caregiver_stages: list[str]


class AssignableOwner(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str


class ElderProspectBase(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    source: str | None = None
    stage: str = "NEW"
    owner_user_id: int | None = None
    next_follow_up_at: datetime | None = None
    lost_reason: str | None = None
    notes: str | None = None
    care_level: str | None = None


class ElderProspectCreate(ElderProspectBase):
    tenant_id: int | None = None


class ElderProspectUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    source: str | None = None
    stage: str | None = None
    owner_user_id: int | None = None
    next_follow_up_at: datetime | None = None
    lost_reason: str | None = None
    notes: str | None = None
    care_level: str | None = None
    status: str | None = None


class ElderProspectResponse(ElderProspectBase):
    id: int
    tenant_id: int
    status: str
    converted_elder_id: int | None
    owner_name: str | None = None
    created_at: datetime
    updated_at: datetime
    # Website lead tracking (FIX 107/108)
    lead_source: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    referrer_url: str | None = None
    landing_page: str | None = None
    referral_code: str | None = None
    referred_by: str | None = None
    pincode: str | None = None
    area_served: bool | None = None
    assessment_slot: str | None = None
    assessment_fee_paise: int | None = None
    assessment_paid: bool = False

    model_config = {"from_attributes": True}


class CaregiverProspectBase(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    source: str | None = None
    stage: str = "APPLIED"
    owner_user_id: int | None = None
    next_follow_up_at: datetime | None = None
    lost_reason: str | None = None
    notes: str | None = None
    years_experience: int | None = None


class CaregiverProspectCreate(CaregiverProspectBase):
    tenant_id: int | None = None


class CaregiverProspectUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    source: str | None = None
    stage: str | None = None
    owner_user_id: int | None = None
    next_follow_up_at: datetime | None = None
    lost_reason: str | None = None
    notes: str | None = None
    years_experience: int | None = None
    status: str | None = None


class CaregiverProspectResponse(CaregiverProspectBase):
    id: int
    tenant_id: int
    status: str
    converted_caregiver_id: int | None
    owner_name: str | None = None
    resume_score: float | None = None
    resume_document_id: int | None = None
    has_resume: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StageUpdateRequest(BaseModel):
    stage: str
    lost_reason: str | None = None


class ActivityCreate(BaseModel):
    activity_type: str = Field(default="NOTE")
    # LiveWell assessment reports include improvement plan + quote and regularly exceed 5k.
    body: str = Field(min_length=1, max_length=100_000)


class ActivityResponse(BaseModel):
    id: int
    activity_type: str
    body: str
    metadata: dict | None = None
    created_by_user_id: int | None
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConvertElderRequest(BaseModel):
    """Optional body: link prospect to an existing client instead of creating one."""

    elder_id: int | None = None


class ConvertElderResponse(BaseModel):
    prospect: ElderProspectResponse | None = None
    elder_id: int
    absorbed_prospect_id: int | None = None
    prospect_absorbed: bool = True


class ConvertCaregiverResponse(BaseModel):
    prospect: CaregiverProspectResponse
    caregiver_id: int
    skills_mapped: int = 0
