from datetime import datetime

from pydantic import BaseModel, Field


EVENT_TYPES = frozenset({
    "MOTION",
    "FALL",
    "DOOR",
    "NO_MOVEMENT",
    "PANIC",
    "ENVIRONMENTAL",
})

SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


class CameraEventCreate(BaseModel):
    elder_id: int
    event_type: str
    event_timestamp: datetime | None = None
    severity: str = "MEDIUM"
    clip_url: str | None = None
    snapshot_url: str | None = None
    metadata: dict | None = None
    process_rules: bool = True


class CameraEventIngest(BaseModel):
    """Webhook payload from camera / IoT gateway (tenant-scoped via auth)."""

    elder_id: int
    event_type: str
    event_timestamp: datetime | None = None
    severity: str = "MEDIUM"
    clip_url: str | None = None
    snapshot_url: str | None = None
    metadata: dict | None = None


class CameraEventResponse(BaseModel):
    id: int
    tenant_id: int
    elder_id: int
    event_type: str
    event_timestamp: datetime
    severity: str | None
    clip_url: str | None
    snapshot_url: str | None
    metadata: dict | None = None

    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    elder_id: int
    caregiver_id: int | None = None
    incident_type: str
    severity: str = "MEDIUM"
    description: str | None = None


class IncidentUpdate(BaseModel):
    status: str | None = None
    description: str | None = None


class MonitoringConfigUpdate(BaseModel):
    allowed_zones: list[str] | None = None
    restricted_zones: list[str] | None = None
    notify_care_manager: bool | None = None
    notify_family: bool | None = None
    auto_incident_on_fall: bool | None = None
    auto_incident_on_critical: bool | None = None
    no_movement_hours: int | None = None
    channels: list[str] | None = None


class MonitoringConsentUpdate(BaseModel):
    video_monitoring_consent: bool
    family_notifications_consent: bool = False
    consented_by_name: str | None = None
    notes: str | None = None


class MonitoringConsentResponse(BaseModel):
    elder_id: int
    video_monitoring_consent: bool
    family_notifications_consent: bool
    consented_by_name: str | None
    consented_at: datetime | None
    notes: str | None


class EventProcessResult(BaseModel):
    event_id: int
    processed: bool
    severity: str | None = None
    reasons: list[str] = []
    incident_id: int | None = None
    alerts_sent: int = 0


class MonitoringAlertResponse(BaseModel):
    id: int
    elder_id: int
    channel: str
    recipient_role: str
    recipient: str
    status: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: int
    tenant_id: int
    elder_id: int
    caregiver_id: int | None
    source_event_id: int | None = None
    incident_type: str
    severity: str
    description: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class MonitoringSummary(BaseModel):
    total_events_24h: int
    open_incidents: int
    critical_alerts: int
    events_by_type: dict[str, int]
