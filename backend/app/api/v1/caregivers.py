"""Caregiver roster (caregivers table) — list/CRUD. Admins create for anyone; a
manager's new caregiver joins their own team (same rule as POST /team/caregivers)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.models.user import User
from app.schemas.caregiver import CaregiverCreate, CaregiverResponse, CaregiverUpdate
from app.services.caregiver_service import CaregiverService

router = APIRouter(prefix="/caregivers", tags=["Caregivers"])


@router.get("", response_model=list[CaregiverResponse])
def list_caregivers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return CaregiverService.list_caregivers(db, current_user)


@router.get("/{caregiver_id}", response_model=CaregiverResponse)
def get_caregiver(
    caregiver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return CaregiverService.get_caregiver(db, caregiver_id, current_user)


@router.post("", response_model=CaregiverResponse)
def create_caregiver(
    data: CaregiverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return CaregiverService.create_caregiver(db, data, current_user)


@router.put("/{caregiver_id}", response_model=CaregiverResponse)
@router.patch("/{caregiver_id}", response_model=CaregiverResponse)
def update_caregiver(
    caregiver_id: int,
    data: CaregiverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return CaregiverService.update_caregiver(db, caregiver_id, data, current_user)


@router.delete("/{caregiver_id}")
def delete_caregiver(
    caregiver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    CaregiverService.delete_caregiver(db, caregiver_id, current_user)
    return {"status": "deactivated"}
