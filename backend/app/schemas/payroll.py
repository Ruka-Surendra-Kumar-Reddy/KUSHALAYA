from datetime import date, datetime

from pydantic import BaseModel, Field


class PayRateCreate(BaseModel):
    caregiver_id: int
    hourly_rate: float = Field(gt=0)
    effective_from: date | None = None


class PayRateResponse(BaseModel):
    id: int
    caregiver_id: int
    hourly_rate: float
    currency: str
    effective_from: date

    model_config = {"from_attributes": True}


class PayrollGenerateRequest(BaseModel):
    period_start: date
    period_end: date


class PayrollDeductionResponse(BaseModel):
    deduction_type: str
    base_amount: float
    rate: float | None = None
    amount: float
    notes: str | None = None

    model_config = {"from_attributes": True}


class PayrollCaregiverSummary(BaseModel):
    caregiver_id: int
    caregiver_name: str
    hours: float
    gross: float
    deductions: list[PayrollDeductionResponse] = []
    total_deductions: float
    net: float


class PayrollLineResponse(BaseModel):
    id: int
    caregiver_id: int
    attendance_record_id: int | None
    hours: float
    hourly_rate: float
    amount: float
    description: str | None

    model_config = {"from_attributes": True}


class PayrollRunResponse(BaseModel):
    id: int
    period_start: date
    period_end: date
    status: str
    total_amount: float
    total_deductions: float = 0.0
    total_net: float = 0.0
    finalized_at: datetime | None
    lines: list[PayrollLineResponse] = []
    summaries: list[PayrollCaregiverSummary] = []

    model_config = {"from_attributes": True}
