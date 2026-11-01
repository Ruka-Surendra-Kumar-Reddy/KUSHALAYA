from datetime import date, datetime

from pydantic import BaseModel, Field


class ServiceRequestCreate(BaseModel):
    request_type: str = Field(
        description="EXTRA_SHIFT | REPLACEMENT_CAREGIVER | ADDITIONAL_SERVICE"
    )
    notes: str | None = Field(default=None, max_length=5000)
    preferred_date: date | None = None


class ServiceRequestResponse(BaseModel):
    id: int
    elder_id: int
    elder_name: str | None = None
    request_type: str
    status: str
    notes: str | None
    preferred_date: date | None
    staff_notes: str | None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    portal_type: str


class ServiceRequestStaffUpdate(BaseModel):
    status: str
    staff_notes: str | None = Field(default=None, max_length=5000)


class VisitHistoryResponse(BaseModel):
    id: int
    caregiver_name: str
    checkin_time: datetime | None
    checkout_time: datetime | None
    visit_duration_minutes: float | None
    status: str
    portal_type: str
