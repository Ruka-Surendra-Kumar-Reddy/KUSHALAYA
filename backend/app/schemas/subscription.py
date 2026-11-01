from datetime import date, datetime

from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    id: int
    code: str
    market: str = "IN"
    name: str
    description: str | None
    billing_model: str
    base_price_inr: float
    price_per_worker_inr: float
    included_workers: int
    max_workers: int | None
    trial_days: int
    is_active: bool

    model_config = {"from_attributes": True}


class TenantSubscriptionResponse(BaseModel):
    id: int
    tenant_id: int
    tenant_name: str | None = None
    plan: SubscriptionPlanResponse
    status: str
    trial_ends_at: datetime | None
    current_period_start: date | None
    current_period_end: date | None
    active_workers: int = 0
    notes: str | None = None

    model_config = {"from_attributes": True}


class AssignSubscriptionRequest(BaseModel):
    plan_code: str = Field(..., max_length=30)
    status: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)


class SubscriptionInvoiceGenerateRequest(BaseModel):
    tenant_id: int | None = None
    period_start: date
    period_end: date


class SubscriptionInvoiceResponse(BaseModel):
    id: int
    tenant_id: int
    tenant_name: str | None = None
    subscription_id: int
    plan_code: str | None = None
    invoice_number: str | None
    period_start: date
    period_end: date
    worker_count: int
    status: str
    subtotal: float
    tax_rate: float
    tax_amount: float
    total_amount: float
    amount_paid: float
    due_date: date | None
    issued_at: datetime | None
    paid_at: datetime | None
    line_description: str | None = None

    model_config = {"from_attributes": True}


class SubscriptionPaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    reference: str | None = Field(default=None, max_length=200)
