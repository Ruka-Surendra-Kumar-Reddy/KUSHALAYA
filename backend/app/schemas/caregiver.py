from pydantic import BaseModel, EmailStr, field_serializer

from app.core.identity_utils import mask_aadhaar


class CaregiverBase(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: EmailStr | None = None
    aadhaar_number: str | None = None
    years_experience: int | None = None
    background_check_status: str | None = None
    police_verification_status: str | None = None
    custom_attributes: dict | None = None
    status: str = "ACTIVE"


class CaregiverCreate(CaregiverBase):
    tenant_id: int | None = None


class CaregiverUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    aadhaar_number: str | None = None
    years_experience: int | None = None
    background_check_status: str | None = None
    police_verification_status: str | None = None
    custom_attributes: dict | None = None
    status: str | None = None


class CaregiverResponse(CaregiverBase):
    id: int
    tenant_id: int

    model_config = {"from_attributes": True}

    @field_serializer("aadhaar_number")
    def serialize_aadhaar_masked(self, value: str | None) -> str | None:
        return mask_aadhaar(value)
