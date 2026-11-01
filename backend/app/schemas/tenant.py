from pydantic import BaseModel, EmailStr, Field

from app.core.markets import DEFAULT_MARKET, VALID_MARKETS
from app.core.verticals import DEFAULT_VERTICAL, VALID_VERTICALS


class MarketInfo(BaseModel):
    id: str
    label: str
    currency: str
    tax_label: str
    payroll_regime: str


class TenantCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    address: str
    city: str
    state: str
    country: str = "India"
    market: str = DEFAULT_MARKET
    theme: str = "classic"
    vertical: str = DEFAULT_VERTICAL
    admin_email: EmailStr | None = None
    admin_password: str | None = Field(default=None, min_length=8)
    admin_first_name: str | None = None
    admin_last_name: str | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    market: str | None = None
    status: str | None = None
    vertical: str | None = None
    theme: str | None = None
    logo_url: str | None = None
    portal_title: str | None = Field(default=None, max_length=255)


class TenantBrandingUpdate(BaseModel):
    theme: str | None = None
    logo_url: str | None = None
    portal_title: str | None = Field(default=None, max_length=255)
    bench_cost_per_caregiver_month_inr: float | None = Field(
        default=None,
        ge=1_000,
        le=1_000_000,
        description="Monthly bench carrying cost per caregiver (INR) for Executive Command Center",
    )


class TenantBrandingResponse(BaseModel):
    id: int | None
    name: str
    portal_title: str
    logo_url: str | None
    theme: str
    platform_name: str = "WorkforceOS"
    vertical: str = DEFAULT_VERTICAL
    vertical_label: str = "LiveWell360"
    market: str = DEFAULT_MARKET
    market_label: str = "India"
    currency: str = "INR"
    bench_cost_per_caregiver_month_inr: float = 15_000.0
    elder_field_schema: list[dict] = []
    caregiver_field_schema: list[dict] = []

    model_config = {"from_attributes": True}


class ThemeInfo(BaseModel):
    id: str
    name: str
    description: str


class TenantDeleteRequest(BaseModel):
    confirm_name: str = Field(
        ...,
        min_length=1,
        description="Must exactly match tenant.name",
    )


class TenantDeleteResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    deleted_counts: dict[str, int]


class TenantResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    address: str
    city: str
    state: str
    country: str
    market: str = DEFAULT_MARKET
    status: str
    vertical: str = DEFAULT_VERTICAL
    theme: str = "classic"
    logo_url: str | None = None
    portal_title: str | None = None

    model_config = {"from_attributes": True}


class VerticalInfo(BaseModel):
    id: str
    label: str
    description: str
