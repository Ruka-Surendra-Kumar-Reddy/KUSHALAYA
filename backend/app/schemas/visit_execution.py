from datetime import date, datetime

from pydantic import BaseModel, Field


class VisitChecklistItem(BaseModel):
    code: str
    title: str
    required: bool = True
    completed: bool = False
    log_id: int | None = None


class VisitChecklistResponse(BaseModel):
    elder_id: int
    log_date: date
    vertical_label: str
    items: list[VisitChecklistItem]
    required_total: int
    required_completed: int
    incident_types: list[dict] = Field(default_factory=list)


class VisitChecklistLogCreate(BaseModel):
    elder_id: int
    item_code: str
    completed: bool = True
    assignment_id: int | None = None
    attendance_id: int | None = None


class VisitChecklistLogResponse(BaseModel):
    id: int
    item_code: str
    item_title: str
    completed: bool
    log_date: date
    vertical_label: str


class VisitCareNoteResponse(BaseModel):
    id: int
    elder_id: int
    caregiver_id: int
    caregiver_name: str | None = None
    assignment_id: int | None = None
    attendance_id: int | None = None
    note_date: date
    note_type: str
    body: str
    created_at: datetime
    vertical_label: str


class VisitCareNoteCreate(BaseModel):
    elder_id: int
    note_type: str = "GENERAL"
    body: str
    assignment_id: int | None = None
    attendance_id: int | None = None


class FieldIncidentCreate(BaseModel):
    elder_id: int
    incident_type: str
    severity: str = "MEDIUM"
    description: str
    assignment_id: int | None = None


class FieldIncidentResponse(BaseModel):
    id: int
    elder_id: int
    caregiver_id: int | None = None
    incident_type: str
    severity: str
    description: str | None = None
    status: str
    created_at: datetime
    vertical_label: str
