from datetime import date, datetime

from pydantic import BaseModel, Field


class BillingRateCreate(BaseModel):
    elder_id: int
    hourly_rate: float = Field(gt=0)


class BillingRateResponse(BaseModel):
    id: int
    elder_id: int
    hourly_rate: float
    currency: str

    model_config = {"from_attributes": True}


class InvoiceGenerateRequest(BaseModel):
    period_start: date
    period_end: date
    elder_id: int | None = None
    include_attendance: bool = True


class InvoiceLineResponse(BaseModel):
    id: int
    description: str
    hours: float
    unit_price: float
    amount: float
    attendance_record_id: int | None = None

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: int
    elder_id: int
    invoice_number: str | None = None
    period_start: date
    period_end: date
    status: str
    subtotal: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total_amount: float
    amount_paid: float = 0.0
    due_date: date | None = None
    issued_at: datetime | None = None
    paid_at: datetime | None = None
    lines: list[InvoiceLineResponse] = []

    model_config = {"from_attributes": True}


class InvoicePaymentRequest(BaseModel):
    amount: float = Field(gt=0)


class CollectionsInvoiceEntry(BaseModel):
    invoice_id: int
    invoice_number: str | None = None
    elder_id: int
    elder_name: str
    due_date: str | None = None
    total_amount: float
    amount_paid: float
    balance: float
    status: str
    days_overdue: int = 0


class CollectionsResponse(BaseModel):
    as_of: str
    total_outstanding: float
    overdue_count: int
    buckets: dict[str, list[CollectionsInvoiceEntry]]
