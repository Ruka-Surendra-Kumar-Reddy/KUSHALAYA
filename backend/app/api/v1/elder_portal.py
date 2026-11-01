from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_elder_portal
from app.models.user import User
from app.schemas.elder_portal import (
    CareStatusResponse,
    ElderActivitySummary,
    ElderPortalMeResponse,
    MessageCreate,
    MessageResponse,
    NotificationResponse,
)
from app.services.elder_portal_service import ElderPortalService

router = APIRouter(prefix="/elder-portal", tags=["Elder Portal"])


@router.get("/me", response_model=ElderPortalMeResponse)
def portal_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.portal_me(db, current_user)


@router.get("/activity", response_model=ElderActivitySummary)
def activity_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.activity_summary(db, current_user)


@router.get("/status", response_model=CareStatusResponse)
def care_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.care_status(db, current_user)


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.list_notifications(db, current_user)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.mark_notification_read(
        db, current_user, notification_id
    )


@router.get("/messages", response_model=list[MessageResponse])
def list_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.list_messages(db, current_user)


@router.post("/messages", response_model=MessageResponse)
def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return ElderPortalService.send_message_from_elder(
        db, current_user, data.body
    )
