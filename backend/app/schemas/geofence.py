from datetime import datetime

from pydantic import BaseModel, Field

LOCATION_EVENT_TYPES = frozenset({
    "ENTER",
    "EXIT",
    "CHECKIN",
    "CHECKOUT",
    "DWELL",
})

ATTENDANCE_STATUSES = frozenset({
    "SCHEDULED",
    "CHECKED_IN",
    "COMPLETED",
    "NO_SHOW",
    "ANOMALY",
})


class GeofenceCreate(BaseModel):
    elder_id: int
    latitude: float
    longitude: float
    radius_meters: float = Field(default=100.0, ge=20, le=500)


class GeofenceUpdate(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    radius_meters: float | None = Field(default=None, ge=20, le=500)


class GeofenceResponse(BaseModel):
    id: int
    elder_id: int
    tenant_id: int
    latitude: float
    longitude: float
    radius_meters: float

    model_config = {"from_attributes": True}


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=255)
    device_label: str | None = None


class LocationEventCreate(BaseModel):
    caregiver_id: int
    elder_id: int
    event_type: str
    latitude: float
    longitude: float
    accuracy: float | None = None
    device_id: str | None = None
    assignment_id: int | None = None
    event_timestamp: datetime | None = None


class LocationEventResponse(BaseModel):
    id: int
    event_type: str
    distance_meters: float | None
    within_geofence: bool
    attendance_id: int | None
    attendance_status: str | None
    message: str
    notifications_sent: int = 0


class AttendanceResponse(BaseModel):
    id: int
    assignment_id: int
    caregiver_id: int
    elder_id: int
    checkin_time: datetime | None
    checkout_time: datetime | None
    visit_duration_minutes: float | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AttendanceSummary(BaseModel):
    total_visits: int
    checked_in_now: int
    completed_today: int
    no_show_today: int
    average_duration_minutes: float | None
    on_time_arrivals: int
    late_arrivals: int
