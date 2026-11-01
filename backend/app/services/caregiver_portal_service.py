"""Caregiver mobile/PWA portal — scoped shifts, device, location events."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import CARE_MANAGER, CAREGIVER, SYSTEM_ADMIN, TENANT_ADMIN
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.tenant import Tenant
from app.models.user import User
from app.models.visit import Visit
from app.schemas.auth import CaregiverPortalAccountCreate
from app.schemas.caregiver_portal import CaregiverLocationEventPortalCreate
from app.schemas.geofence import DeviceRegisterRequest, LocationEventCreate
from app.services.geofence_service import GeofenceService


class CaregiverPortalService:

    @staticmethod
    def get_linked_caregiver(db: Session, user: User) -> Caregiver:
        if user.caregiver_id is None:
            raise_not_found("Caregiver profile not linked")
        cg = db.query(Caregiver).filter(Caregiver.id == user.caregiver_id).first()
        if not cg:
            raise_not_found("Caregiver profile not found")
        if user.tenant_id is not None and cg.tenant_id != user.tenant_id:
            raise_bad_request("Caregiver tenant mismatch")
        return cg

    @staticmethod
    def portal_me(db: Session, user: User) -> dict:
        cg = CaregiverPortalService.get_linked_caregiver(db, user)
        tenant = db.query(Tenant).filter(Tenant.id == cg.tenant_id).first()
        name = tenant.name if tenant else "Agency"
        return {
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "caregiver_id": cg.id,
            "tenant_id": cg.tenant_id,
            "tenant_name": name,
            "portal_title": (tenant.portal_title if tenant else None) or name,
        }

    @staticmethod
    def _geofence_for_elder(db: Session, elder: Elder) -> dict | None:
        row = (
            db.query(ElderLocation)
            .filter(ElderLocation.elder_id == elder.id)
            .first()
        )
        if row:
            return {
                "latitude": row.latitude,
                "longitude": row.longitude,
                "radius_meters": row.radius_meters,
                "configured": True,
            }
        attrs = elder.custom_attributes or {}
        lat, lon = attrs.get("latitude"), attrs.get("longitude")
        if lat is not None and lon is not None:
            return {
                "latitude": float(lat),
                "longitude": float(lon),
                "radius_meters": float(attrs.get("geofence_radius_meters") or 100),
                "configured": True,
            }
        return None

    @staticmethod
    def list_shifts_today(db: Session, user: User) -> list[dict]:
        cg = CaregiverPortalService.get_linked_caregiver(db, user)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        visits = (
            db.query(Visit)
            .filter(
                Visit.caregiver_id == cg.id,
                Visit.scheduled_start >= today_start,
                Visit.scheduled_start < today_end,
            )
            .order_by(Visit.scheduled_start)
            .all()
        )

        seen_assignments: set[int] = set()
        shifts: list[dict] = []

        def append_shift(
            assignment: Assignment,
            elder: Elder,
            visit: Visit | None,
            attendance: AttendanceRecord | None,
        ) -> None:
            if assignment.id in seen_assignments:
                return
            seen_assignments.add(assignment.id)
            shifts.append(
                {
                    "assignment_id": assignment.id,
                    "elder_id": elder.id,
                    "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
                    "elder_address": elder.address,
                    "visit_id": visit.id if visit else None,
                    "visit_status": visit.status if visit else None,
                    "scheduled_start": visit.scheduled_start if visit else None,
                    "scheduled_end": visit.scheduled_end if visit else None,
                    "attendance_id": attendance.id if attendance else None,
                    "attendance_status": attendance.status if attendance else None,
                    "geofence": CaregiverPortalService._geofence_for_elder(db, elder),
                }
            )

        for visit in visits:
            assignment = (
                db.query(Assignment)
                .filter(Assignment.id == visit.assignment_id)
                .first()
            )
            elder = db.query(Elder).filter(Elder.id == visit.elder_id).first()
            if not assignment or not elder:
                continue
            attendance = None
            if visit.attendance_record_id:
                attendance = (
                    db.query(AttendanceRecord)
                    .filter(AttendanceRecord.id == visit.attendance_record_id)
                    .first()
                )
            if not attendance:
                attendance = (
                    db.query(AttendanceRecord)
                    .filter(
                        AttendanceRecord.assignment_id == assignment.id,
                        AttendanceRecord.caregiver_id == cg.id,
                        AttendanceRecord.created_at >= today_start,
                    )
                    .order_by(AttendanceRecord.id.desc())
                    .first()
                )
            append_shift(assignment, elder, visit, attendance)

        if not shifts:
            assignments = (
                db.query(Assignment)
                .filter(
                    Assignment.caregiver_id == cg.id,
                    Assignment.status == "ACTIVE",
                )
                .all()
            )
            for assignment in assignments:
                elder = db.query(Elder).filter(Elder.id == assignment.elder_id).first()
                if not elder:
                    continue
                attendance = (
                    db.query(AttendanceRecord)
                    .filter(
                        AttendanceRecord.assignment_id == assignment.id,
                        AttendanceRecord.caregiver_id == cg.id,
                        AttendanceRecord.created_at >= today_start,
                    )
                    .order_by(AttendanceRecord.id.desc())
                    .first()
                )
                append_shift(assignment, elder, None, attendance)

        return shifts

    @staticmethod
    def register_device(db: Session, user: User, data: DeviceRegisterRequest):
        cg = CaregiverPortalService.get_linked_caregiver(db, user)
        return GeofenceService.register_device(db, cg.id, data, user)

    @staticmethod
    def send_location_event(
        db: Session,
        user: User,
        data: CaregiverLocationEventPortalCreate,
    ) -> dict:
        cg = CaregiverPortalService.get_linked_caregiver(db, user)
        payload = LocationEventCreate(
            caregiver_id=cg.id,
            elder_id=data.elder_id,
            event_type=data.event_type,
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy=data.accuracy,
            device_id=data.device_id,
            assignment_id=data.assignment_id,
        )
        return GeofenceService.process_location_event(db, payload, user)

    @staticmethod
    def create_portal_account(
        db: Session,
        caregiver_id: int,
        data: CaregiverPortalAccountCreate,
        actor: User,
    ) -> dict:
        if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER}:
            raise_bad_request("Only admins can create caregiver portal accounts")

        cg = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        if not cg:
            raise_not_found("Caregiver not found")
        if actor.role != SYSTEM_ADMIN and actor.tenant_id != cg.tenant_id:
            raise_bad_request("Cannot create account for another tenant")
        from app.core.team_scope import assert_caregiver_in_team

        assert_caregiver_in_team(db, actor, cg.id)

        if db.query(User).filter(User.email == data.email).first():
            raise_conflict("Email already registered")

        existing = (
            db.query(User)
            .filter(User.caregiver_id == cg.id, User.role == CAREGIVER)
            .first()
        )
        if existing:
            raise_conflict("Caregiver portal account already exists")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name or cg.first_name,
            last_name=data.last_name or cg.last_name,
            role=CAREGIVER,
            tenant_id=cg.tenant_id,
            caregiver_id=cg.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "caregiver_id": user.caregiver_id,
        }
