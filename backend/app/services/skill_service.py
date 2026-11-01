from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access
from app.core.responses import raise_conflict, raise_not_found
from app.models.caregiver import Caregiver
from app.models.caregiver_skill import CaregiverSkill
from app.models.elder import Elder
from app.models.elder_requirement import ElderRequirement
from app.models.skill import Skill
from app.models.user import User
from app.schemas.skill import (
    CaregiverSkillCreate,
    ElderRequirementCreate,
    SkillCreate,
)


class SkillService:

    @staticmethod
    def list_skills(db: Session) -> list[Skill]:
        return db.query(Skill).order_by(Skill.name).all()

    @staticmethod
    def create_skill(db: Session, data: SkillCreate) -> Skill:
        if db.query(Skill).filter(Skill.code == data.code).first():
            raise_conflict("Skill code already exists")
        skill = Skill(
            code=data.code,
            name=data.name,
            category=data.category,
            description=data.description,
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    @staticmethod
    def add_elder_requirement(
        db: Session,
        elder_id: int,
        data: ElderRequirementCreate,
        user: User,
    ) -> ElderRequirement:
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder.id)
        if not db.query(Skill).filter(Skill.id == data.skill_id).first():
            raise_not_found("Skill not found")

        req = ElderRequirement(
            elder_id=elder_id,
            skill_id=data.skill_id,
            required=data.required,
            weight=data.weight,
            notes=data.notes,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return req

    @staticmethod
    def list_elder_requirements(
        db: Session,
        elder_id: int,
        user: User,
    ) -> list[ElderRequirement]:
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder.id)
        return (
            db.query(ElderRequirement)
            .filter(ElderRequirement.elder_id == elder_id)
            .all()
        )

    @staticmethod
    def add_caregiver_skill(
        db: Session,
        caregiver_id: int,
        data: CaregiverSkillCreate,
        user: User,
    ) -> CaregiverSkill:
        caregiver = (
            db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        )
        if not caregiver:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, caregiver.tenant_id)
        from app.core.team_scope import assert_caregiver_in_team

        assert_caregiver_in_team(db, user, caregiver.id)
        if not db.query(Skill).filter(Skill.id == data.skill_id).first():
            raise_not_found("Skill not found")

        row = CaregiverSkill(
            caregiver_id=caregiver_id,
            skill_id=data.skill_id,
            experience_years=data.experience_years,
            certified=data.certified,
            certification_reference=data.certification_reference,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_caregiver_skills(
        db: Session,
        caregiver_id: int,
        user: User,
    ) -> list[CaregiverSkill]:
        caregiver = (
            db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        )
        if not caregiver:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, caregiver.tenant_id)
        from app.core.team_scope import assert_caregiver_in_team

        assert_caregiver_in_team(db, user, caregiver.id)
        return (
            db.query(CaregiverSkill)
            .filter(CaregiverSkill.caregiver_id == caregiver_id)
            .all()
        )
