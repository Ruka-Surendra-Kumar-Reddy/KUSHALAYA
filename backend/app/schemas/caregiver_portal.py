from datetime import date, datetime

from pydantic import BaseModel, Field


class CaregiverPortalMeResponse(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str
    caregiver_id: int
    tenant_id: int
    tenant_name: str
    portal_title: str


class CaregiverShiftGeofence(BaseModel):
    latitude: float
    longitude: float
    radius_meters: float
    configured: bool = True


class CaregiverShiftToday(BaseModel):
    assignment_id: int
    elder_id: int
    elder_name: str
    elder_address: str | None
    visit_id: int | None = None
    visit_status: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    attendance_id: int | None = None
    attendance_status: str | None = None
    geofence: CaregiverShiftGeofence | None = None


class CaregiverEarningsPeriod(BaseModel):
    run_id: int
    period_start: date
    period_end: date
    gross: float
    deductions: float = 0.0
    net: float = 0.0
    hours: float


class CaregiverEarningsSummary(BaseModel):
    caregiver_id: int
    ytd_year: int
    ytd_gross: float
    ytd_net: float = 0.0
    ytd_hours: float
    finalized_runs_count: int
    last_period: CaregiverEarningsPeriod | None = None


class CaregiverPayslipSummary(BaseModel):
    run_id: int
    period_start: date
    period_end: date
    gross: float
    deductions: float = 0.0
    net: float = 0.0
    hours: float
    finalized_at: datetime | None = None


class CaregiverLocationEventPortalCreate(BaseModel):
    elder_id: int
    event_type: str
    latitude: float
    longitude: float
    accuracy: float | None = None
    device_id: str = Field(min_length=8, max_length=255)
    assignment_id: int | None = None


class CaregiverCleaningJobPortal(BaseModel):
    id: int
    external_job_id: str
    property_id: int
    status: str
    scheduled_start: datetime | None = None
    notes: str | None = None
    my_role: str | None = None
    lead_cleaner_id: int | None = None
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    checked_in_caregiver_id: int | None = None
    address_line: str | None = None
    geofence: CaregiverShiftGeofence | None = None
    property: dict | None = None
    crew: list[dict] = Field(default_factory=list)


class CaregiverCleaningCheckPayload(BaseModel):
    latitude: float
    longitude: float
    accuracy: float | None = None
    device_id: str = Field(min_length=8, max_length=255)


class CaregiverCleaningCheckResult(BaseModel):
    job: CaregiverCleaningJobPortal
    within_geofence: bool
    distance_meters: float | None = None
    message: str
