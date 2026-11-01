from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.supplier_service import HomeSafetySupplierService
from app.models.user import User
from app.schemas.home_safety_suppliers import SupplierDirectory

router = APIRouter(prefix="/home-safety/suppliers", tags=["Safe Home — Suppliers"])


@router.get("", response_model=SupplierDirectory)
def get_home_safety_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetySupplierService.get_suppliers(db, current_user)


@router.put("", response_model=SupplierDirectory)
def save_home_safety_suppliers(
    data: SupplierDirectory,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetySupplierService.save_suppliers(db, current_user, data.model_dump())
