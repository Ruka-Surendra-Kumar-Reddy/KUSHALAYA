from pydantic import BaseModel, Field


PARTNER_ROLES = ("supplier", "installer")
PARTNER_TIERS = ("", "founding_platinum", "gold", "silver")
DEFAULT_ROLLING_WINDOW = 5


class Supplier(BaseModel):
    id: str
    name: str
    contact: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    rating: float | None = Field(default=None, ge=0, le=5)
    """Manual seed / override rating (0–5). Used until rolling reviews exist."""
    roles: list[str] = Field(default_factory=lambda: ["supplier"])
    """Partner roles: supplier (product vendor) and/or installer (field work)."""
    category: str = ""
    """e.g. Bathroom Safety, Medical Equipment, Smart Home, Home Healthcare."""
    partner_tier: str = ""
    """founding_platinum | gold | silver | empty."""
    rolling_rating: float | None = Field(default=None, ge=0, le=5)
    """Average of last N visit experience ratings."""
    rolling_rating_count: int = Field(default=0, ge=0)
    rolling_window: int = Field(default=DEFAULT_ROLLING_WINDOW, ge=1, le=20)
    active: bool = True
    sort_order: int = 0


class ProductSupplierOffer(BaseModel):
    id: str
    product_id: str
    supplier_id: str
    supplier_cost_inr: int = Field(ge=0)
    preferred: bool = False
    moq: int = Field(default=1, ge=1)
    lead_time_days: int = Field(default=0, ge=0)
    vendor_sku: str = ""
    active: bool = True


class SupplierDirectory(BaseModel):
    suppliers: list[Supplier] = Field(default_factory=list)
    offers: list[ProductSupplierOffer] = Field(default_factory=list)
