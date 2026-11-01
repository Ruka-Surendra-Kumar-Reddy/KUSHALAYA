"""Emit workflow events for attendance exceptions."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.workflow_events import ATTENDANCE_ALERT
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.services.workflow_emitter import emit_workflow_event

# Normalize ops alert labels to workflow template conditions.
WORKFLOW_ALERT_TYPES = frozenset(
    {
        "LATE",
        "NO_SHOW",
        "GEOFENCE_VIOLATION",
        "MISSED_CHECKIN",
        "MISSED_ARRIVAL",
        "DEPARTURE",
    }
)


def normalize_alert_type(alert_type: str) -> str:
    raw = (alert_type or "").upper()
    if raw == "MISSED_ARRIVAL":
        return "MISSED_CHECKIN"
    if raw == "DEPARTURE":
        return "GEOFENCE_VIOLATION"
    return raw


class AttendanceWorkflowService:

    @staticmethod
    def emit_attendance_alert(
        db: Session,
        record: AttendanceRecord,
        elder: Elder,
        caregiver: Caregiver,
        alert_type: str,
        message: str,
        *,
        commit: bool = False,
    ) -> dict | None:
        normalized = normalize_alert_type(alert_type)
        if normalized not in {
            "LATE",
            "NO_SHOW",
            "GEOFENCE_VIOLATION",
            "MISSED_CHECKIN",
        }:
            return None

        return emit_workflow_event(
            db,
            tenant_id=record.tenant_id,
            event_type=ATTENDANCE_ALERT,
            entity_type="attendance_record",
            entity_id=record.id,
            payload={
                "alert_type": normalized,
                "raw_alert_type": alert_type.upper(),
                "message": message,
                "elder_id": elder.id,
                "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
                "caregiver_id": caregiver.id,
                "caregiver_name": (
                    f"{caregiver.first_name} {caregiver.last_name}".strip()
                ),
                "assignment_id": record.assignment_id,
                "summary": message[:300],
            },
            commit=commit,
        )
