"""Customer-spine client list (shared `elders` table) for SafeHome visits/family linking."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (
    ADMIN_ROLES,
    CARE_MANAGER,
    READ_ROLES,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    WRITE_ROLES,
    require_roles,
    resolve_tenant_id,
)
from app.livewell.family_elder_link import republish_latest_assessment_for_elder
from app.livewell.family_elder_access import find_family_user_for_elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User
from app.schemas.auth import ElderPortalAccountCreate, TokenResponse, UserResponse
from app.schemas.elder import ElderCreate, ElderResponse, ElderUpdate
from app.services.customer_delete_service import CustomerDeleteService
from app.services.elder_portal_service import ElderPortalService
from app.services.elder_service import ElderService

router = APIRouter(prefix="/elders", tags=["Clients"])

# custom_attributes keys only the system (or an admin) may write.
PROTECTED_ATTRIBUTES = {"safe_home", "kushlife_ack", "kushlife_baseline"}


def _safe_home_block(elder) -> dict:
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    sh = attrs.get("safe_home")
    return sh if isinstance(sh, dict) else {}


def _family_published(sh: dict) -> tuple[bool, int | None]:
    score = sh.get("safety_score") if isinstance(sh.get("safety_score"), dict) else None
    if not score:
        return False, None
    if score.get("is_demo"):
        return False, None
    total = score.get("total")
    if total is None:
        return False, None
    try:
        return True, int(total)
    except (TypeError, ValueError):
        return True, None


def _latest_assessment(
    db: Session,
    *,
    tenant_id: int | None,
    elder_id: int,
    prospect_id: int | None,
) -> tuple[str | None, str | None]:
    from sqlalchemy import or_

    clauses = [HomeSafetyAssessmentRecord.elder_id == elder_id]
    if prospect_id is not None:
        clauses.append(HomeSafetyAssessmentRecord.prospect_id == prospect_id)
    q = db.query(HomeSafetyAssessmentRecord).filter(or_(*clauses))
    if tenant_id is not None:
        q = q.filter(HomeSafetyAssessmentRecord.tenant_id == tenant_id)
    row = q.order_by(HomeSafetyAssessmentRecord.updated_at.desc()).first()
    if not row:
        return None, None
    return str(row.assessment_id), str(row.status or "")


def _next_step(
    *,
    family_published: bool,
    latest_status: str | None,
    linked_prospect_id: int | None,
) -> str:
    if family_published:
        return "Family portal is up to date — log visits or update the plan as needed."
    if latest_status == "draft":
        return "Finish the draft assessment (100% checklist) and Save to publish to family."
    if latest_status == "completed":
        return "Assessment saved but family score missing — use Republish to family."
    if linked_prospect_id:
        return "Start an assessment for this client (link the prospect on intake)."
    return "Start an assessment, or link an open prospect to this client."


def _absorb_legacy_won_prospects(db: Session, tenant_id: int | None) -> None:
    """Move leftover converted leads onto their clients (pre-absorb-on-convert data)."""
    from app.livewell.family_elder_link import absorb_prospect_into_elder

    q = db.query(ElderProspect).filter(ElderProspect.converted_elder_id.isnot(None))
    if tenant_id is not None:
        q = q.filter(ElderProspect.tenant_id == tenant_id)
    rows = q.all()
    if not rows:
        return
    for row in rows:
        absorb_prospect_into_elder(
            db, prospect_id=int(row.id), elder_id=int(row.converted_elder_id)
        )
    try:
        db.commit()
    except Exception:
        db.rollback()


def _elder_response_enriched(db: Session, elder, *, tenant_id: int | None) -> ElderResponse:
    sh = _safe_home_block(elder)
    published, score_total = _family_published(sh)
    assess_id, assess_status = _latest_assessment(
        db,
        tenant_id=tenant_id,
        elder_id=int(elder.id),
        prospect_id=None,
    )
    family_user = find_family_user_for_elder(db, int(elder.id))

    base = ElderResponse.model_validate(elder)
    return base.model_copy(
        update={
            "linked_prospect_id": None,
            "linked_prospect_name": None,
            "family_published": published,
            "independence_score": score_total,
            "latest_assessment_id": assess_id,
            "latest_assessment_status": assess_status,
            "family_email": family_user.email if family_user else None,
            "next_step": _next_step(
                family_published=published,
                latest_status=assess_status,
                linked_prospect_id=None,
            ),
        }
    )


@router.get("", response_model=list[ElderResponse])
def list_elders(
    include_leads: bool = Query(False, description="Also leads being assessed (Room checks)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    tid = resolve_tenant_id(current_user)
    _absorb_legacy_won_prospects(db, tid)
    from app.livewell.assessment_start import is_lead_record

    # Hidden records made to assess a lead (not a client yet) stay out of the list.
    elders = [e for e in ElderService.list_elders(db, current_user) if include_leads or not is_lead_record(e)]
    return [
        _elder_response_enriched(db, e, tenant_id=tid).model_copy(update={"is_lead": is_lead_record(e)})
        for e in elders
    ]


@router.get("/{elder_id}", response_model=ElderResponse)
def get_elder(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    elder = ElderService.get_elder(db, elder_id, current_user)
    return _elder_response_enriched(
        db, elder, tenant_id=resolve_tenant_id(current_user)
    )


@router.post("/{elder_id}/republish-assessment")
def republish_assessment_to_family(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Re-run family publish from the latest completed assessment for this client."""
    elder = ElderService.get_elder(db, elder_id, current_user)
    ok = republish_latest_assessment_for_elder(
        db,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        prospect_id=None,
    )
    db.commit()
    if not ok:
        return {
            "ok": False,
            "message": "No completed assessment found for this client.",
            "elder": _elder_response_enriched(
                db, elder, tenant_id=resolve_tenant_id(current_user)
            ),
        }
    db.refresh(elder)
    return {
        "ok": True,
        "message": "Published latest assessment to the family portal.",
        "elder": _elder_response_enriched(
            db, elder, tenant_id=resolve_tenant_id(current_user)
        ),
    }


@router.post("", response_model=ElderResponse)
def create_elder(
    data: ElderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ElderService.create_elder(db, data, current_user)


@router.put("/{elder_id}", response_model=ElderResponse)
def update_elder(
    elder_id: int,
    data: ElderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    if current_user.role not in ADMIN_ROLES:
        # Managers edit details only: not the client's status, and not the
        # system-written blocks (published score, KushLife acknowledgements).
        fields = data.model_dump(exclude_unset=True)
        fields.pop("status", None)
        attrs = fields.pop("custom_attributes", None)
        if isinstance(attrs, dict):
            attrs = {k: v for k, v in attrs.items() if k not in PROTECTED_ATTRIBUTES}
            if attrs:
                fields["custom_attributes"] = attrs
        data = ElderUpdate(**fields)
    return ElderService.update_elder(db, elder_id, data, current_user)


@router.delete("/{elder_id}")
def deactivate_elder(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Soft-delete: mark client INACTIVE."""
    ElderService.delete_elder(db, elder_id, current_user)
    return {"status": "deactivated"}


@router.delete("/{elder_id}/permanent")
def permanently_delete_elder(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Hard-delete client and related care/assessment links (admin only)."""
    return CustomerDeleteService.permanently_delete_elder(db, elder_id, current_user)


@router.post("/{elder_id}/login-as-family", response_model=TokenResponse)
def login_as_family(
    elder_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER)),
):
    """Open this client's family portal as their family login (staff admin)."""
    return ElderPortalService.login_as_family(db, elder_id, current_user, request=request)


@router.post("/{elder_id}/portal-account", response_model=UserResponse)
def create_elder_portal_account(
    elder_id: int,
    data: ElderPortalAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return ElderPortalService.create_portal_account(db, elder_id, data, current_user)
