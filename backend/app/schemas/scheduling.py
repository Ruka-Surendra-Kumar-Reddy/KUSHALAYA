from datetime import date, datetime

from pydantic import BaseModel, Field


class VisitCreate(BaseModel):
    assignment_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    visit_notes: str | None = None


class VisitUpdate(BaseModel):
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    status: str | None = None
    visit_notes: str | None = None


class VisitResponse(BaseModel):
    id: int
    tenant_id: int
    assignment_id: int
    elder_id: int
    caregiver_id: int
    elder_name: str | None = None
    caregiver_name: str | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    check_in_time: datetime | None
    check_out_time: datetime | None
    attendance_record_id: int | None
    status: str
    visit_notes: str | None

    model_config = {"from_attributes": True}


class GenerateScheduleRequest(BaseModel):
    start_date: date
    end_date: date
    default_start_hour: int = Field(default=9, ge=0, le=23)
    default_duration_hours: float = Field(default=4.0, ge=0.5, le=12)


class ScheduleCoverageSummary(BaseModel):
    active_assignments: int
    visits_scheduled: int
    visits_completed: int
    visits_total: int = 0
    uncovered_assignments: int


class AutoScheduleRequest(BaseModel):
    start_date: date
    end_date: date
    default_start_hour: int = Field(default=9, ge=0, le=23)
    default_duration_hours: float = Field(default=4.0, ge=0.5, le=12)
    max_hours_per_week: float = Field(default=48.0, ge=8, le=80)
    dry_run: bool = Field(
        default=True,
        description="Preview optimized schedule without creating visits",
    )


class UncoveredClient(BaseModel):
    elder_id: int
    elder_name: str
    schedule_days: list[str]


class AutoScheduleProposal(BaseModel):
    assignment_id: int
    elder_id: int
    caregiver_id: int
    elder_name: str | None = None
    caregiver_name: str | None = None
    day: str
    scheduled_start: str
    scheduled_end: str
    action: str
    score: float | None = None
    reasons: list[str] = Field(default_factory=list)


class AutoScheduleResponse(BaseModel):
    mode: str
    created: int
    proposed: int
    skipped: int
    conflicts: int
    assignments: int
    uncovered_clients: list[UncoveredClient]
    proposals: list[AutoScheduleProposal]
