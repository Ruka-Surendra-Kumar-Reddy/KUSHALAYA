"""AI room hazard check API (staff) + confirmed-only view for families."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_elder_portal, require_roles
from app.livewell import ai_hazard_check as svc
from app.livewell.ai_usage import usage_summary
from app.livewell.photo_service import HomeSafetyPhotoService
from app.models.user import User
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/home-safety/ai/hazard-checks", tags=["Safe Home — AI hazard check"])
usage_router = APIRouter(prefix="/home-safety/ai", tags=["Safe Home — AI usage"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family"])


class HazardCheckStart(BaseModel):
    document_id: int
    room_type: str | None = Field(default=None, max_length=32)
    assessment_id: str | None = Field(default=None, max_length=64)
    force: bool = False


class HazardDecision(BaseModel):
    decision: Literal["confirm", "reject"]
    rating: Literal["unsafe", "acceptable"] | None = None


class CarryOver(BaseModel):
    assessment_id: str = Field(max_length=64)


def _schedule(background: BackgroundTasks, db: Session, row, needs_run: bool) -> None:
    if not needs_run:
        return
    bind = db.get_bind()
    background.add_task(svc.run_check, lambda: Session(bind=bind), row.id)


def _log(db: Session, request: Request, user: User, row, action: str) -> None:
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action=action,
        summary=f"AI room check {row.public_id} · photo #{row.document_id} · {row.room_type or 'room'}",
        entity_type="assessment" if row.assessment_id else "photo",
        entity_id=row.assessment_id or str(row.document_id),
        meta={"check_id": row.public_id, "cache_hit": bool(row.cache_hit)},
        commit=True,
    )


@router.post("")
def start_hazard_check(
    data: HazardCheckStart,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    row, needs_run = svc.start_check(
        db,
        current_user,
        document_id=data.document_id,
        room_type=data.room_type,
        assessment_id=data.assessment_id,
        force=data.force,
    )
    if needs_run:
        _log(db, request, current_user, row, "Ran AI room check")
    _schedule(background, db, row, needs_run)
    return svc.get_check(db, current_user, row.public_id)


@router.post("/upload")
async def upload_and_check(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    elder_id: int = Form(...),
    room_type: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Client page "Check a room": save the photo against the client, then check it."""
    from app.core.team_scope import assert_elder_in_team

    assert_elder_in_team(db, current_user, elder_id)
    content = await file.read()
    if not content:
        from app.core.responses import raise_bad_request

        raise_bad_request("The photo is empty.")
    doc = HomeSafetyPhotoService.upload(
        db,
        current_user,
        file_name=file.filename or "room.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        caption="Room check",
        assessment_id=None,
        prospect_id=None,
        elder_id=elder_id,
        room_type=room_type,
    )
    row, needs_run = svc.start_check(db, current_user, document_id=doc.id, room_type=room_type)
    if needs_run:
        _log(db, request, current_user, row, "Ran AI room check")
    _schedule(background, db, row, needs_run)
    return svc.get_check(db, current_user, row.public_id)


@router.get("")
def list_hazard_checks(
    assessment_id: str | None = Query(None),
    elder_id: int | None = Query(None),
    document_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.list_checks(
        db, current_user, assessment_id=assessment_id, elder_id=elder_id, document_id=document_id
    )


@router.get("/pending")
def pending_for_reassessment(
    elder_id: int = Query(...),
    assessment_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return {"hazards": svc.pending_carry_over(db, current_user, elder_id, exclude_assessment=assessment_id)}


@router.post("/carry-over")
def carry_over(
    data: CarryOver,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return svc.carry_over(db, current_user, data.assessment_id)


@router.get("/{check_id}")
def get_hazard_check(
    check_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.get_check(db, current_user, check_id)


@router.post("/{check_id}/hazards/{n}")
def decide_hazard(
    check_id: str,
    n: int,
    data: HazardDecision,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    out = svc.decide(db, current_user, check_id, n, decision=data.decision, rating=data.rating)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Confirmed AI hazard" if data.decision == "confirm" else "Rejected AI hazard",
        summary=f"AI room check {check_id} · hazard {n}",
        entity_type="assessment" if out.get("assessment_id") else "photo",
        entity_id=out.get("assessment_id") or str(out.get("document_id")),
        meta={"check_id": check_id, "n": n, "decision": data.decision},
        commit=True,
    )
    return out


@usage_router.get("/usage-summary")
def ai_usage(
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.core.rbac import resolve_tenant_id

    return usage_summary(db, resolve_tenant_id(current_user), days=days)


@family_router.get("/room-hazards")
def family_room_hazards(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Hazards our staff confirmed in the home — plain words only."""
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, current_user)
    return svc.family_hazards(db, elder.id, elder.tenant_id)
