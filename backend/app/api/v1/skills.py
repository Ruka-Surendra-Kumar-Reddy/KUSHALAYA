from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.models.user import User
from app.schemas.skill import (
    CaregiverSkillCreate,
    ElderRequirementCreate,
    SkillCreate,
    SkillResponse,
)
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("", response_model=list[SkillResponse])
def list_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return SkillService.list_skills(db)


@router.post("", response_model=SkillResponse)
def create_skill(
    data: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return SkillService.create_skill(db, data)


@router.post("/elders/{elder_id}/requirements")
def add_elder_requirement(
    elder_id: int,
    data: ElderRequirementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    req = SkillService.add_elder_requirement(db, elder_id, data, current_user)
    return {
        "id": req.id,
        "elder_id": req.elder_id,
        "skill_id": req.skill_id,
        "weight": req.weight,
    }


@router.get("/elders/{elder_id}/requirements")
def list_elder_requirements(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.models.skill import Skill

    reqs = SkillService.list_elder_requirements(db, elder_id, current_user)
    skill_ids = {r.skill_id for r in reqs}
    skills = {
        s.id: s.name
        for s in db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
    } if skill_ids else {}
    return [
        {
            "id": r.id,
            "elder_id": r.elder_id,
            "skill_id": r.skill_id,
            "skill_name": skills.get(r.skill_id),
            "required": r.required,
            "weight": r.weight,
        }
        for r in reqs
    ]


@router.post("/caregivers/{caregiver_id}/skills")
def add_caregiver_skill(
    caregiver_id: int,
    data: CaregiverSkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    row = SkillService.add_caregiver_skill(db, caregiver_id, data, current_user)
    return {
        "id": row.id,
        "caregiver_id": row.caregiver_id,
        "skill_id": row.skill_id,
        "certified": row.certified,
    }


@router.get("/caregivers/{caregiver_id}/skills")
def list_caregiver_skills(
    caregiver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    rows = SkillService.list_caregiver_skills(db, caregiver_id, current_user)
    return [
        {
            "id": r.id,
            "caregiver_id": r.caregiver_id,
            "skill_id": r.skill_id,
            "certified": r.certified,
        }
        for r in rows
    ]
