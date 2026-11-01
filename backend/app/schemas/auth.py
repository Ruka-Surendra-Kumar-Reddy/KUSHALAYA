from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    tenant_id: int
    role: str = "CARE_MANAGER"
    caregiver_id: int | None = None
    phone: str | None = Field(default=None, max_length=30)


class RegisterTenantRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    tenant_name: str
    tenant_email: EmailStr
    phone: str
    address: str
    city: str
    state: str
    country: str = "India"
    market: str = "IN"
    vertical: str = "LIVEWELL360"


class LoginRequest(BaseModel):
    # Plain str, not EmailStr: the service trims and lower-cases it and answers
    # a malformed address with the same "Invalid credentials" as a wrong one,
    # instead of a 422 validation blob the login form cannot show cleanly.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    email: str
    role: str
    tenant_id: int | None = None
    elder_id: int | None = None
    caregiver_id: int | None = None
    session_id: str | None = None
    # Always None: there is no sign-out for inactivity (session_policy).
    idle_minutes: int | None = None


class CaregiverPortalAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str | None = None
    last_name: str | None = None


class ElderPortalAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str | None = None
    last_name: str | None = None
    portal_relationship: str | None = "family"


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    tenant_id: int | None
    phone: str | None = None
    caregiver_id: int | None = None
    elder_id: int | None = None
    status: str = "ACTIVE"

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
