from typing import Literal

from pydantic import BaseModel, Field


class SafeHomePricingConfig(BaseModel):
    default_margin_percent: int = Field(default=25, ge=0, le=100)
    min_margin_percent: int = Field(default=15, ge=0, le=100)
    max_margin_percent: int = Field(default=50, ge=0, le=100)
    margin_type: Literal["percent", "fixed"] = "percent"
    fixed_margin_inr: int = Field(default=0, ge=0)
    travel_rate_per_km_inr: int = Field(default=15, ge=0)
    minimum_service_charge_inr: int = Field(default=500, ge=0)
    labor_rate_per_hour_inr: int = Field(default=700, ge=0)
    default_labor_hours_per_solution: float = Field(default=2, ge=0)
    default_consumables_inr: int = Field(default=500, ge=0)
    default_miscellaneous_inr: int = Field(default=0, ge=0)
    emergency_surcharge_percent: int = Field(default=25, ge=0, le=100)
    weekend_surcharge_percent: int = Field(default=15, ge=0, le=100)
    gst_percent: int = Field(default=18, ge=0, le=100)
    round_off_rule: Literal["none", "nearest_50", "nearest_100"] = "nearest_100"
    default_travel_km: float = Field(default=0, ge=0)
    use_vendor_cost_for_margin: bool = False
