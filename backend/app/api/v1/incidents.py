"""Staff-side SOS / incident operations: /api/v1/care/incidents."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_roles, resolve_tenant_id
from app.core.team_scope import team_elder_ids
from app.livewell import incident_service
from app.models.incident import INCIDENT_OUTCOMES, INCIDENT_STATUSES
from app.models.user import User
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/care/incidents", tags=["Safe Home — Incidents (staff)"])


class IncidentEventResponse(BaseModel):
    id: int
    at: datetime
    event: str
    channel: str | None = None
    recipient: str | None = None
    ok: bool = True
    detail: str | None = None
    actor_user_id: int | None = None
    actor_name: str | None = None


class IncidentResponse(BaseModel):
    id: int
    tenant_id: int
    elder_id: int
    elder_name: str | None = None
    kind: str
    kind_label: str
    severity: str
    status: str
    source: str
    device_mac: str | None = None
    hub_key: str | None = None
    dedupe_key: str | None = None
    note: str | None = None
    opened_at: datetime
    minutes_open: int
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    escalated_at: datetime | None = None
    escalation_level: int = 0
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    outcome: str | None = None
    resolution_note: str | None = None
    legacy_id: str | None = None
    owner_user_id: int | None = None
    owner_name: str | None = None
    details: dict | None = None
    elder_phone: str | None = None
    elder_address: str | None = None
    family_phone: str | None = None
    family_name: str | None = None
    partners: list[dict] | None = None
    # SOS steps: care team first, family after "Notify family" (sos_siren.summary).
    sos: dict | None = None
    events: list[IncidentEventResponse] | None = None


class IncidentSummaryResponse(BaseModel):
    open: int = 0
    acknowledged: int = 0
    escalated: int = 0
    critical: int = 0
    total: int = 0


class IncidentResolveRequest(BaseModel):
    outcome: str = Field(..., description=" | ".join(INCIDENT_OUTCOMES))
    note: str | None = None


class IncidentNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


class IncidentEscalateRequest(BaseModel):
    reason: str | None = None


class EmergencyRaiseRequest(BaseModel):
    elder_id: int
    type: str = Field(..., max_length=40)
    reported_by: str = Field(..., max_length=40)
    reporter_phone: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    job_id: int | None = None


class EmergencyStepRequest(BaseModel):
    step: str = Field(..., max_length=40)
    hospital_name: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class EmergencyOwnerRequest(BaseModel):
    user_id: int | None = None


class EmergencyCloseRequest(BaseModel):
    outcome: str = Field(..., max_length=40)
    note: str = Field(..., min_length=1, max_length=2000)


class EmergencyPartnerNotifyRequest(BaseModel):
    partner_id: str = Field(..., max_length=40)
    message: str | None = Field(default=None, max_length=500)


def _statuses(raw: str | None) -> list[str]:
    if not raw:
        return ["open", "acknowledged", "escalated"]
    wanted = [s.strip().lower() for s in raw.split(",") if s.strip()]
    if "all" in wanted:
        return list(INCIDENT_STATUSES)
    return [s for s in wanted if s in INCIDENT_STATUSES] or ["open", "acknowledged", "escalated"]


def _log(request: Request, db: Session, user: User, *, action: str, summary: str, incident_id: int) -> None:
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action=action,
        summary=summary,
        entity_type="incident",
        entity_id=str(incident_id),
        commit=True,
    )


def _team_incident(db: Session, user: User, incident_id: int, tid):
    """An incident the user may act on: same agency and, for a care manager, their own team's client."""
    from app.core.team_scope import assert_elder_in_team

    row = incident_service.get_incident(db, incident_id, tenant_id=tid)
    if row.elder_id:
        assert_elder_in_team(db, user, row.elder_id)
    return row


@router.get("/summary", response_model=IncidentSummaryResponse)
def incident_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Counts for the nav badge (open-ish incidents only)."""
    return incident_service.summary(db, resolve_tenant_id(current_user), elder_ids=team_elder_ids(db, current_user))


# --- Staff-raised emergency (Phase 3D). Declared before /{incident_id}. ---


@router.get("/emergency/options")
def emergency_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell import emergency_service

    return emergency_service.options(db, resolve_tenant_id(current_user))


@router.get("/emergency/partners")
def get_emergency_partners(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell import emergency_service
    from app.models.tenant import Tenant

    tid = resolve_tenant_id(current_user)
    return emergency_service.get_config(db.get(Tenant, tid) if tid else None)


@router.put("/emergency/partners")
def put_emergency_partners(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.core.responses import raise_not_found
    from app.livewell import emergency_service
    from app.models.tenant import Tenant

    tid = resolve_tenant_id(current_user)
    tenant = db.get(Tenant, tid) if tid else None
    if not tenant:
        raise_not_found("Agency not found")
    return emergency_service.save_config(db, tenant, body)


@router.post("/emergency", response_model=IncidentResponse)
def raise_emergency(
    body: EmergencyRaiseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """A care manager / admin raises an emergency for a client in their team."""
    from app.core.responses import raise_not_found
    from app.core.team_scope import assert_elder_in_team
    from app.livewell import emergency_service
    from app.models.elder import Elder

    tid = resolve_tenant_id(current_user)
    elder = db.get(Elder, body.elder_id)
    if not elder or (tid is not None and elder.tenant_id != tid):
        raise_not_found("Client not found")
    assert_elder_in_team(db, current_user, elder.id)
    row, _created = emergency_service.raise_emergency(
        db, current_user, elder=elder, emergency_type=body.type, reported_by=body.reported_by,
        reporter_phone=body.reporter_phone, note=body.note, job_id=body.job_id,
    )
    _log(request, db, current_user, action="Raised emergency", summary=f"emergency #{row.id}", incident_id=row.id)
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    status: str | None = Query(default=None, description="comma list; default open,acknowledged,escalated; 'all'"),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.core.team_scope import team_elder_ids

    return incident_service.list_for_tenant(
        db,
        resolve_tenant_id(current_user),
        statuses=_statuses(status),
        limit=limit,
        elder_ids=team_elder_ids(db, current_user),
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    _team_incident(db, current_user, incident_id, resolve_tenant_id(current_user))
    return incident_service.detail_for_tenant(db, resolve_tenant_id(current_user), incident_id)


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(current_user)
    row = _team_incident(db, current_user, incident_id, tid)
    incident_service.acknowledge(db, row, current_user)
    _log(request, db, current_user, action="Acknowledged incident", summary=f"{row.kind} #{row.id}", incident_id=row.id)
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/escalate", response_model=IncidentResponse)
def escalate_incident(
    incident_id: int,
    request: Request,
    body: IncidentEscalateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(current_user)
    row = _team_incident(db, current_user, incident_id, tid)
    incident_service.escalate(
        db,
        row,
        actor_user_id=current_user.id,
        reason=(body.reason if body else None),
    )
    _log(
        request,
        db,
        current_user,
        action="Escalated incident",
        summary=f"{row.kind} #{row.id} → level {row.escalation_level}",
        incident_id=row.id,
    )
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    incident_id: int,
    body: IncidentResolveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(current_user)
    row = _team_incident(db, current_user, incident_id, tid)
    if row.kind == "staff_emergency":
        # Emergencies close through their own rules (outcome + family mirror).
        raise HTTPException(status_code=400, detail="Use Close emergency")
    incident_service.resolve(db, row, outcome=body.outcome, note=body.note, user=current_user)
    _log(
        request,
        db,
        current_user,
        action="Resolved incident",
        summary=f"{row.kind} #{row.id} → {row.outcome}",
        incident_id=row.id,
    )
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/note", response_model=IncidentResponse)
def note_incident(
    incident_id: int,
    body: IncidentNoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(current_user)
    row = _team_incident(db, current_user, incident_id, tid)
    incident_service.add_note(db, row, current_user, body.note)
    _log(request, db, current_user, action="Noted incident", summary=f"{row.kind} #{row.id}", incident_id=row.id)
    return incident_service.detail_for_tenant(db, tid, row.id)


def _team_emergency(db: Session, user: User, incident_id: int):
    from app.livewell import emergency_service

    tid = resolve_tenant_id(user)
    _team_incident(db, user, incident_id, tid)
    return tid, emergency_service._emergency(db, incident_id, tid)


@router.post("/{incident_id}/emergency/step", response_model=IncidentResponse)
def emergency_step(
    incident_id: int,
    body: EmergencyStepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell import emergency_service

    tid, row = _team_emergency(db, current_user, incident_id)
    emergency_service.tick_step(db, row, current_user, body.step, hospital_name=body.hospital_name, note=body.note)
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/emergency/owner", response_model=IncidentResponse)
def emergency_owner(
    incident_id: int,
    body: EmergencyOwnerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell import emergency_service

    tid, row = _team_emergency(db, current_user, incident_id)
    emergency_service.assign_owner(db, row, current_user, body.user_id)
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/emergency/close", response_model=IncidentResponse)
def emergency_close(
    incident_id: int,
    body: EmergencyCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell import emergency_service

    tid, row = _team_emergency(db, current_user, incident_id)
    emergency_service.close(db, row, current_user, outcome=body.outcome, note=body.note)
    _log(request, db, current_user, action="Closed emergency", summary=f"emergency #{row.id} → {row.outcome}", incident_id=row.id)
    return incident_service.detail_for_tenant(db, tid, row.id)


@router.post("/{incident_id}/emergency/notify-partner", response_model=IncidentResponse)
def emergency_notify_partner(
    incident_id: int,
    body: EmergencyPartnerNotifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell import emergency_service

    tid, row = _team_emergency(db, current_user, incident_id)
    emergency_service.notify_partner(db, row, current_user, body.partner_id, message=body.message)
    _log(request, db, current_user, action="Notified emergency partner", summary=f"emergency #{row.id}", incident_id=row.id)
    return incident_service.detail_for_tenant(db, tid, row.id)
