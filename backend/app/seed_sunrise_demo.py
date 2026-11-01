"""Full Sunrise Elder Care demo dataset (idempotent).

Populates elders, caregivers, family portal users, assignments, scheduled visits
(past + future), shift-swap requests, leave requests, care-plan work items,
visit notes/checklists, monitoring, prospects, and sample attendance.

Run after migrations:
  python -m app.db_migrate && python -m app.seed_care_demo

Or reset demo tenant entirely:
  python -m app.reset_sunrise_demo --confirm-name "Sunrise Elder Care"
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.care_plans.adapters import ELDER_CARE_DEFAULT_ACTIVITIES
from app.core.database import SessionLocal
from app.core.monitoring_config import DEFAULT_MONITORING_CONFIG
from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.camera_event import CameraEvent
from app.models.care_plan import (
    CarePlan,
    CarePlanActivity,
    CarePlanActivityLog,
    LOG_COMPLETED,
    PLAN_STATUS_ACTIVE,
)
from app.models.caregiver import Caregiver
from app.models.caregiver_pay_rate import CaregiverPayRate
from app.models.caregiver_rating import CaregiverRating
from app.models.caregiver_skill import CaregiverSkill
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.elder_message import DIRECTION_TENANT_TO_ELDER, ElderMessage
from app.models.elder_notification import ElderNotification
from app.models.elder_requirement import ElderRequirement
from app.models.incident import Incident
from app.models.leave_request import LeaveRequest
from app.models.monitoring_consent import MonitoringConsent
from app.models.placement_history import PlacementHistory
from app.models.shift_swap_request import ShiftSwapRequest
from app.models.skill import Skill
from app.models.tenant import Tenant
from app.models.user import User
from app.models.visit import Visit
from app.models.visit_care_note import NOTE_HANDOVER, VisitCareNote
from app.models.visit_checklist_log import VisitChecklistLog
from app.models.elder_prospect import ElderProspect
from app.models.caregiver_prospect import CaregiverProspect
from app.models.attendance_alert import AttendanceAlert
from app.seed_care_admin import LEGACY_ADMIN_EMAIL, SUNRISE_TENANT_NAME, TENANT_ADMIN_EMAIL

DEMO_PASSWORD = "demo1234"
WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
PAST_SCHEDULE_DAYS = 14
FUTURE_SCHEDULE_DAYS = 28

VISIT_CHECKLIST = [
    ("CLIENT_SAFE", "Client safe and comfortable"),
    ("MEDICATIONS", "Medications given as per care plan"),
    ("HOME_SECURED", "Home secured (doors and windows)"),
    ("ENVIRONMENT", "Environment safe — no hazards left"),
    ("HANDOVER", "Family informed if any concerns"),
]

SKILLS = [
    ("NURSING", "Nursing Care", "Clinical"),
    ("MEDICATION", "Medication Administration", "Clinical"),
    ("COOKING", "Cooking", "Daily Living"),
    ("MOBILITY", "Mobility Assistance", "Daily Living"),
]

CAREGIVERS = [
    (
        "Anita",
        "Devi",
        8,
        "VERIFIED",
        "VERIFIED",
        {
            "languages": ["Telugu", "Hindi"],
            "latitude": 17.42,
            "longitude": 78.47,
            "availability": {
                "days": ["mon", "wed", "fri", "sat"],
                "care_type": "visit_based",
            },
        },
        ["NURSING", "MEDICATION", "COOKING"],
        4.9,
    ),
    (
        "Sunita",
        "Rao",
        4,
        "VERIFIED",
        "PENDING",
        {
            "languages": ["Telugu"],
            "latitude": 17.44,
            "longitude": 78.50,
            "availability": {
                "days": ["mon", "tue", "wed"],
                "care_type": "visit_based",
            },
        },
        ["COOKING", "MOBILITY"],
        4.2,
    ),
    (
        "Meena",
        "Iyer",
        6,
        "VERIFIED",
        "VERIFIED",
        {
            "languages": ["Telugu", "English"],
            "latitude": 17.50,
            "longitude": 78.55,
            "availability": {
                "days": ["mon", "wed", "fri"],
                "care_type": "visit_based",
            },
        },
        ["NURSING", "MEDICATION"],
        4.7,
    ),
]


def _remove_legacy_admin(db: Session) -> None:
    legacy = db.query(User).filter(User.email == LEGACY_ADMIN_EMAIL).first()
    if legacy:
        db.delete(legacy)


def ensure_sunrise_tenant(db: Session) -> Tenant:
    """Return or create the Sunrise Elder Care demo tenant (by name)."""
    tenant = db.query(Tenant).filter(Tenant.name == SUNRISE_TENANT_NAME).first()
    if tenant:
        return tenant

    tenant = Tenant(
        name=SUNRISE_TENANT_NAME,
        email="contact@sunrise-care.example",
        phone="+91-9876543210",
        address="12 MG Road",
        city="Hyderabad",
        state="Telangana",
        vertical="ELDER_CARE",
        theme="ocean",
        portal_title=SUNRISE_TENANT_NAME,
    )
    db.add(tenant)
    db.flush()
    print(f"Created elder-care tenant: {SUNRISE_TENANT_NAME} (id={tenant.id})")
    return tenant


def _ensure_user(
    db: Session,
    *,
    email: str,
    tenant_id: int,
    role: str,
    first_name: str,
    last_name: str,
    elder_id: int | None = None,
    caregiver_id: int | None = None,
    portal_relationship: str | None = None,
) -> User:
    row = db.query(User).filter(User.email == email).first()
    pwd = hash_password(DEMO_PASSWORD)
    if row:
        row.role = role
        row.tenant_id = tenant_id
        row.first_name = first_name
        row.last_name = last_name
        row.status = "ACTIVE"
        row.elder_id = elder_id
        row.caregiver_id = caregiver_id
        row.portal_relationship = portal_relationship
        from app.core.security import verify_password

        try:
            if not verify_password(DEMO_PASSWORD, row.password_hash):
                row.password_hash = pwd
        except Exception:
            row.password_hash = pwd
        return row

    row = User(
        email=email,
        password_hash=pwd,
        first_name=first_name,
        last_name=last_name,
        role=role,
        tenant_id=tenant_id,
        status="ACTIVE",
        elder_id=elder_id,
        caregiver_id=caregiver_id,
        portal_relationship=portal_relationship,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_skills(db: Session) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for code, name, category in SKILLS:
        row = db.query(Skill).filter(Skill.code == code).first()
        if not row:
            row = Skill(code=code, name=name, category=category)
            db.add(row)
            db.flush()
        skills[code] = row
    return skills


def _ensure_elder(db: Session, tenant: Tenant, skills: dict[str, Skill]) -> Elder:
    elder = (
        db.query(Elder)
        .filter(
            Elder.tenant_id == tenant.id,
            Elder.first_name == "Lakshmi",
            Elder.last_name == "Reddy",
        )
        .first()
    )
    if not elder:
        elder = Elder(
            tenant_id=tenant.id,
            first_name="Lakshmi",
            last_name="Reddy",
            date_of_birth=date(1945, 3, 15),
            gender="Female",
            phone="+91-9000000001",
            address="45 Banjara Hills, Hyderabad",
            mobility_status="Assisted",
            care_level="High",
            custom_attributes={
                "language_preference": "Telugu",
                "latitude": 17.4239,
                "longitude": 78.4738,
                "required_experience_years": 5,
                "care_type": "visit_based",
                "schedule_requirements": {"days": ["mon", "wed", "fri"]},
            },
        )
        db.add(elder)
        db.flush()

    existing_reqs = {
        r.skill_id
        for r in db.query(ElderRequirement).filter(ElderRequirement.elder_id == elder.id)
    }
    for code, weight in [("NURSING", 10), ("MEDICATION", 10), ("COOKING", 5)]:
        sid = skills[code].id
        if sid not in existing_reqs:
            db.add(
                ElderRequirement(
                    elder_id=elder.id,
                    skill_id=sid,
                    required=True,
                    weight=weight,
                )
            )
    return elder


def _ensure_padmaja_elder(db: Session, tenant: Tenant) -> Elder:
    """Second staffed client (Alpharetta) for multi-client schedule demos."""
    elder = (
        db.query(Elder)
        .filter(
            Elder.tenant_id == tenant.id,
            Elder.first_name == "Padmaja",
            Elder.last_name == "Posa",
        )
        .first()
    )
    if not elder:
        elder = Elder(
            tenant_id=tenant.id,
            first_name="Padmaja",
            last_name="Posa",
            phone="+1-404-555-2450",
            address="2450 Clairview St, Alpharetta, GA 30009, USA",
            emergency_contact_name="Srikrishna Posa",
            emergency_contact_phone="+1-404-555-2450",
            care_level="Medium",
            mobility_status="Independent",
            custom_attributes={
                "language_preference": "English",
                "latitude": 34.0781034,
                "longitude": -84.2829513,
                "geofence_radius_meters": 100.0,
                "care_type": "visit_based",
                "schedule_requirements": {"days": ["mon", "wed", "fri"]},
            },
        )
        db.add(elder)
        db.flush()

    if not db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first():
        db.add(
            ElderLocation(
                tenant_id=tenant.id,
                elder_id=elder.id,
                latitude=34.0781034,
                longitude=-84.2829513,
                radius_meters=100.0,
            )
        )
    return elder


def _ensure_unstaffed_elder(db: Session, tenant: Tenant) -> Elder:
    """Client with schedule needs but no caregiver — powers unstaffed matching on /scheduling."""
    elder = (
        db.query(Elder)
        .filter(
            Elder.tenant_id == tenant.id,
            Elder.first_name == "Govind",
            Elder.last_name == "Rao",
        )
        .first()
    )
    if not elder:
        elder = Elder(
            tenant_id=tenant.id,
            first_name="Govind",
            last_name="Rao",
            phone="+91-9000000099",
            address="88 Jubilee Hills, Hyderabad",
            care_level="High",
            mobility_status="Wheelchair",
            custom_attributes={
                "language_preference": "Telugu",
                "latitude": 17.4310,
                "longitude": 78.4070,
                "care_type": "visit_based",
                "schedule_requirements": {"days": ["mon", "tue", "thu"]},
            },
        )
        db.add(elder)
        db.flush()
    return elder


def _ensure_assignment(
    db: Session,
    tenant: Tenant,
    elder: Elder,
    caregiver: Caregiver,
    *,
    match_score: float = 90.0,
) -> Assignment:
    row = (
        db.query(Assignment)
        .filter(
            Assignment.tenant_id == tenant.id,
            Assignment.elder_id == elder.id,
            Assignment.caregiver_id == caregiver.id,
            Assignment.status == "ACTIVE",
        )
        .first()
    )
    if row:
        return row
    row = Assignment(
        tenant_id=tenant.id,
        elder_id=elder.id,
        caregiver_id=caregiver.id,
        status="ACTIVE",
        match_score=match_score,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_caregivers(
    db: Session, tenant: Tenant, skills: dict[str, Skill]
) -> dict[str, Caregiver]:
    by_key: dict[str, Caregiver] = {}
    for first, last, years, bg, police, attrs, skill_codes, rating in CAREGIVERS:
        email = f"{first.lower()}.{last.lower()}@example.com"
        cg = (
            db.query(Caregiver)
            .filter(
                Caregiver.tenant_id == tenant.id,
                Caregiver.email == email,
            )
            .first()
        )
        if not cg:
            cg = Caregiver(
                tenant_id=tenant.id,
                first_name=first,
                last_name=last,
                years_experience=years,
                background_check_status=bg,
                police_verification_status=police,
                custom_attributes=attrs,
                email=email,
            )
            db.add(cg)
            db.flush()

        if not db.query(CaregiverRating).filter(CaregiverRating.caregiver_id == cg.id).first():
            db.add(
                CaregiverRating(
                    tenant_id=tenant.id,
                    caregiver_id=cg.id,
                    rating=rating,
                    source="care_manager",
                )
            )

        existing_skills = {
            s.skill_id
            for s in db.query(CaregiverSkill).filter(CaregiverSkill.caregiver_id == cg.id)
        }
        for code in skill_codes:
            sid = skills[code].id
            if sid not in existing_skills:
                db.add(
                    CaregiverSkill(
                        caregiver_id=cg.id,
                        skill_id=sid,
                        experience_years=years,
                        certified=code in ("NURSING", "MEDICATION"),
                    )
                )

        if not db.query(CaregiverPayRate).filter(CaregiverPayRate.caregiver_id == cg.id).first():
            db.add(
                CaregiverPayRate(
                    tenant_id=tenant.id,
                    caregiver_id=cg.id,
                    hourly_rate=350.0 if first == "Anita" else 280.0,
                    effective_from=date.today().replace(day=1),
                )
            )

        by_key[first.lower()] = cg
    return by_key


def _schedule_days(elder: Elder) -> set[int]:
    sched = (elder.custom_attributes or {}).get("schedule_requirements") or {}
    days = sched.get("days") if isinstance(sched, dict) else []
    out = set()
    if isinstance(days, list):
        for d in days:
            if isinstance(d, str) and d.lower() in WEEKDAY_MAP:
                out.add(WEEKDAY_MAP[d.lower()])
    return out or {0, 2, 4}


def _ensure_visits(
    db: Session,
    tenant: Tenant,
    assignment: Assignment,
    elder: Elder,
    caregiver: Caregiver,
    *,
    start: date,
    end: date,
    start_hour: int = 9,
    duration_hours: int = 4,
    extra_dates: set[date] | None = None,
    today_in_progress: bool = False,
) -> int:
    """Create scheduled shifts (visits) across a date range; idempotent."""
    created = 0
    schedule = _schedule_days(elder)
    extras = extra_dates or set()
    today = date.today()
    now = datetime.now(timezone.utc)
    day = start
    while day <= end:
        if day.weekday() not in schedule and day not in extras:
            day += timedelta(days=1)
            continue

        start_dt = datetime.combine(
            day,
            datetime.min.time().replace(hour=start_hour),
            tzinfo=timezone.utc,
        )
        end_dt = start_dt + timedelta(hours=duration_hours)

        visit = (
            db.query(Visit)
            .filter(
                Visit.assignment_id == assignment.id,
                Visit.scheduled_start == start_dt,
            )
            .first()
        )
        if not visit:
            if day < today:
                status = "COMPLETED"
                check_in = start_dt + timedelta(minutes=5)
                check_out = end_dt - timedelta(minutes=10)
            elif day == today and today_in_progress:
                status = "IN_PROGRESS"
                check_in = start_dt + timedelta(minutes=5) if now >= start_dt else None
                check_out = None
            else:
                status = "SCHEDULED"
                check_in = None
                check_out = None

            visit = Visit(
                tenant_id=tenant.id,
                assignment_id=assignment.id,
                elder_id=elder.id,
                caregiver_id=caregiver.id,
                scheduled_start=start_dt,
                scheduled_end=end_dt,
                status=status,
                check_in_time=check_in,
                check_out_time=check_out,
            )
            db.add(visit)
            created += 1
        elif day < today and visit.status == "SCHEDULED":
            visit.status = "COMPLETED"
            visit.check_in_time = visit.check_in_time or start_dt + timedelta(minutes=5)
            visit.check_out_time = visit.check_out_time or end_dt - timedelta(minutes=10)
        elif day == today and today_in_progress and visit.status == "SCHEDULED":
            visit.status = "IN_PROGRESS"
            if now >= start_dt and not visit.check_in_time:
                visit.check_in_time = start_dt + timedelta(minutes=5)

        day += timedelta(days=1)
    return created


def _ensure_attendance_for_completed_visits(
    db: Session,
    tenant: Tenant,
    assignment: Assignment,
) -> int:
    """Backfill attendance rows for completed visits missing them."""
    created = 0
    visits = (
        db.query(Visit)
        .filter(
            Visit.assignment_id == assignment.id,
            Visit.status == "COMPLETED",
            Visit.check_in_time.isnot(None),
            Visit.check_out_time.isnot(None),
        )
        .all()
    )
    for visit in visits:
        if visit.attendance_record_id:
            continue
        record = AttendanceRecord(
            tenant_id=tenant.id,
            assignment_id=assignment.id,
            caregiver_id=visit.caregiver_id,
            elder_id=visit.elder_id,
            checkin_time=visit.check_in_time,
            checkout_time=visit.check_out_time,
            visit_duration_minutes=max(
                0.0,
                (visit.check_out_time - visit.check_in_time).total_seconds() / 60.0,
            ),
            status="COMPLETED",
        )
        db.add(record)
        db.flush()
        visit.attendance_record_id = record.id
        created += 1
    return created


def _ensure_visit_execution(
    db: Session,
    tenant: Tenant,
    assignment: Assignment,
    elder: Elder,
    caregiver: Caregiver,
) -> None:
    """Care notes and end-of-visit checklist for a recent completed shift."""
    past_day = date.today() - timedelta(days=3)
    while past_day.weekday() not in _schedule_days(elder):
        past_day -= timedelta(days=1)

    if db.query(VisitCareNote).filter(
        VisitCareNote.elder_id == elder.id,
        VisitCareNote.note_date == past_day,
    ).first():
        return

    start_dt = datetime.combine(
        past_day,
        datetime.min.time().replace(hour=9),
        tzinfo=timezone.utc,
    )
    visit = (
        db.query(Visit)
        .filter(
            Visit.assignment_id == assignment.id,
            Visit.scheduled_start == start_dt,
        )
        .first()
    )
    attendance = None
    if visit and visit.attendance_record_id:
        attendance = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.id == visit.attendance_record_id)
            .first()
        )

    db.add(
        VisitCareNote(
            tenant_id=tenant.id,
            elder_id=elder.id,
            caregiver_id=caregiver.id,
            assignment_id=assignment.id,
            attendance_id=attendance.id if attendance else None,
            note_date=past_day,
            note_type=NOTE_HANDOVER,
            body=(
                "Client was alert and cooperative. Medications taken with breakfast. "
                "No concerns — family updated via portal message."
            ),
        )
    )

    for code, title in VISIT_CHECKLIST:
        if db.query(VisitChecklistLog).filter(
            VisitChecklistLog.elder_id == elder.id,
            VisitChecklistLog.log_date == past_day,
            VisitChecklistLog.item_code == code,
        ).first():
            continue
        db.add(
            VisitChecklistLog(
                tenant_id=tenant.id,
                elder_id=elder.id,
                caregiver_id=caregiver.id,
                assignment_id=assignment.id,
                attendance_id=attendance.id if attendance else None,
                log_date=past_day,
                item_code=code,
                item_title=title,
                completed=True,
            )
        )

    if attendance and not db.query(AttendanceAlert).filter(
        AttendanceAlert.attendance_id == attendance.id
    ).first():
        db.add(
            AttendanceAlert(
                tenant_id=tenant.id,
                attendance_id=attendance.id,
                elder_id=elder.id,
                caregiver_id=caregiver.id,
                alert_type="CHECKOUT",
                channel="log",
                recipient_role="CARE_MANAGER",
                recipient="manager@sunrise-care.example",
                status="LOGGED",
                message="Caregiver checked out — visit completed (demo seed).",
            )
        )


def _ensure_shift_swap_demo(
    db: Session,
    tenant: Tenant,
    requesting: Caregiver,
    replacement: Caregiver,
    assignment: Assignment,
) -> None:
    """Pending shift-swap on a future visit for the scheduling approvals panel."""
    if db.query(ShiftSwapRequest).filter(
        ShiftSwapRequest.tenant_id == tenant.id,
        ShiftSwapRequest.status == "PENDING",
    ).first():
        return

    now = datetime.now(timezone.utc)
    visit = (
        db.query(Visit)
        .filter(
            Visit.assignment_id == assignment.id,
            Visit.caregiver_id == requesting.id,
            Visit.status == "SCHEDULED",
            Visit.scheduled_start > now + timedelta(days=1),
        )
        .order_by(Visit.scheduled_start)
        .first()
    )
    if not visit:
        swap_day = date.today() + timedelta(days=3)
        start_dt = datetime.combine(
            swap_day,
            datetime.min.time().replace(hour=9),
            tzinfo=timezone.utc,
        )
        visit = Visit(
            tenant_id=tenant.id,
            assignment_id=assignment.id,
            elder_id=assignment.elder_id,
            caregiver_id=requesting.id,
            scheduled_start=start_dt,
            scheduled_end=start_dt + timedelta(hours=4),
            status="SCHEDULED",
        )
        db.add(visit)
        db.flush()

    db.add(
        ShiftSwapRequest(
            tenant_id=tenant.id,
            visit_id=visit.id,
            requesting_caregiver_id=requesting.id,
            replacement_caregiver_id=replacement.id,
            reason="Family appointment — requesting cover for this shift.",
            status="PENDING",
        )
    )


def _ensure_leave_requests(
    db: Session, tenant: Tenant, caregivers: dict[str, Caregiver]
) -> None:
    if not db.query(LeaveRequest).filter(LeaveRequest.tenant_id == tenant.id).first():
        sunita = caregivers["sunita"]
        meena = caregivers["meena"]
        pending_start = date.today() + timedelta(days=5)
        db.add(
            LeaveRequest(
                tenant_id=tenant.id,
                caregiver_id=sunita.id,
                leave_type="PERSONAL",
                start_date=pending_start,
                end_date=pending_start + timedelta(days=1),
                reason="Family function — demo pending approval.",
                status="PENDING",
            )
        )
        approved_start = date.today() - timedelta(days=10)
        db.add(
            LeaveRequest(
                tenant_id=tenant.id,
                caregiver_id=meena.id,
                leave_type="SICK",
                start_date=approved_start,
                end_date=approved_start,
                reason="Recovered — demo approved leave.",
                status="APPROVED",
            )
        )


def _ensure_placement_history(
    db: Session,
    tenant: Tenant,
    assignment: Assignment,
    elder: Elder,
    caregiver: Caregiver,
) -> None:
    if db.query(PlacementHistory).filter(
        PlacementHistory.assignment_id == assignment.id
    ).first():
        return
    db.add(
        PlacementHistory(
            tenant_id=tenant.id,
            elder_id=elder.id,
            caregiver_id=caregiver.id,
            assignment_id=assignment.id,
            start_date=date.today() - timedelta(days=30),
            outcome="ACTIVE",
        )
    )


def _ensure_prospects(db: Session, tenant: Tenant, manager: User | None) -> None:
    if not db.query(ElderProspect).filter(ElderProspect.tenant_id == tenant.id).first():
        db.add(
            ElderProspect(
                tenant_id=tenant.id,
                first_name="Kamala",
                last_name="Nair",
                phone="+91-9000000022",
                email="kamala.nair@example.com",
                source="Website inquiry",
                stage="ASSESSMENT_SCHEDULED",
                status="OPEN",
                owner_user_id=manager.id if manager else None,
                care_level="Medium",
                notes="Interested in weekday visit-based care for parent.",
            )
        )
    if not db.query(CaregiverProspect).filter(
        CaregiverProspect.tenant_id == tenant.id
    ).first():
        db.add(
            CaregiverProspect(
                tenant_id=tenant.id,
                first_name="Deepa",
                last_name="Kumar",
                phone="+91-9000000033",
                email="deepa.kumar@example.com",
                source="Referral",
                stage="INTERVIEW",
                status="OPEN",
                owner_user_id=manager.id if manager else None,
                years_experience=3,
                notes="Certified nursing assistant — demo recruitment pipeline.",
            )
        )


def _ensure_care_plan(
    db: Session,
    tenant: Tenant,
    elder: Elder,
    manager: User | None,
    caregiver: Caregiver,
    assignment: Assignment,
) -> None:
    plan = (
        db.query(CarePlan)
        .filter(CarePlan.tenant_id == tenant.id, CarePlan.elder_id == elder.id)
        .first()
    )
    if not plan:
        plan = CarePlan(
            tenant_id=tenant.id,
            elder_id=elder.id,
            title="Daily care plan",
            status=PLAN_STATUS_ACTIVE,
            effective_from=date.today(),
            notes="Demo care plan with daily work items for Lakshmi.",
            created_by_user_id=manager.id if manager else None,
        )
        db.add(plan)
        db.flush()

        for idx, item in enumerate(ELDER_CARE_DEFAULT_ACTIVITIES):
            db.add(
                CarePlanActivity(
                    care_plan_id=plan.id,
                    activity_type=item["activity_type"],
                    title=item["title"],
                    scheduled_time=item.get("scheduled_time"),
                    sort_order=idx,
                    required=item.get("required", True),
                )
            )
        db.flush()

    today = date.today()
    activities = (
        db.query(CarePlanActivity)
        .filter(CarePlanActivity.care_plan_id == plan.id)
        .order_by(CarePlanActivity.sort_order)
        .all()
    )
    for activity in activities[:3]:
        exists = (
            db.query(CarePlanActivityLog)
            .filter(
                CarePlanActivityLog.activity_id == activity.id,
                CarePlanActivityLog.log_date == today,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            CarePlanActivityLog(
                tenant_id=tenant.id,
                care_plan_id=plan.id,
                activity_id=activity.id,
                elder_id=elder.id,
                caregiver_id=caregiver.id,
                assignment_id=assignment.id,
                log_date=today,
                status=LOG_COMPLETED,
                notes="Completed during morning visit (demo seed).",
                completed_at=datetime.now(timezone.utc),
            )
        )


def _ensure_monitoring(db: Session, tenant: Tenant, elder: Elder) -> None:
    if not tenant.monitoring_config:
        tenant.monitoring_config = DEFAULT_MONITORING_CONFIG

    if not db.query(MonitoringConsent).filter(MonitoringConsent.elder_id == elder.id).first():
        db.add(
            MonitoringConsent(
                tenant_id=tenant.id,
                elder_id=elder.id,
                video_monitoring_consent=True,
                family_notifications_consent=True,
                consented_by_name="Demo seed",
                consented_at=datetime.utcnow(),
                notes="Seeded for monitoring demo",
            )
        )

    if db.query(CameraEvent).filter(CameraEvent.tenant_id == tenant.id).first():
        return

    now = datetime.utcnow()
    db.add_all(
        [
            CameraEvent(
                tenant_id=tenant.id,
                elder_id=elder.id,
                event_type="MOTION",
                event_timestamp=now - timedelta(hours=2),
                severity="LOW",
                snapshot_url="/demo/snap-motion.jpg",
                metadata_={"zone": "living_room"},
            ),
            CameraEvent(
                tenant_id=tenant.id,
                elder_id=elder.id,
                event_type="DOOR",
                event_timestamp=now - timedelta(hours=1),
                severity="MEDIUM",
                metadata_={"door": "front"},
            ),
            CameraEvent(
                tenant_id=tenant.id,
                elder_id=elder.id,
                event_type="FALL",
                event_timestamp=now - timedelta(minutes=45),
                severity="CRITICAL",
                clip_url="/demo/clip-fall.mp4",
                snapshot_url="/demo/snap-fall.jpg",
                metadata_={"confidence": 0.92},
            ),
            CameraEvent(
                tenant_id=tenant.id,
                elder_id=elder.id,
                event_type="NO_MOVEMENT",
                event_timestamp=now - timedelta(minutes=20),
                severity="HIGH",
                metadata_={"duration_minutes": 180},
            ),
        ]
    )
    db.add(
        Incident(
            tenant_id=tenant.id,
            elder_id=elder.id,
            incident_type="FALL_DETECTED",
            severity="HIGH",
            description="Auto-created from camera FALL event — awaiting review",
            status="OPEN",
        )
    )


def ensure_sunrise_demo_data() -> dict:
    """Idempotently populate the Sunrise / care_admin tenant with full demo data."""
    db = SessionLocal()
    summary: dict = {}
    try:
        tenant = ensure_sunrise_tenant(db)

        _remove_legacy_admin(db)

        skills = _ensure_skills(db)

        _ensure_user(
            db,
            email=TENANT_ADMIN_EMAIL,
            tenant_id=tenant.id,
            role="TENANT_ADMIN",
            first_name="Priya",
            last_name="Sharma",
        )
        manager = _ensure_user(
            db,
            email="manager@sunrise-care.example",
            tenant_id=tenant.id,
            role="CARE_MANAGER",
            first_name="Ravi",
            last_name="Kumar",
        )

        elder = _ensure_elder(db, tenant, skills)
        padmaja = _ensure_padmaja_elder(db, tenant)
        _ensure_unstaffed_elder(db, tenant)

        caregivers = _ensure_caregivers(db, tenant, skills)
        anita = caregivers["anita"]
        sunita = caregivers["sunita"]
        meena = caregivers["meena"]

        assignment_lakshmi = _ensure_assignment(
            db, tenant, elder, anita, match_score=92.0
        )
        assignment_padmaja = _ensure_assignment(
            db, tenant, padmaja, meena, match_score=88.0
        )

        if not db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first():
            db.add(
                ElderLocation(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    latitude=17.4239,
                    longitude=78.4738,
                    radius_meters=100.0,
                )
            )

        _ensure_user(
            db,
            email="anita.caregiver@sunrise-care.example",
            tenant_id=tenant.id,
            role="CAREGIVER",
            first_name=anita.first_name,
            last_name=anita.last_name,
            caregiver_id=anita.id,
        )
        _ensure_user(
            db,
            email="meena.caregiver@sunrise-care.example",
            tenant_id=tenant.id,
            role="CAREGIVER",
            first_name=meena.first_name,
            last_name=meena.last_name,
            caregiver_id=meena.id,
        )
        family_self = _ensure_user(
            db,
            email="lakshmi.family@sunrise-care.example",
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name="Lakshmi",
            last_name="Reddy",
            elder_id=elder.id,
            portal_relationship="self",
        )
        _ensure_user(
            db,
            email="arjun.family@sunrise-care.example",
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name="Arjun",
            last_name="Reddy",
            elder_id=elder.id,
            portal_relationship="son",
        )
        _ensure_user(
            db,
            email="clairview.family@sunrise-care.example",
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name=padmaja.first_name,
            last_name=padmaja.last_name,
            elder_id=padmaja.id,
            portal_relationship="self",
        )

        if not db.query(ElderNotification).filter(ElderNotification.elder_id == elder.id).first():
            db.add(
                ElderNotification(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    title="Welcome to your care portal",
                    body=(
                        "You can view care status, read messages from Sunrise Elder Care, "
                        "and contact your care team here."
                    ),
                    sent_by_user_id=manager.id,
                )
            )

        if not db.query(ElderMessage).filter(ElderMessage.elder_id == elder.id).first():
            db.add(
                ElderMessage(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    direction=DIRECTION_TENANT_TO_ELDER,
                    body=(
                        "Hello Lakshmi — your care team is here if you need anything. "
                        "Reply anytime on the Contact page."
                    ),
                    sender_user_id=manager.id,
                )
            )

        today = date.today()
        schedule_start = today - timedelta(days=PAST_SCHEDULE_DAYS)
        schedule_end = today + timedelta(days=FUTURE_SCHEDULE_DAYS)
        demo_dates = {today, today + timedelta(days=1), today + timedelta(days=3)}

        visits_created = 0
        visits_created += _ensure_visits(
            db,
            tenant,
            assignment_lakshmi,
            elder,
            anita,
            start=schedule_start,
            end=schedule_end,
            extra_dates=demo_dates,
            today_in_progress=True,
        )
        visits_created += _ensure_visits(
            db,
            tenant,
            assignment_padmaja,
            padmaja,
            meena,
            start=schedule_start,
            end=schedule_end,
            extra_dates={today, today + timedelta(days=2)},
        )

        attendance_created = _ensure_attendance_for_completed_visits(
            db, tenant, assignment_lakshmi
        )
        attendance_created += _ensure_attendance_for_completed_visits(
            db, tenant, assignment_padmaja
        )

        _ensure_visit_execution(db, tenant, assignment_lakshmi, elder, anita)
        _ensure_shift_swap_demo(db, tenant, anita, sunita, assignment_lakshmi)
        _ensure_leave_requests(db, tenant, caregivers)
        _ensure_placement_history(db, tenant, assignment_lakshmi, elder, anita)
        _ensure_prospects(db, tenant, manager)
        _ensure_care_plan(db, tenant, elder, manager, anita, assignment_lakshmi)
        _ensure_monitoring(db, tenant, elder)

        db.commit()

        visit_count = db.query(Visit).filter(Visit.tenant_id == tenant.id).count()
        swap_count = (
            db.query(ShiftSwapRequest)
            .filter(ShiftSwapRequest.tenant_id == tenant.id)
            .count()
        )
        leave_count = db.query(LeaveRequest).filter(LeaveRequest.tenant_id == tenant.id).count()
        summary = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "elder_id": elder.id,
            "caregivers": len(caregivers),
            "visits_created": visits_created,
            "visits_total": visit_count,
            "attendance_created": attendance_created,
            "shift_swaps": swap_count,
            "leave_requests": leave_count,
            "family_portal": family_self.email,
        }

        print("Sunrise demo data ready.")
        print(f"  Tenant: {tenant.name} (id={tenant.id})")
        print(f"  Tenant admin: {TENANT_ADMIN_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Care manager: manager@sunrise-care.example / {DEMO_PASSWORD}")
        print(f"  Elder portal (self): lakshmi.family@sunrise-care.example / {DEMO_PASSWORD}")
        print(f"  Family (son): arjun.family@sunrise-care.example / {DEMO_PASSWORD}")
        print(f"  Caregiver app: anita.caregiver@sunrise-care.example / {DEMO_PASSWORD}")
        print(f"  Second client: Padmaja Posa — caregiver meena.caregiver@sunrise-care.example")
        print(f"  Unstaffed client: Govind Rao (for auto-match on /scheduling)")
        print(f"  Shifts (visits): {visit_count} total ({visits_created} new)")
        print(f"  Shift swap requests: {swap_count} | Leave requests: {leave_count}")
    finally:
        db.close()
    return summary


if __name__ == "__main__":
    ensure_sunrise_demo_data()
