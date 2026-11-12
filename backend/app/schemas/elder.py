from datetime import date

from pydantic import BaseModel, Field


class ElderBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    medical_conditions: str | None = None
    allergies: str | None = None
    mobility_status: str | None = None
    care_level: str | None = None
    custom_attributes: dict | None = None
    status: str = "ACTIVE"


class ElderCreate(ElderBase):
    tenant_id: int | None = None


class ElderUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    medical_conditions: str | None = None
    allergies: str | None = None
    mobility_status: str | None = None
    care_level: str | None = None
    custom_attributes: dict | None = None
    status: str | None = None


class ElderResponse(ElderBase):
    id: int
    tenant_id: int
    """Prospect that converted/linked to this client, if any."""
    linked_prospect_id: int | None = None
    linked_prospect_name: str | None = None
    # A record made to assess a lead, not a client yet (only listed with include_leads).
    is_lead: bool = False
    """Family portal has a published Independence Score™."""
    family_published: bool = False
    independence_score: int | None = None
    """Latest assessment linked to this client (draft or completed)."""
    latest_assessment_id: str | None = None
    latest_assessment_status: str | None = None
    """Short next-action hint for admin UI."""
    next_step: str | None = None
    """Family portal login email, if one exists for this client."""
    family_email: str | None = None

    model_config = {"from_attributes": True}
