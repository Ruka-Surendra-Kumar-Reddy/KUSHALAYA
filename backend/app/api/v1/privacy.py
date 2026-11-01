"""DPDP (#104) and backup status (#105) endpoints.

Family:  /home-safety/family/privacy/*   (consent, download my data, delete my account)
Public:  /home-safety/privacy/notice      (the versioned privacy notice)
Admins:  /home-safety/privacy/requests/*  (delete-request review queue), /backup-status
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import SYSTEM_ADMIN, TENANT_ADMIN, require_elder_portal, require_roles
from app.livewell import privacy
from app.models.user import User

family_router = APIRouter(prefix="/home-safety/family/privacy", tags=["Privacy (DPDP) — family"])
router = APIRouter(prefix="/home-safety/privacy", tags=["Privacy (DPDP) — admin"])

require_admin = require_roles(SYSTEM_ADMIN, TENANT_ADMIN)


class ElderConsentIn(BaseModel):
    elder_id: int
    purposes: dict[str, bool] = {}
    consented_by_name: str | None = None
    relationship: str | None = None


class ConsentIn(BaseModel):
    purposes: dict[str, bool] = {}
    consented_by_name: str | None = None
    elders: list[ElderConsentIn] = []


class DeleteRequestIn(BaseModel):
    scope: str = "account"
    reason: str | None = None


class ReviewIn(BaseModel):
    note: str | None = None


@router.get("/notice")
def privacy_notice(db: Session = Depends(get_db)):
    return privacy.notice_payload(db)


@family_router.get("/notice")
def family_privacy_notice(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return privacy.notice_payload(db, user.tenant_id)


@family_router.get("/consent")
def family_consent_status(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return privacy.consent_status(db, user)


@family_router.post("/consent")
def family_record_consent(
    payload: ConsentIn, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)
):
    return privacy.record_consent(db, user, payload.model_dump())


@family_router.get("/export")
def family_export(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    body, filename = privacy.export_zip(db, user)
    return Response(
        content=body,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@family_router.post("/delete-request")
def family_delete_request(
    payload: DeleteRequestIn, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)
):
    return privacy.request_delete(db, user, scope=payload.scope, reason=payload.reason)


@router.get("/requests")
def admin_list_requests(
    status: str | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    return privacy.list_requests(db, admin, status)


@router.post("/requests/{request_id}/approve")
def admin_approve_request(
    request_id: int, payload: ReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    return privacy.approve_request(db, admin, request_id, payload.note)


@router.post("/requests/{request_id}/reject")
def admin_reject_request(
    request_id: int, payload: ReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    return privacy.reject_request(db, admin, request_id, payload.note)


@router.get("/backup-status")
def admin_backup_status(admin: User = Depends(require_admin)):
    return privacy.backup_status()
