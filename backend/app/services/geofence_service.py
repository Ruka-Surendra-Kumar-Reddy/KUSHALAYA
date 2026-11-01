import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.geofence_utils import (
    max_gps_accuracy_meters,
    within_geofence,
)
from app.core.rbac import CAREGIVER, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.assignment import Assignment
from app.models.attendance_alert import AttendanceAlert
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.caregiver_device import CaregiverDevice
from app.models.caregiver_location_event import CaregiverLocationEvent
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.user import User
from app.schemas.geofence import (
    LOCATION_EVENT_TYPES,
    DeviceRegisterRequest,
    GeofenceCreate,
    GeofenceUpdate,
    LocationEventCreate,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

ARRIVAL_EVENTS = frozenset({"ENTER", "CHECKIN"})
DEPARTURE_EVENTS = frozenset({"EXIT", "CHECKOUT"})


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class GeofenceService:

    @staticmethod
    def _get_elder(db: Session, elder_id: int, user: User) -> Elder:
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        return elder

    @staticmethod
    def create_geofence(
        db: Session,
        data: GeofenceCreate,
        user: User,
    ) -> ElderLocation:
        elder = GeofenceService._get_elder(db, data.elder_id, user)
        existing = (
            db.query(ElderLocation)
            .filter(ElderLocation.elder_id == elder.id)
            .first()
        )
        if existing:
            raise_bad_request("Geofence already exists for this elder; use PUT to update")

        row = ElderLocation(
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            latitude=data.latitude,
            longitude=data.longitude,
            radius_meters=data.radius_meters,
        )
        db.add(row)

        attrs = dict(elder.custom_attributes or {})
        attrs["latitude"] = data.latitude
        attrs["longitude"] = data.longitude
        attrs["geofence_radius_meters"] = data.radius_meters
        elder.custom_attributes = attrs

        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def update_geofence(
        db: Session,
        geofence_id: int,
        data: GeofenceUpdate,
        user: User,
    ) -> ElderLocation:
        row = db.query(ElderLocation).filter(ElderLocation.id == geofence_id).first()
        if not row:
            raise_not_found("Geofence not found")
        assert_tenant_access(user, row.tenant_id)

        if data.latitude is not None:
            row.latitude = data.latitude
        if data.longitude is not None:
            row.longitude = data.longitude
        if data.radius_meters is not None:
            row.radius_meters = data.radius_meters

        elder = db.query(Elder).filter(Elder.id == row.elder_id).first()
        if elder:
            attrs = dict(elder.custom_attributes or {})
            attrs["latitude"] = row.latitude
            attrs["longitude"] = row.longitude
            attrs["geofence_radius_meters"] = row.radius_meters
            elder.custom_attributes = attrs

        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_geofence_for_elder(
        db: Session,
        elder_id: int,
        user: User,
    ) -> ElderLocation | None:
        elder = GeofenceService._get_elder(db, elder_id, user)
        row = (
            db.query(ElderLocation)
            .filter(ElderLocation.elder_id == elder.id)
            .first()
        )
        if row:
            return row

        attrs = elder.custom_attributes or {}
        lat, lon = attrs.get("latitude"), attrs.get("longitude")
        if lat is not None and lon is not None:
            return ElderLocation(
                id=0,
                tenant_id=elder.tenant_id,
                elder_id=elder.id,
                latitude=float(lat),
                longitude=float(lon),
                radius_meters=float(attrs.get("geofence_radius_meters") or 100),
            )
        return None

    @staticmethod
    def register_device(
        db: Session,
        caregiver_id: int,
        data: DeviceRegisterRequest,
        user: User,
    ) -> CaregiverDevice:
        caregiver = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        if not caregiver:
            raise_not_found("Caregiver not found")
        if user.role == CAREGIVER:
            if user.caregiver_id != caregiver_id:
                raise_bad_request("Cannot register devices for another caregiver")
        else:
            assert_tenant_access(user, caregiver.tenant_id)

        existing = (
            db.query(CaregiverDevice)
            .filter(CaregiverDevice.device_id == data.device_id)
            .first()
        )
        if existing and existing.caregiver_id != caregiver_id:
            raise_bad_request("Device already registered to another caregiver")

        if existing:
            existing.device_label = data.device_label
            existing.last_seen_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

        device = CaregiverDevice(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            device_id=data.device_id,
            device_label=data.device_label,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(device)
        try:
            db.commit()
        except IntegrityError:
            # Two registrations raced (the app registers on every page load).
            db.rollback()
            existing = db.query(CaregiverDevice).filter(CaregiverDevice.device_id == data.device_id).first()
            if existing and existing.caregiver_id == caregiver_id:
                return existing
            raise_bad_request("Device already registered to another caregiver")
        db.refresh(device)
        return device

    @staticmethod
    def _validate_device(
        db: Session,
        caregiver_id: int,
        device_id: str | None,
        tenant_id: int,
    ) -> None:
        if not device_id:
            raise_bad_request("device_id is required for location events")
        device = (
            db.query(CaregiverDevice)
            .filter(
                CaregiverDevice.device_id == device_id,
                CaregiverDevice.caregiver_id == caregiver_id,
            )
            .first()
        )
        if not device:
            raise_bad_request("Device not registered for this caregiver")

    @staticmethod
    def _resolve_assignment(
        db: Session,
        caregiver_id: int,
        elder_id: int,
        assignment_id: int | None,
    ) -> Assignment:
        if assignment_id:
            row = db.query(Assignment).filter(Assignment.id == assignment_id).first()
            if not row:
                raise_not_found("Assignment not found")
            if row.caregiver_id != caregiver_id or row.elder_id != elder_id:
                raise_bad_request("Assignment does not match caregiver and elder")
            return row

        row = (
            db.query(Assignment)
            .filter(
                Assignment.caregiver_id == caregiver_id,
                Assignment.elder_id == elder_id,
                Assignment.status == "ACTIVE",
            )
            .order_by(Assignment.id.desc())
            .first()
        )
        if not row:
            raise_bad_request("No active assignment for this caregiver and elder")
        return row

    @staticmethod
    def process_location_event(
        db: Session,
        data: LocationEventCreate,
        user: User,
    ) -> dict:
        event_type = data.event_type.upper()
        if event_type not in LOCATION_EVENT_TYPES:
            raise_bad_request(f"event_type must be one of: {', '.join(LOCATION_EVENT_TYPES)}")

        if data.accuracy is not None:
            limit = max_gps_accuracy_meters()
            if data.accuracy > limit:
                raise_bad_request(
                    f"GPS accuracy {data.accuracy:.1f}m exceeds maximum {limit:.0f}m. "
                    "Move outdoors, wait a few seconds for a better fix, or ask your agency "
                    "to adjust MAX_GPS_ACCURACY_METERS if signal is consistently weak."
                )

        caregiver = db.query(Caregiver).filter(Caregiver.id == data.caregiver_id).first()
        if not caregiver:
            raise_not_found("Caregiver not found")
        if user.role == CAREGIVER:
            if user.caregiver_id != data.caregiver_id:
                raise_bad_request("Cannot submit events for another caregiver")
        else:
            assert_tenant_access(user, caregiver.tenant_id)
        elder = GeofenceService._get_elder(db, data.elder_id, user)
        if caregiver.tenant_id != elder.tenant_id:
            raise_bad_request("Caregiver and elder must belong to same tenant")

        GeofenceService._validate_device(
            db,
            caregiver.id,
            data.device_id,
            caregiver.tenant_id,
        )

        geofence = (
            db.query(ElderLocation)
            .filter(ElderLocation.elder_id == elder.id)
            .first()
        )
        if not geofence:
            raise_bad_request("Elder geofence not configured")

        inside, distance = within_geofence(
            data.latitude,
            data.longitude,
            geofence.latitude,
            geofence.longitude,
            geofence.radius_meters,
        )

        assignment = GeofenceService._resolve_assignment(
            db,
            caregiver.id,
            elder.id,
            data.assignment_id,
        )

        event = CaregiverLocationEvent(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            elder_id=elder.id,
            assignment_id=assignment.id,
            event_type=event_type,
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy=data.accuracy,
            distance_meters=distance,
            device_id=data.device_id,
            event_timestamp=data.event_timestamp or datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()

        attendance = None
        notifications: list[AttendanceAlert] = []
        reasons: list[str] = []

        if event_type in ARRIVAL_EVENTS:
            if not inside:
                reasons.append(f"Arrival rejected: {distance:.0f}m from geofence")
            else:
                attendance, alerts = GeofenceService._handle_arrival(
                    db,
                    assignment,
                    event,
                    caregiver,
                    elder,
                    distance,
                )
                notifications.extend(alerts)

        elif event_type in DEPARTURE_EVENTS:
            if not inside and event_type == "EXIT":
                reasons.append("Exit recorded outside geofence radius")
            attendance, alerts = GeofenceService._handle_departure(
                db,
                assignment,
                event,
                caregiver,
                elder,
                distance,
            )
            notifications.extend(alerts)

        else:
            reasons.append(f"Event {event_type} logged")

        AuditService.log(
            db,
            tenant_id=caregiver.tenant_id,
            user_id=user.id,
            entity_type="location_event",
            entity_id=event.id,
            action=f"location_{event_type.lower()}",
            new_value={
                "distance_m": round(distance, 1),
                "inside": inside,
                "assignment_id": assignment.id,
            },
        )

        db.commit()
        if attendance:
            db.refresh(attendance)
        db.refresh(event)

        message = "; ".join(reasons) if reasons else "Event processed"
        return {
            "id": event.id,
            "event_type": event_type,
            "distance_meters": round(distance, 1),
            "within_geofence": inside,
            "attendance_id": attendance.id if attendance else None,
            "attendance_status": attendance.status if attendance else None,
            "message": message,
            "notifications_sent": len(notifications),
        }

    @staticmethod
    def _handle_arrival(
        db: Session,
        assignment: Assignment,
        event: CaregiverLocationEvent,
        caregiver: Caregiver,
        elder: Elder,
        distance: float,
    ) -> tuple[AttendanceRecord, list[AttendanceAlert]]:
        open_row = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.assignment_id == assignment.id,
                AttendanceRecord.status == "CHECKED_IN",
            )
            .first()
        )
        if open_row:
            return open_row, []

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        existing = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.assignment_id == assignment.id,
                AttendanceRecord.checkin_time >= today_start,
                AttendanceRecord.status.in_(["CHECKED_IN", "COMPLETED"]),
            )
            .first()
        )
        if existing and existing.status == "CHECKED_IN":
            return existing, []

        record = AttendanceRecord(
            tenant_id=assignment.tenant_id,
            assignment_id=assignment.id,
            caregiver_id=caregiver.id,
            elder_id=elder.id,
            checkin_time=event.event_timestamp,
            status="CHECKED_IN",
            checkin_event_id=event.id,
        )
        db.add(record)
        db.flush()

        from app.services.scheduling_service import SchedulingService

        SchedulingService.link_attendance(
            db,
            assignment.id,
            record.id,
            record.checkin_time,
            None,
            "CHECKED_IN",
        )

        alerts = GeofenceService._notify_arrival(
            db,
            record,
            caregiver,
            elder,
            distance,
        )
        return record, alerts

    @staticmethod
    def _handle_departure(
        db: Session,
        assignment: Assignment,
        event: CaregiverLocationEvent,
        caregiver: Caregiver,
        elder: Elder,
        distance: float,
    ) -> tuple[AttendanceRecord | None, list[AttendanceAlert]]:
        record = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.assignment_id == assignment.id,
                AttendanceRecord.status == "CHECKED_IN",
            )
            .order_by(AttendanceRecord.checkin_time.desc())
            .first()
        )
        if not record:
            return None, []

        record.checkout_time = event.event_timestamp
        record.checkout_event_id = event.id
        record.status = "COMPLETED"
        if record.checkin_time and record.checkout_time:
            delta = _utc(record.checkout_time) - _utc(record.checkin_time)
            record.visit_duration_minutes = delta.total_seconds() / 60.0

        db.flush()

        from app.services.scheduling_service import SchedulingService

        SchedulingService.link_attendance(
            db,
            assignment.id,
            record.id,
            record.checkin_time,
            record.checkout_time,
            record.status,
        )

        alerts = GeofenceService._notify_departure(
            db,
            record,
            caregiver,
            elder,
        )
        return record, alerts

    @staticmethod
    def _notify_arrival(
        db: Session,
        record: AttendanceRecord,
        caregiver: Caregiver,
        elder: Elder,
        distance: float,
    ) -> list[AttendanceAlert]:
        name = f"{caregiver.first_name} {caregiver.last_name}"
        msg = (
            f"Caregiver {name} arrived. Elder #{elder.id}. "
            f"Time: {record.checkin_time}. Distance: {distance:.0f} meters."
        )
        return GeofenceService._log_alerts(
            db,
            record,
            elder,
            caregiver,
            "ARRIVAL",
            msg,
        )

    @staticmethod
    def _notify_departure(
        db: Session,
        record: AttendanceRecord,
        caregiver: Caregiver,
        elder: Elder,
    ) -> list[AttendanceAlert]:
        name = f"{caregiver.first_name} {caregiver.last_name}"
        duration = record.visit_duration_minutes or 0
        hours = int(duration // 60)
        mins = int(duration % 60)
        msg = (
            f"Caregiver {name} departed. Time: {record.checkout_time}. "
            f"Visit duration: {hours}h {mins}m."
        )
        return GeofenceService._log_alerts(
            db,
            record,
            elder,
            caregiver,
            "DEPARTURE",
            msg,
        )

    @staticmethod
    def _log_alerts(
        db: Session,
        record: AttendanceRecord,
        elder: Elder,
        caregiver: Caregiver,
        alert_type: str,
        message: str,
    ) -> list[AttendanceAlert]:
        try:
            from app.visit_notifications.service import VisitNotificationService
        except ImportError:
            # This product ships without the visit-notification fan-out; keep a
            # logged alert for the care manager so the check-in still records.
            alert = AttendanceAlert(
                tenant_id=elder.tenant_id,
                attendance_id=record.id,
                elder_id=elder.id,
                caregiver_id=caregiver.id,
                alert_type=alert_type,
                channel="log",
                recipient_role="CARE_MANAGER",
                recipient="care-team",
                status="LOGGED",
                message=message,
            )
            db.add(alert)
            db.flush()
            return [alert]

        return VisitNotificationService.record_attendance_alerts(
            db,
            record,
            elder,
            caregiver,
            alert_type,
            message,
        )
