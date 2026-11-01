from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterElderPortalRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    tenant_id: int
    phone: str
    portal_relationship: str | None = "self"


class ElderPortalMeResponse(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str
    portal_relationship: str | None
    elder_id: int
    tenant_id: int
    tenant_name: str
    portal_title: str
    logo_url: str | None
    theme: str


class CareStatusResponse(BaseModel):
    elder_id: int
    elder_name: str
    elder_status: str
    care_level: str | None
    mobility_status: str | None
    assignment_status: str | None
    caregiver_name: str | None
    match_score: float | None
    open_incidents: int
    unread_notifications: int


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    elder_id: int
    title: str = Field(max_length=255)
    body: str


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageReply(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    direction: str
    body: str
    sender_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ElderActivityEvent(BaseModel):
    id: int
    event_type: str
    event_timestamp: datetime
    severity: str | None
    snapshot_url: str | None = None


class ElderActivityIncident(BaseModel):
    id: int
    incident_type: str
    severity: str
    status: str
    created_at: datetime


class ElderActivitySummary(BaseModel):
    events_last_24h: int
    open_incidents: int
    recent_events: list[ElderActivityEvent]
    recent_incidents: list[ElderActivityIncident]
    events_by_type_24h: dict[str, int]


class TenantRegisterOption(BaseModel):
    id: int
    name: str


class FamilyAttendanceResponse(BaseModel):
    id: int
    caregiver_name: str
    checkin_time: datetime | None
    checkout_time: datetime | None
    visit_duration_minutes: float | None
    status: str
