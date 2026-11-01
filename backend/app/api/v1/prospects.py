from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pipeline_constants import (
    CAREGIVER_PROSPECT_STAGES,
    ELDER_PROSPECT_STAGES,
)
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_roles
from app.models.user import User
from app.schemas.prospects import (
    ActivityCreate,
    ActivityResponse,
    AssignableOwner,
    CaregiverProspectCreate,
    CaregiverProspectResponse,
    CaregiverProspectUpdate,
    ConvertCaregiverResponse,
    ConvertElderRequest,
    ConvertElderResponse,
    ElderProspectCreate,
    ElderProspectResponse,
    ElderProspectUpdate,
    PipelineStagesResponse,
    StageUpdateRequest,
)
from app.schemas.recruitment import (
    PlacementSuggestionsResponse,
    ResumeAttachResponse,
    ResumeParseResponse,
)
from app.services.customer_delete_service import CustomerDeleteService
from app.services.prospect_service import ProspectService
from app.services.resume_intelligence_service import ResumeIntelligenceService

router = APIRouter(prefix="/prospects", tags=["Pipeline / Prospects"])


@router.get("/stages", response_model=PipelineStagesResponse)
def pipeline_stages(
    _user: User = Depends(require_roles(*READ_ROLES)),
):
    return PipelineStagesResponse(
        elder_stages=list(ELDER_PROSPECT_STAGES),
        caregiver_stages=list(CAREGIVER_PROSPECT_STAGES),
    )


@router.get("/owners", response_model=list[AssignableOwner])
def assignable_owners(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    users = ProspectService.list_assignable_owners(db, current_user)
    return [
        AssignableOwner(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            role=u.role,
        )
        for u in users
    ]


# --- Elder prospects ---


@router.get("/elders", response_model=list[ElderProspectResponse])
def list_elder_prospects(
    status: str | None = Query(None),
    stage: str | None = Query(None),
    owner_user_id: int | None = Query(None),
    overdue_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return ProspectService.list_elder_prospects(
        db,
        current_user,
        status=status,
        stage=stage,
        owner_user_id=owner_user_id,
        overdue_only=overdue_only,
    )


@router.post("/elders", response_model=ElderProspectResponse)
def create_elder_prospect(
    data: ElderProspectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.create_elder_prospect(db, data, current_user)


@router.get("/elders/{prospect_id}", response_model=ElderProspectResponse)
def get_elder_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    row = ProspectService.get_elder_prospect(db, prospect_id, current_user)
    return ProspectService._elder_dict(db, row)


@router.patch("/elders/{prospect_id}", response_model=ElderProspectResponse)
def update_elder_prospect(
    prospect_id: int,
    data: ElderProspectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.update_elder_prospect(db, prospect_id, data, current_user)


@router.patch("/elders/{prospect_id}/stage", response_model=ElderProspectResponse)
def set_elder_stage(
    prospect_id: int,
    data: StageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.set_elder_stage(
        db,
        prospect_id,
        data.stage,
        current_user,
        lost_reason=data.lost_reason,
    )


@router.post("/elders/{prospect_id}/convert", response_model=ConvertElderResponse)
def convert_elder_prospect(
    prospect_id: int,
    data: ConvertElderRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.convert_elder_prospect(
        db,
        prospect_id,
        current_user,
        link_to_elder_id=data.elder_id if data else None,
    )


@router.post("/elders/{prospect_id}/unlink", response_model=ElderProspectResponse)
def unlink_elder_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Clear prospect↔client link and reopen the prospect (admin/staff)."""
    return ProspectService.unlink_elder_prospect(db, prospect_id, current_user)


@router.delete("/elders/{prospect_id}/permanent")
def permanently_delete_elder_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Hard-delete an elder prospect and its pipeline activity (admin only)."""
    return CustomerDeleteService.permanently_delete_elder_prospect(
        db, prospect_id, current_user
    )


@router.get("/elders/{prospect_id}/activities", response_model=list[ActivityResponse])
def list_elder_activities(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return ProspectService.list_elder_activities(db, prospect_id, current_user)


@router.post("/elders/{prospect_id}/activities", response_model=ActivityResponse)
def add_elder_activity(
    prospect_id: int,
    data: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.add_elder_activity(db, prospect_id, data, current_user)


# --- Caregiver prospects ---


@router.get("/caregivers", response_model=list[CaregiverProspectResponse])
def list_caregiver_prospects(
    status: str | None = Query(None),
    stage: str | None = Query(None),
    owner_user_id: int | None = Query(None),
    overdue_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return ProspectService.list_caregiver_prospects(
        db,
        current_user,
        status=status,
        stage=stage,
        owner_user_id=owner_user_id,
        overdue_only=overdue_only,
    )


@router.post("/caregivers", response_model=CaregiverProspectResponse)
def create_caregiver_prospect(
    data: CaregiverProspectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.create_caregiver_prospect(db, data, current_user)


@router.get("/caregivers/{prospect_id}", response_model=CaregiverProspectResponse)
def get_caregiver_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    row = ProspectService.get_caregiver_prospect(db, prospect_id, current_user)
    return ProspectService._caregiver_dict(db, row)


@router.patch("/caregivers/{prospect_id}", response_model=CaregiverProspectResponse)
def update_caregiver_prospect(
    prospect_id: int,
    data: CaregiverProspectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.update_caregiver_prospect(
        db, prospect_id, data, current_user
    )


@router.patch("/caregivers/{prospect_id}/stage", response_model=CaregiverProspectResponse)
def set_caregiver_stage(
    prospect_id: int,
    data: StageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    updates = CaregiverProspectUpdate(stage=data.stage, lost_reason=data.lost_reason)
    return ProspectService.update_caregiver_prospect(
        db, prospect_id, updates, current_user
    )


@router.post(
    "/caregivers/{prospect_id}/convert",
    response_model=ConvertCaregiverResponse,
)
def convert_caregiver_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.convert_caregiver_prospect(db, prospect_id, current_user)


@router.get(
    "/caregivers/{prospect_id}/activities",
    response_model=list[ActivityResponse],
)
def list_caregiver_activities(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return ProspectService.list_caregiver_activities(db, prospect_id, current_user)


@router.get(
    "/caregivers/{prospect_id}/placement-suggestions",
    response_model=PlacementSuggestionsResponse,
)
def caregiver_placement_suggestions(
    prospect_id: int,
    limit: int = Query(default=5, ge=1, le=10),
    min_score: float = Query(default=40.0, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Rank open client demand for this recruit (uses resume + matching)."""
    from app.core.responses import raise_bad_request

    raise_bad_request("Placement suggestions are not available in SafeHomeOps")


@router.post(
    "/caregivers/{prospect_id}/resume",
    response_model=ResumeAttachResponse,
)
async def upload_caregiver_resume(
    prospect_id: int,
    file: UploadFile = File(...),
    apply_fields: bool = Form(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    content = await file.read()
    result = ResumeIntelligenceService.attach_to_prospect(
        db,
        prospect_id,
        content,
        file.content_type or "application/octet-stream",
        file.filename or "resume",
        current_user,
        apply_fields=apply_fields,
    )
    return ResumeAttachResponse(
        prospect=result["prospect"],
        parse=ResumeParseResponse(**result["parse"]),
        document_id=result["document_id"],
    )


@router.post(
    "/caregivers/{prospect_id}/activities",
    response_model=ActivityResponse,
)
def add_caregiver_activity(
    prospect_id: int,
    data: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ProspectService.add_caregiver_activity(db, prospect_id, data, current_user)
