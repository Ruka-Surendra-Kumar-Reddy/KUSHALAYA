from datetime import datetime

from pydantic import BaseModel, Field


class ShiftSwapCreate(BaseModel):
    visit_id: int
    replacement_caregiver_id: int | None = None
    reason: str | None = Field(default=None, max_length=2000)


class ShiftSwapApprove(BaseModel):
    replacement_caregiver_id: int | None = None


class ShiftSwapReject(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ShiftSwapResponse(BaseModel):
    id: int
    tenant_id: int
    visit_id: int
    requesting_caregiver_id: int
    requesting_caregiver_name: str | None = None
    replacement_caregiver_id: int | None
    replacement_caregiver_name: str | None = None
    elder_id: int | None = None
    elder_name: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    reason: str | None
    status: str
    resolved_at: datetime | None = None
    resolved_by_user_id: int | None = None
    resolution_note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CoworkerOption(BaseModel):
    caregiver_id: int
    name: str
