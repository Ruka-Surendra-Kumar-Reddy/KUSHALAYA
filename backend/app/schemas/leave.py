from datetime import date, datetime

from pydantic import BaseModel, Field


LEAVE_TYPES = frozenset({"ANNUAL", "SICK", "UNPAID", "OTHER"})


class LeaveRequestCreate(BaseModel):
    leave_type: str = Field(..., max_length=30)
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)


class LeaveRequestReject(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class LeaveRequestResponse(BaseModel):
    id: int
    tenant_id: int
    caregiver_id: int
    caregiver_name: str | None = None
    leave_type: str
    start_date: date
    end_date: date
    reason: str | None
    status: str
    resolved_at: datetime | None = None
    resolved_by_user_id: int | None = None
    resolution_note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
