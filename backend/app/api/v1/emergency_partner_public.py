"""Emergency partner hand-off page — no login, the signed link is the key.

``/api/v1/home-safety/emergency-response/{incident_id}/{token}``: mounted under
the Safe Home prefix so nginx already routes it. The token is scoped to one
incident and expires after 48 h (see ``emergency_service``).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell import emergency_service

router = APIRouter(prefix="/home-safety/emergency-response", tags=["Safe Home — Emergency partner"])


class PartnerResponseRequest(BaseModel):
    status: str = Field(..., max_length=20)
    note: str | None = Field(default=None, max_length=500)


@router.get("/{incident_id}/{token}")
def partner_view(incident_id: int, token: str, db: Session = Depends(get_db)):
    try:
        return emergency_service.partner_view(db, incident_id, token[:200])
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # Bad link: no tenant to read, so offer the public care-team number.
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail, **emergency_service.partner_contact(None)},
        )


@router.post("/{incident_id}/{token}")
def partner_respond(incident_id: int, token: str, body: PartnerResponseRequest, db: Session = Depends(get_db)):
    return emergency_service.partner_respond(db, incident_id, token[:200], body.status, body.note)
