from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.visit import Visit
from app.models.user import User
from app.schemas.scheduling import (
    GenerateScheduleRequest,
    VisitCreate,
    VisitResponse,
    VisitUpdate,
)

WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class SchedulingService:

    @staticmethod
    def _display_name(first: str | None, last: str | None) -> str:
        name = f"{first or ''} {last or ''}".strip()
        return name or "Unknown"

    @staticmethod
    def visit_to_response(db: Session, visit: Visit) -> VisitResponse:
        elder = db.query(Elder).filter(Elder.id == visit.elder_id).first()
        caregiver = (
            db.query(Caregiver).filter(Caregiver.id == visit.caregiver_id).first()
        )
        return VisitResponse(
            id=visit.id,
            tenant_id=visit.tenant_id,
            assignment_id=visit.assignment_id,
            elder_id=visit.elder_id,
            caregiver_id=visit.caregiver_id,
            elder_name=(
                SchedulingService._display_name(elder.first_name, elder.last_name)
                if elder
                else None
            ),
            caregiver_name=(
                SchedulingService._display_name(
                    caregiver.first_name,
                    caregiver.last_name,
                )
                if caregiver
                else None
            ),
            scheduled_start=visit.scheduled_start,
            scheduled_end=visit.scheduled_end,
            check_in_time=visit.check_in_time,
            check_out_time=visit.check_out_time,
            attendance_record_id=visit.attendance_record_id,
            status=visit.status,
            visit_notes=visit.visit_notes,
        )

    @staticmethod
    def visits_to_responses(db: Session, visits: list[Visit]) -> list[VisitResponse]:
        if not visits:
            return []
        elder_ids = {v.elder_id for v in visits}
        caregiver_ids = {v.caregiver_id for v in visits}
        elders = {
            e.id: e
            for e in db.query(Elder).filter(Elder.id.in_(elder_ids)).all()
        }
        caregivers = {
            c.id: c
            for c in db.query(Caregiver).filter(Caregiver.id.in_(caregiver_ids)).all()
        }
        out: list[VisitResponse] = []
        for visit in visits:
            elder = elders.get(visit.elder_id)
            caregiver = caregivers.get(visit.caregiver_id)
            out.append(
                VisitResponse(
                    id=visit.id,
                    tenant_id=visit.tenant_id,
                    assignment_id=visit.assignment_id,
                    elder_id=visit.elder_id,
                    caregiver_id=visit.caregiver_id,
                    elder_name=(
                        SchedulingService._display_name(
                            elder.first_name, elder.last_name
                        )
                        if elder
                        else None
                    ),
                    caregiver_name=(
                        SchedulingService._display_name(
                            caregiver.first_name,
                            caregiver.last_name,
                        )
                        if caregiver
                        else None
                    ),
                    scheduled_start=visit.scheduled_start,
                    scheduled_end=visit.scheduled_end,
                    check_in_time=visit.check_in_time,
                    check_out_time=visit.check_out_time,
                    attendance_record_id=visit.attendance_record_id,
                    status=visit.status,
                    visit_notes=visit.visit_notes,
                )
            )
        return out

    @staticmethod
    def _assignment(db: Session, assignment_id: int, user: User) -> Assignment:
        row = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not row:
            raise_not_found("Assignment not found")
        assert_tenant_access(user, row.tenant_id)
        return row

    @staticmethod
    def list_visits(
        db: Session,
        user: User,
        *,
        assignment_id: int | None = None,
        elder_id: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 200,
    ) -> list[Visit]:
        query = db.query(Visit).order_by(Visit.scheduled_start.asc())
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Visit.tenant_id == tid)
        if assignment_id is not None:
            query = query.filter(Visit.assignment_id == assignment_id)
        if elder_id is not None:
            query = query.filter(Visit.elder_id == elder_id)
        if from_date:
            start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
            query = query.filter(Visit.scheduled_start >= start)
        if to_date:
            end = datetime.combine(
                to_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            query = query.filter(Visit.scheduled_start < end)
        return query.limit(limit).all()

    @staticmethod
    def create_visit(db: Session, data: VisitCreate, user: User) -> Visit:
        assignment = SchedulingService._assignment(db, data.assignment_id, user)
        if assignment.status != "ACTIVE":
            raise_bad_request("Assignment must be ACTIVE")
        if data.scheduled_end <= data.scheduled_start:
            raise_bad_request("scheduled_end must be after scheduled_start")

        visit = Visit(
            tenant_id=assignment.tenant_id,
            assignment_id=assignment.id,
            elder_id=assignment.elder_id,
            caregiver_id=assignment.caregiver_id,
            scheduled_start=data.scheduled_start,
            scheduled_end=data.scheduled_end,
            visit_notes=data.visit_notes,
            status="SCHEDULED",
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)
        return visit

    @staticmethod
    def update_visit(
        db: Session,
        visit_id: int,
        data: VisitUpdate,
        user: User,
    ) -> Visit:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise_not_found("Visit not found")
        assert_tenant_access(user, visit.tenant_id)

        if data.scheduled_start is not None:
            visit.scheduled_start = data.scheduled_start
        if data.scheduled_end is not None:
            visit.scheduled_end = data.scheduled_end
        if data.status is not None:
            visit.status = data.status.upper()
        if data.visit_notes is not None:
            visit.visit_notes = data.visit_notes

        if visit.scheduled_end <= visit.scheduled_start:
            raise_bad_request("scheduled_end must be after scheduled_start")

        db.commit()
        db.refresh(visit)
        return visit

    @staticmethod
    def _elder_schedule_days(elder: Elder) -> set[int]:
        attrs = elder.custom_attributes or {}
        sched = attrs.get("schedule_requirements")
        if not isinstance(sched, dict):
            return {0, 2, 4}
        days = sched.get("days") or []
        if not isinstance(days, list):
            return {0, 2, 4}
        out = set()
        for d in days:
            if isinstance(d, str) and d.lower() in WEEKDAY_MAP:
                out.add(WEEKDAY_MAP[d.lower()])
        return out or {0, 2, 4}

    @staticmethod
    def generate_schedule(
        db: Session,
        data: GenerateScheduleRequest,
        user: User,
    ) -> dict:
        if data.end_date < data.start_date:
            raise_bad_request("end_date must be on or after start_date")

        tid = resolve_tenant_id(user)
        query = db.query(Assignment).filter(Assignment.status == "ACTIVE")
        if tid is not None:
            query = query.filter(Assignment.tenant_id == tid)
        assignments = query.all()

        created = 0
        skipped = 0
        day = data.start_date
        while day <= data.end_date:
            weekday = day.weekday()
            for assignment in assignments:
                elder = db.query(Elder).filter(Elder.id == assignment.elder_id).first()
                if not elder:
                    continue
                if weekday not in SchedulingService._elder_schedule_days(elder):
                    continue

                start_dt = datetime.combine(
                    day,
                    datetime.min.time().replace(hour=data.default_start_hour),
                    tzinfo=timezone.utc,
                )
                end_dt = start_dt + timedelta(hours=data.default_duration_hours)

                exists = (
                    db.query(Visit)
                    .filter(
                        Visit.assignment_id == assignment.id,
                        Visit.scheduled_start == start_dt,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    continue

                db.add(
                    Visit(
                        tenant_id=assignment.tenant_id,
                        assignment_id=assignment.id,
                        elder_id=assignment.elder_id,
                        caregiver_id=assignment.caregiver_id,
                        scheduled_start=start_dt,
                        scheduled_end=end_dt,
                        status="SCHEDULED",
                    )
                )
                created += 1
            day += timedelta(days=1)

        db.commit()
        return {
            "created": created,
            "skipped": skipped,
            "assignments": len(assignments),
        }

    @staticmethod
    def coverage_summary(db: Session, user: User, days: int = 7) -> dict:
        tid = resolve_tenant_id(user)
        today = date.today()
        end = today + timedelta(days=days)

        assign_q = db.query(Assignment).filter(Assignment.status == "ACTIVE")
        if tid is not None:
            assign_q = assign_q.filter(Assignment.tenant_id == tid)
        active = assign_q.count()

        start_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        visit_q = db.query(Visit).filter(
            Visit.scheduled_start >= start_dt,
            Visit.scheduled_start < end_dt,
        )
        if tid is not None:
            visit_q = visit_q.filter(Visit.tenant_id == tid)

        scheduled = visit_q.filter(Visit.status == "SCHEDULED").count()
        completed = visit_q.filter(Visit.status == "COMPLETED").count()
        total_visits = visit_q.count()

        assignment_ids_with_visits = {
            row[0]
            for row in visit_q.with_entities(Visit.assignment_id).distinct().all()
        }
        uncovered = max(0, active - len(assignment_ids_with_visits))

        return {
            "active_assignments": active,
            "visits_scheduled": scheduled,
            "visits_completed": completed,
            "visits_total": total_visits,
            "uncovered_assignments": uncovered,
        }

    @staticmethod
    def link_attendance(
        db: Session,
        assignment_id: int,
        attendance_id: int,
        checkin_time: datetime,
        checkout_time: datetime | None,
        status: str,
    ) -> None:
        day_start = datetime.combine(
            checkin_time.date(),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        visit = (
            db.query(Visit)
            .filter(
                Visit.assignment_id == assignment_id,
                Visit.scheduled_start >= day_start,
                Visit.scheduled_start < day_end,
                Visit.status.in_(["SCHEDULED", "IN_PROGRESS"]),
            )
            .order_by(Visit.scheduled_start.asc())
            .first()
        )
        if not visit:
            return

        visit.attendance_record_id = attendance_id
        visit.check_in_time = checkin_time
        if checkout_time:
            visit.check_out_time = checkout_time
        visit.status = "COMPLETED" if status == "COMPLETED" else "IN_PROGRESS"
