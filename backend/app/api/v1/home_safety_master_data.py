from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.master_data_service import HomeSafetyMasterDataService
from app.models.user import User
from app.schemas.home_safety_master_data import (
    MasterDataApproveRequest,
    MasterDataApproveResult,
    MasterDataCurrentSummary,
    MasterDataImportResult,
    MasterDataStagedPricingUpdate,
    MasterDataSyncStatus,
    MasterDataVersionSummary,
)

router = APIRouter(prefix="/home-safety/master-data", tags=["Safe Home — Master Data"])


@router.get("/current", response_model=MasterDataCurrentSummary)
def get_master_data_current(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Counts for config live in this tenant (what Catalog/Rubric/etc. use now)."""
    return HomeSafetyMasterDataService.get_current_summary(db, current_user)


@router.get("/sync-status", response_model=MasterDataSyncStatus)
def get_master_data_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Empty / dirty / upload-id status vs last approved spreadsheet baseline."""
    return HomeSafetyMasterDataService.get_sync_status(db, current_user)


@router.get("/export")
def export_master_workbook(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    data = HomeSafetyMasterDataService.export_workbook(db, current_user)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Kushalaya_Configuration.xlsx"'},
    )


@router.post("/import", response_model=MasterDataImportResult)
async def import_master_workbook(
    file: UploadFile = File(...),
    comments: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    raw = await file.read()
    return HomeSafetyMasterDataService.import_workbook(
        db,
        current_user,
        raw,
        comments,
        filename=file.filename,
    )


@router.get("/import/{version_id}", response_model=MasterDataImportResult)
def get_staged_import(
    version_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyMasterDataService.get_staged(db, current_user, version_id)


@router.put("/import/{version_id}/pricing", response_model=MasterDataImportResult)
def update_staged_import_pricing(
    version_id: str,
    body: MasterDataStagedPricingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyMasterDataService.update_staged_pricing(
        db,
        current_user,
        version_id,
        body.pricing.model_dump(),
    )


@router.post("/import/approve", response_model=MasterDataApproveResult)
def approve_master_import(
    body: MasterDataApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    result = HomeSafetyMasterDataService.approve_import(
        db,
        current_user,
        body.version_id,
        confirm_catalog_photo_loss=body.confirm_catalog_photo_loss,
    )
    return {
        "version_id": result["version_id"],
        "status": result["status"],
        "applied": result["applied"],
        "upload_id": result.get("upload_id") or result["version_id"],
    }


@router.get("/versions", response_model=list[MasterDataVersionSummary])
def list_master_versions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyMasterDataService.list_versions(db, current_user)


@router.post("/rollback/{version_id}")
def rollback_master_version(
    version_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyMasterDataService.rollback(db, current_user, version_id)


@router.post("/seed-defaults", response_model=MasterDataImportResult)
def seed_master_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Stage factory Kushalaya_Configuration.xlsx for review/approve (does not write live config)."""
    return HomeSafetyMasterDataService.seed_defaults(db, current_user)
