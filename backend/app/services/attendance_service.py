from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.models.assignment import Assignment
from app.models.attendance_alert import AttendanceAlert
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User
from app.models.visit import Visit


def _utc_start_of_today() -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _dt_gte(value: datetime | None, boundary: datetime) -> bool:
    """Compare datetimes safely when DB returns naive timestamps."""
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if boundary.tzinfo is None:
        boundary = boundary.replace(tzinfo=timezone.utc)
    return value >= boundary


class AttendanceService:

    @staticmethod
    def list_attendance(
        db: Session,
        user: User,
        elder_id: int | None = None,
        caregiver_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AttendanceRecord]:
        query = db.query(AttendanceRecord).order_by(
            AttendanceRecord.checkin_time.desc().nullslast()
        )
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(AttendanceRecord.tenant_id == tid)
        if elder_id is not None:
            query = query.filter(AttendanceRecord.elder_id == elder_id)
        if caregiver_id is not None:
            query = query.filter(AttendanceRecord.caregiver_id == caregiver_id)
        if status:
            query = query.filter(AttendanceRecord.status == status.upper())
        return query.limit(limit).all()

    @staticmethod
    def summary(db: Session, user: User) -> dict:
        tid = resolve_tenant_id(user)
        query = db.query(AttendanceRecord)
        if tid is not None:
            query = query.filter(AttendanceRecord.tenant_id == tid)

        rows = query.all()
        today_start = _utc_start_of_today()

        checked_in = sum(1 for r in rows if r.status == "CHECKED_IN")
        completed_today = sum(
            1
            for r in rows
            if r.status == "COMPLETED"
            and r.checkin_time
            and _dt_gte(r.checkin_time, today_start)
        )
        no_show = sum(
            1
            for r in rows
            if r.status == "NO_SHOW"
            and _dt_gte(r.created_at, today_start)
        )

        durations = [
            r.visit_duration_minutes
            for r in rows
            if r.visit_duration_minutes is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else None

        return {
            "total_visits": len(rows),
            "checked_in_now": checked_in,
            "completed_today": completed_today,
            "no_show_today": no_show,
            "average_duration_minutes": round(avg_duration, 1) if avg_duration else None,
            "on_time_arrivals": completed_today,
            "late_arrivals": 0,
        }

    @staticmethod
    def scan_missed_arrivals(db: Session, user: User) -> dict:
        """Flag active assignments with no check-in after grace window (ops cron / manual)."""
        tid = resolve_tenant_id(user)
        if tid is None and user.role != "SYSTEM_ADMIN":
            raise_bad_request("Tenant context required")

        today_start = _utc_start_of_today()
        today_end = today_start + timedelta(days=1)

        query = db.query(Assignment).filter(Assignment.status == "ACTIVE")
        if tid is not None:
            query = query.filter(Assignment.tenant_id == tid)
        assignments = query.all()

        flagged = 0
        alerts = 0

        for assignment in assignments:
            visit_today = (
                db.query(Visit)
                .filter(
                    Visit.assignment_id == assignment.id,
                    Visit.scheduled_start >= today_start,
                    Visit.scheduled_start < today_end,
                )
                .first()
            )
            if visit_today and (
                visit_today.check_in_time is not None
                or visit_today.status in ("IN_PROGRESS", "COMPLETED")
            ):
                continue

            attended = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.assignment_id == assignment.id,
                    AttendanceRecord.status.in_(["CHECKED_IN", "COMPLETED"]),
                )
                .all()
            )
            if any(_dt_gte(r.checkin_time, today_start) for r in attended):
                continue

            existing_no_show = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.assignment_id == assignment.id,
                    AttendanceRecord.status == "NO_SHOW",
                )
                .all()
            )
            if any(_dt_gte(r.created_at, today_start) for r in existing_no_show):
                continue

            elder = db.query(Elder).filter(Elder.id == assignment.elder_id).first()
            caregiver = (
                db.query(Caregiver)
                .filter(Caregiver.id == assignment.caregiver_id)
                .first()
            )
            if not elder or not caregiver:
                continue

            record = AttendanceRecord(
                tenant_id=assignment.tenant_id,
                assignment_id=assignment.id,
                caregiver_id=caregiver.id,
                elder_id=elder.id,
                status="NO_SHOW",
            )
            db.add(record)
            db.flush()
            flagged += 1

            msg = (
                "Assigned caregiver has not arrived within scheduled window. "
                f"Elder #{elder.id}, caregiver #{caregiver.id}."
            )
            managers = (
                db.query(User)
                .filter(
                    User.tenant_id == assignment.tenant_id,
                    User.role.in_(["CARE_MANAGER", "TENANT_ADMIN"]),
                    User.status == "ACTIVE",
                )
                .limit(5)
                .all()
            )
            for u in managers:
                db.add(
                    AttendanceAlert(
                        tenant_id=assignment.tenant_id,
                        attendance_id=record.id,
                        elder_id=elder.id,
                        caregiver_id=caregiver.id,
                        alert_type="MISSED_ARRIVAL",
                        channel="log",
                        recipient_role="care_manager",
                        recipient=u.email,
                        status="LOGGED",
                        message=msg,
                    )
                )
                alerts += 1

            from app.services.attendance_workflow_service import (
                AttendanceWorkflowService,
            )

            AttendanceWorkflowService.emit_attendance_alert(
                db,
                record,
                elder,
                caregiver,
                "MISSED_ARRIVAL",
                msg,
                commit=False,
            )

        db.commit()
        return {"flagged": flagged, "alerts_logged": alerts}

    @staticmethod
    def replacement_suggestions(
        db: Session,
        user: User,
        attendance_id: int,
        *,
        limit: int = 5,
    ) -> dict:
        from app.core.rbac import assert_tenant_access
        from app.core.responses import raise_not_found
        from app.services.replacement_staffing_service import (
            ReplacementStaffingService,
        )

        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.id == attendance_id)
            .first()
        )
        if not record:
            raise_not_found("Attendance record not found")
        assert_tenant_access(user, record.tenant_id)

        return ReplacementStaffingService.suggest_replacements(
            db,
            record.tenant_id,
            record.elder_id,
            exclude_caregiver_id=record.caregiver_id,
            limit=limit,
        )

    @staticmethod
    def family_today(db: Session, user: User) -> list[AttendanceRecord]:
        from app.services.elder_portal_service import ElderPortalService

        elder = ElderPortalService.get_linked_elder(db, user)
        today_start = _utc_start_of_today()
        rows = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.elder_id == elder.id)
            .order_by(AttendanceRecord.checkin_time.desc())
            .limit(20)
            .all()
        )
        return [r for r in rows if _dt_gte(r.checkin_time, today_start)]
