from datetime import date, datetime

from pydantic import BaseModel, Field


class CarePlanActivityCreate(BaseModel):
    activity_type: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scheduled_time: str | None = Field(default=None, max_length=5)
    sort_order: int = 0
    required: bool = True


class CarePlanActivityUpdate(BaseModel):
    activity_type: str | None = None
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    scheduled_time: str | None = Field(default=None, max_length=5)
    sort_order: int | None = None
    required: bool | None = None


class CarePlanActivityResponse(BaseModel):
    id: int
    care_plan_id: int
    activity_type: str
    title: str
    description: str | None
    scheduled_time: str | None
    sort_order: int
    required: bool


class CarePlanCreate(BaseModel):
    elder_id: int
    title: str = Field(default="Care plan", max_length=255)
    notes: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    activities: list[CarePlanActivityCreate] = Field(default_factory=list)


class CarePlanUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    status: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class CarePlanResponse(BaseModel):
    id: int
    elder_id: int
    title: str
    status: str
    notes: str | None
    effective_from: date | None
    effective_to: date | None
    vertical_label: str
    activities: list[CarePlanActivityResponse] = Field(default_factory=list)


class CarePlanLogCreate(BaseModel):
    activity_id: int
    elder_id: int
    status: str = "COMPLETED"
    notes: str | None = None
    assignment_id: int | None = None


class CarePlanLogResponse(BaseModel):
    id: int
    activity_id: int
    elder_id: int
    log_date: date
    status: str
    notes: str | None
    completed_at: datetime | None


class CarePlanTaskToday(BaseModel):
    activity_id: int
    activity_type: str
    title: str
    description: str | None
    scheduled_time: str | None
    required: bool
    log_status: str | None
    log_id: int | None


class CarePlanComplianceSummary(BaseModel):
    elder_id: int
    plan_id: int | None
    plan_title: str | None
    plan_status: str | None
    portal_type: str
    today_required: int
    today_completed: int
    today_partial: int
    today_missed: int
    week_completion_rate: float
    activities: list[CarePlanTaskToday]


class CarePlanTemplateResponse(BaseModel):
    vertical_label: str
    default_plan_title: str
    default_activities: list[CarePlanActivityCreate]
    activity_types: list[dict]


class CarePlanComplianceDay(BaseModel):
    log_date: date
    required_total: int
    completed: int
    partial: int
    completion_rate: float


class CarePlanComplianceHistory(BaseModel):
    elder_id: int
    plan_id: int | None
    plan_title: str | None = None
    vertical_label: str
    days: list[CarePlanComplianceDay]
