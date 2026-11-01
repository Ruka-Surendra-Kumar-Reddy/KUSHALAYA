"""Caregiver portal API — the signed-in caregiver's own day, check-ins and pay.

Every route here is scoped to the caller's linked caregiver profile
(`require_caregiver_portal`); none takes a caregiver id from the client.
Staff create the caregiver's login through `POST /caregivers/{id}/portal-account`.

Pay is read straight from finalized payroll runs. (`caregiver_payroll_portal_service`
depends on finance modules this product does not ship, so it is not used here.)
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import WRITE_ROLES, require_caregiver_portal, require_roles
from app.models.payroll_deduction import PayrollDeduction
from app.models.payroll_run import PayrollLine, PayrollRun
from app.models.user import User
from app.schemas.auth import CaregiverPortalAccountCreate
from app.schemas.caregiver_portal import (
    CaregiverEarningsPeriod,
    CaregiverEarningsSummary,
    CaregiverLocationEventPortalCreate,
    CaregiverPayslipSummary,
    CaregiverPortalMeResponse,
    CaregiverShiftToday,
)
from app.schemas.geofence import DeviceRegisterRequest
from app.services.caregiver_portal_service import CaregiverPortalService

router = APIRouter(prefix="/caregiver-portal", tags=["Caregiver portal"])
staff_router = APIRouter(prefix="/caregivers", tags=["Assessors"])

FINALIZED = "FINALIZED"


@router.get("/me", response_model=CaregiverPortalMeResponse)
def me(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    return CaregiverPortalService.portal_me(db, user)


@router.get("/shifts/today", response_model=list[CaregiverShiftToday])
def shifts_today(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    return CaregiverPortalService.list_shifts_today(db, user)


@router.post("/device")
def register_device(
    data: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    device = CaregiverPortalService.register_device(db, user, data)
    return {"id": device.id, "device_id": device.device_id}


@router.post("/location-events")
def location_event(
    data: CaregiverLocationEventPortalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    return CaregiverPortalService.send_location_event(db, user, data)


def _payslips(db: Session, caregiver_id: int) -> list[CaregiverPayslipSummary]:
    """One payslip per finalized payroll run that paid this caregiver, newest first."""
    rows = (
        db.query(
            PayrollRun.id,
            PayrollRun.period_start,
            PayrollRun.period_end,
            PayrollRun.finalized_at,
            func.coalesce(func.sum(PayrollLine.amount), 0.0),
            func.coalesce(func.sum(PayrollLine.hours), 0.0),
        )
        .join(PayrollLine, PayrollLine.payroll_run_id == PayrollRun.id)
        .filter(PayrollLine.caregiver_id == caregiver_id, PayrollRun.status == FINALIZED)
        .group_by(PayrollRun.id, PayrollRun.period_start, PayrollRun.period_end, PayrollRun.finalized_at)
        .order_by(PayrollRun.period_end.desc())
        .all()
    )
    deductions = dict(
        db.query(PayrollDeduction.payroll_run_id, func.coalesce(func.sum(PayrollDeduction.amount), 0.0))
        .filter(PayrollDeduction.caregiver_id == caregiver_id)
        .group_by(PayrollDeduction.payroll_run_id)
        .all()
    )
    out = []
    for run_id, start, end, finalized_at, gross, hours in rows:
        ded = float(deductions.get(run_id, 0.0))
        out.append(
            CaregiverPayslipSummary(
                run_id=run_id,
                period_start=start,
                period_end=end,
                gross=round(float(gross), 2),
                deductions=round(ded, 2),
                net=round(float(gross) - ded, 2),
                hours=round(float(hours), 2),
                finalized_at=finalized_at,
            )
        )
    return out


@router.get("/payslips", response_model=list[CaregiverPayslipSummary])
def payslips(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    cg = CaregiverPortalService.get_linked_caregiver(db, user)
    return _payslips(db, cg.id)


@router.get("/earnings", response_model=CaregiverEarningsSummary)
def earnings(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    cg = CaregiverPortalService.get_linked_caregiver(db, user)
    year = datetime.now(timezone.utc).year
    slips = _payslips(db, cg.id)
    this_year = [s for s in slips if s.period_end >= date(year, 1, 1)]
    last = slips[0] if slips else None
    return CaregiverEarningsSummary(
        caregiver_id=cg.id,
        ytd_year=year,
        ytd_gross=round(sum(s.gross for s in this_year), 2),
        ytd_net=round(sum(s.net for s in this_year), 2),
        ytd_hours=round(sum(s.hours for s in this_year), 2),
        finalized_runs_count=len(slips),
        last_period=(
            CaregiverEarningsPeriod(
                run_id=last.run_id,
                period_start=last.period_start,
                period_end=last.period_end,
                gross=last.gross,
                deductions=last.deductions,
                net=last.net,
                hours=last.hours,
            )
            if last
            else None
        ),
    )


@staff_router.post("/{caregiver_id}/portal-account", status_code=201)
def create_portal_account(
    caregiver_id: int,
    data: CaregiverPortalAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return CaregiverPortalService.create_portal_account(db, caregiver_id, data, current_user)


# --- Jobs: visits, assessments and installs assigned to this caregiver -----------


class JobStatusUpdate(BaseModel):
    status: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)
    note: str | None = None


class FieldAssessmentSave(BaseModel):
    ratings: dict = Field(default_factory=dict)
    item_notes: dict = Field(default_factory=dict)
    answer_labels: dict = Field(default_factory=dict)
    resident_profile: dict = Field(default_factory=dict)
    notes: str = ""
    complete: bool = False
    # Finishing the assessment closes the visit, so it needs a location like check-out.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)


@router.get("/jobs")
def my_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.care_jobs import list_for_caregiver

    return list_for_caregiver(db, user)


@router.post("/jobs/{job_id}/status")
def my_job_status(
    job_id: int,
    data: JobStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.care_jobs import caregiver_set_status
    from app.livewell.visit_location import require

    # Check-in and finishing need a location (on the way does not).
    if data.status in ("checked_in", "completed"):
        require(data.latitude, data.longitude, "checkin" if data.status == "checked_in" else "checkout")
    return caregiver_set_status(
        db, user, job_id, data.status, lat=data.latitude, lng=data.longitude, accuracy=data.accuracy, note=data.note
    )


class LivePosition(BaseModel):
    latitude: float
    longitude: float
    accuracy: float | None = Field(default=None, ge=0)


@router.post("/jobs/{job_id}/location")
def my_job_location(
    job_id: int,
    data: LivePosition,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """Latest position while on the way (only the newest point is kept)."""
    from app.livewell.live_location import record

    return record(db, user, job_id, lat=data.latitude, lng=data.longitude, accuracy=data.accuracy)


@router.get("/jobs/{job_id}/assessment")
def my_job_assessment(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.field_assessment import load_for_job

    return load_for_job(db, user, job_id)


@router.put("/jobs/{job_id}/assessment")
def my_job_assessment_save(
    job_id: int,
    data: FieldAssessmentSave,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.field_assessment import save_for_job
    from app.livewell.visit_location import require

    if data.complete:
        require(data.latitude, data.longitude, "checkout")
    return save_for_job(db, user, job_id, data.model_dump())


@router.post("/jobs/{job_id}/photos")
async def my_job_photo(
    job_id: int,
    file: UploadFile = File(...),
    room_type: str | None = Form(None),
    caption: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.field_assessment import add_photo

    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        from app.core.responses import raise_bad_request

        raise_bad_request("Photo is too large (max 12 MB)")
    return add_photo(
        db,
        user,
        job_id,
        file_name=file.filename or "photo.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        room_type=room_type,
        caption=caption,
    )


@router.get("/jobs/{job_id}/suggestions")
def my_job_suggestions(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.field_assessment import suggestions_for_job

    return suggestions_for_job(db, user, job_id)



class VisitReportIn(BaseModel):
    checks: dict = Field(default_factory=dict)
    kushlife: dict | None = None
    checklist: dict | list | None = None
    note: str = ""
    hazard: dict | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)


@router.post("/jobs/{job_id}/report")
def my_job_report(
    job_id: int,
    data: VisitReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """Finish a visit or install: KushLife check, note for the family, optional new hazard."""
    from app.livewell.visit_location import require
    from app.livewell.visit_reports import complete_with_report

    require(data.latitude, data.longitude, "checkout")
    return complete_with_report(db, user, job_id, data.model_dump())


@router.get("/products")
def my_products(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """Product names for flagging a hazard (no prices)."""
    from app.livewell.commerce import ensure_default_products
    from app.models.commerce import Product

    ensure_default_products(db, user.tenant_id)
    rows = db.query(Product).filter(Product.tenant_id == user.tenant_id, Product.active.is_(True))
    return [{"id": p.id, "name": p.name} for p in rows.order_by(Product.sort_order).all()]


# --- Staff-raised emergency (Phase 3D): the caregiver raises it on a client ---


class CaregiverEmergencyRaise(BaseModel):
    elder_id: int
    type: str = Field(..., max_length=40)
    reported_by: str = Field(default="caregiver", max_length=40)
    reporter_phone: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    job_id: int | None = None


def _my_emergency_view(db: Session, row) -> dict:
    from app.livewell.emergency_service import STEPS

    d = row.details if isinstance(row.details, dict) else {}
    owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
    return {
        "id": row.id,
        "elder_id": row.elder_id,
        "status": row.status,
        "type_label": d.get("type_label"),
        "opened_at": row.opened_at,
        "owner_name": f"{owner.first_name or ''} {owner.last_name or ''}".strip() if owner else None,
        "steps_done": [STEPS[k] for k in (d.get("steps") or {}) if k in STEPS],
        "outcome": row.outcome,
    }


@router.get("/emergency/options")
def my_emergency_options(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.emergency_service import EMERGENCY_TYPES, REPORTERS

    return {
        "types": [{"value": k, "label": v} for k, v in EMERGENCY_TYPES.items()],
        "reporters": [{"value": k, "label": v} for k, v in REPORTERS.items()],
    }


@router.post("/emergency")
def my_emergency_raise(
    data: CaregiverEmergencyRaise,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """Raise an emergency for one of the caregiver's own clients."""
    from fastapi import HTTPException

    from app.livewell.emergency_service import caregiver_elder_ids, raise_emergency
    from app.models.elder import Elder

    elder = db.get(Elder, data.elder_id)
    if (
        not elder
        or elder.tenant_id != user.tenant_id
        or elder.id not in caregiver_elder_ids(db, user.caregiver_id)
    ):
        raise HTTPException(status_code=404, detail="Client not found")
    # Only keep a job id that is this caregiver's visit for this client.
    job_id = None
    if data.job_id:
        from app.models.care_job import CareJob

        job = db.get(CareJob, data.job_id)
        if job and job.caregiver_id == user.caregiver_id and job.elder_id == elder.id:
            job_id = job.id
    row, created = raise_emergency(
        db, user, elder=elder, emergency_type=data.type, reported_by=data.reported_by,
        reporter_phone=data.reporter_phone, note=data.note, job_id=job_id,
    )
    return {**_my_emergency_view(db, row), "created": created}


@router.get("/emergency")
def my_emergencies(
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """Open emergencies on the caregiver's clients (status only)."""
    from app.livewell.emergency_service import KIND, caregiver_elder_ids
    from app.models.incident import OPEN_STATUSES, Incident

    ids = caregiver_elder_ids(db, user.caregiver_id)
    rows = (
        db.query(Incident)
        .filter(
            Incident.tenant_id == user.tenant_id,
            Incident.kind == KIND,
            Incident.status.in_(list(OPEN_STATUSES)),
            Incident.elder_id.in_(ids or {-1}),
        )
        .order_by(Incident.id.desc())
        .all()
    )
    return [_my_emergency_view(db, r) for r in rows]


class AssessmentClientSave(BaseModel):
    details: dict = Field(default_factory=dict)
    location: dict = Field(default_factory=dict)
    beneficiaries: list = Field(default_factory=list)


@router.put("/jobs/{job_id}/assessment/client")
def my_job_assessment_client(
    job_id: int,
    data: AssessmentClientSave,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    from app.livewell.field_assessment import save_client

    return save_client(db, user, job_id, data.model_dump())
