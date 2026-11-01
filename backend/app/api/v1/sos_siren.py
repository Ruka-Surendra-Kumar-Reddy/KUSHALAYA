"""SOS siren (C1): the polling endpoint every portal uses, acknowledge, and the
care-team-first steps (confirm / notify family / false alarm). See app/livewell/sos_siren.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import WRITE_ROLES, require_roles
from app.livewell import sos_siren
from app.models.user import User

router = APIRouter(prefix="/sos-siren", tags=["SOS siren"])


class FalseAlarmBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("/active")
def active(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Unacknowledged SOS alerts for the signed-in person (staff, caregiver or family)."""
    return sos_siren.active_for(db, current_user)


@router.post("/{alert_id}/acknowledge")
def acknowledge(alert_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return sos_siren.acknowledge(db, alert_id, current_user)


@router.post("/incidents/{incident_id}/confirm")
def confirm(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    row = sos_siren.confirm(db, incident_id, current_user)
    return {"ok": True, "incident_id": row.id, "status": row.status}


class NotifyFamilyBody(BaseModel):
    message: str | None = Field(default=None, max_length=300)


@router.post("/incidents/{incident_id}/notify-family")
def notify_family(
    incident_id: int,
    body: NotifyFamilyBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """After confirming: alert all the client's family logins (owner, 29 Oct)."""
    row = sos_siren.notify_family(db, incident_id, current_user, message=body.message if body else None)
    return {"ok": True, "incident_id": row.id, "status": row.status}


@router.post("/incidents/{incident_id}/false-alarm")
def false_alarm(
    incident_id: int,
    body: FalseAlarmBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    row = sos_siren.false_alarm(db, incident_id, current_user, note=body.note if body else None)
    return {"ok": True, "incident_id": row.id, "status": row.status}
