from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.pipeline_constants import (
    ACTIVITY_FOLLOW_UP,
    ACTIVITY_NOTE,
    ACTIVITY_OWNER_CHANGE,
    ACTIVITY_STAGE_CHANGE,
    CAREGIVER_PROSPECT_STAGES,
    ELDER_PROSPECT_STAGES,
    PROSPECT_STATUS_LOST,
    PROSPECT_STATUS_OPEN,
    PROSPECT_STATUS_WON,
)
from app.core.rbac import (
    CARE_MANAGER,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    assert_tenant_access,
    resolve_tenant_id,
)
from app.core.responses import raise_bad_request, raise_not_found
from app.core.vertical_guards import require_tenant_feature
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.user import User
from app.livewell.public_enquiry_service import validate_contact
from app.schemas.caregiver import CaregiverCreate
from app.schemas.elder import ElderCreate
from app.schemas.prospects import (
    ActivityCreate,
    CaregiverProspectCreate,
    CaregiverProspectUpdate,
    ElderProspectCreate,
    ElderProspectUpdate,
)
from app.services.audit_service import AuditService
from app.services.caregiver_service import CaregiverService
from app.services.elder_service import ElderService


class ProspectService:

    @staticmethod
    def _assert_caregiver_prospects(db: Session, user: User) -> None:
        require_tenant_feature(db, user, "caregiver_prospects")

    @staticmethod
    def _assert_elder_prospects(db: Session, user: User) -> None:
        require_tenant_feature(db, user, "elder_prospects")

    @staticmethod
    def _tenant_id_for_create(user: User, tenant_id: int | None) -> int:
        tid = resolve_tenant_id(user, tenant_id)
        if tid is None:
            raise_bad_request("tenant_id is required")
        return tid

    @staticmethod
    def _owner_name(db: Session, user_id: int | None) -> str | None:
        if not user_id:
            return None
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return None
        return f"{u.first_name} {u.last_name}".strip()

    @staticmethod
    def _log_activity(
        db: Session,
        *,
        tenant_id: int,
        elder_prospect_id: int | None = None,
        caregiver_prospect_id: int | None = None,
        activity_type: str,
        body: str,
        actor: User,
        metadata: dict | None = None,
    ) -> PipelineActivity:
        row = PipelineActivity(
            tenant_id=tenant_id,
            elder_prospect_id=elder_prospect_id,
            caregiver_prospect_id=caregiver_prospect_id,
            activity_type=activity_type,
            body=body,
            metadata_=metadata,
            created_by_user_id=actor.id,
        )
        db.add(row)
        return row

    @staticmethod
    def _activity_dict(db: Session, row: PipelineActivity) -> dict:
        return {
            "id": row.id,
            "activity_type": row.activity_type,
            "body": row.body,
            "metadata": row.metadata_,
            "created_by_user_id": row.created_by_user_id,
            "created_by_name": ProspectService._owner_name(db, row.created_by_user_id),
            "created_at": row.created_at,
        }

    @staticmethod
    def list_assignable_owners(db: Session, user: User) -> list[User]:
        tid = resolve_tenant_id(user)
        if tid is None:
            return []
        return (
            db.query(User)
            .filter(
                User.tenant_id == tid,
                User.role.in_([TENANT_ADMIN, CARE_MANAGER]),
                User.status == "ACTIVE",
            )
            .order_by(User.first_name, User.last_name)
            .all()
        )

    # --- Elder prospects ---

    @staticmethod
    def _elder_dict(db: Session, row: ElderProspect) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "phone": row.phone,
            "email": row.email,
            "address": row.address,
            "source": row.source,
            "stage": row.stage,
            "status": row.status,
            "owner_user_id": row.owner_user_id,
            "owner_name": ProspectService._owner_name(db, row.owner_user_id),
            "next_follow_up_at": row.next_follow_up_at,
            "lost_reason": row.lost_reason,
            "notes": row.notes,
            "care_level": row.care_level,
            "converted_elder_id": row.converted_elder_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            **ProspectService._lead_fields(db, row),
        }

    @staticmethod
    def _lead_fields(db: Session, row: ElderProspect) -> dict:
        """Website lead tracking (FIX 107/108): where it came from, who referred it."""
        from app.livewell.site_settings import lead_source, referrer_name

        return {
            "lead_source": lead_source(row),
            "utm_source": row.utm_source,
            "utm_medium": row.utm_medium,
            "utm_campaign": row.utm_campaign,
            "referrer_url": row.referrer_url,
            "landing_page": row.landing_page,
            "referral_code": row.referral_code,
            "referred_by": referrer_name(db, row.referral_code, row.tenant_id) if row.referral_code else None,
            "pincode": row.pincode,
            "area_served": row.area_served,
            "assessment_slot": row.assessment_slot,
            "assessment_fee_paise": row.assessment_fee_paise,
            "assessment_paid": row.assessment_paid_at is not None,
        }

    @staticmethod
    def list_elder_prospects(
        db: Session,
        user: User,
        *,
        status: str | None = None,
        stage: str | None = None,
        owner_user_id: int | None = None,
        overdue_only: bool = False,
    ) -> list[dict]:
        ProspectService._assert_elder_prospects(db, user)
        query = db.query(ElderProspect)
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(ElderProspect.tenant_id == tid)
        if status:
            query = query.filter(ElderProspect.status == status)
        if stage:
            query = query.filter(ElderProspect.stage == stage)
        if owner_user_id is not None:
            query = query.filter(ElderProspect.owner_user_id == owner_user_id)
        if overdue_only:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            query = query.filter(
                ElderProspect.status == PROSPECT_STATUS_OPEN,
                ElderProspect.next_follow_up_at.isnot(None),
                ElderProspect.next_follow_up_at < now,
            )
        rows = query.order_by(ElderProspect.updated_at.desc()).all()
        return [ProspectService._elder_dict(db, r) for r in rows]

    @staticmethod
    def get_elder_prospect(db: Session, prospect_id: int, user: User) -> ElderProspect:
        ProspectService._assert_elder_prospects(db, user)
        row = db.query(ElderProspect).filter(ElderProspect.id == prospect_id).first()
        if not row:
            raise_not_found("Elder prospect not found")
        assert_tenant_access(user, row.tenant_id)
        return row

    @staticmethod
    def create_elder_prospect(
        db: Session,
        data: ElderProspectCreate,
        user: User,
    ) -> dict:
        ProspectService._assert_elder_prospects(db, user)
        tenant_id = ProspectService._tenant_id_for_create(user, data.tenant_id)
        if data.stage not in ELDER_PROSPECT_STAGES:
            raise_bad_request(f"Invalid stage. Allowed: {', '.join(ELDER_PROSPECT_STAGES)}")
        phone, email = validate_contact(data.phone, data.email)
        row = ElderProspect(
            tenant_id=tenant_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=phone,
            email=email,
            address=data.address,
            source=data.source,
            stage=data.stage,
            status=PROSPECT_STATUS_OPEN,
            owner_user_id=data.owner_user_id or user.id,
            next_follow_up_at=data.next_follow_up_at,
            notes=data.notes,
            care_level=data.care_level,
        )
        db.add(row)
        db.flush()
        if data.notes:
            ProspectService._log_activity(
                db,
                tenant_id=tenant_id,
                elder_prospect_id=row.id,
                activity_type=ACTIVITY_NOTE,
                body=data.notes,
                actor=user,
            )
        ProspectService._log_activity(
            db,
            tenant_id=tenant_id,
            elder_prospect_id=row.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=f"Prospect created in stage {row.stage}",
            actor=user,
            metadata={"stage": row.stage},
        )
        db.commit()
        db.refresh(row)
        return ProspectService._elder_dict(db, row)

    @staticmethod
    def update_elder_prospect(
        db: Session,
        prospect_id: int,
        data: ElderProspectUpdate,
        user: User,
    ) -> dict:
        row = ProspectService.get_elder_prospect(db, prospect_id, user)
        if row.status != PROSPECT_STATUS_OPEN:
            raise_bad_request("Cannot edit a closed prospect")
        updates = data.model_dump(exclude_unset=True)
        old_owner = row.owner_user_id
        old_follow_up = row.next_follow_up_at
        old_stage = row.stage

        if "stage" in updates and updates["stage"] not in ELDER_PROSPECT_STAGES:
            raise_bad_request(f"Invalid stage. Allowed: {', '.join(ELDER_PROSPECT_STAGES)}")
        if "phone" in updates or "email" in updates:
            phone, email = validate_contact(
                updates.get("phone", None) if "phone" in updates else None,
                updates.get("email", None) if "email" in updates else None,
            )
            if "phone" in updates:
                updates["phone"] = phone
            if "email" in updates:
                updates["email"] = email

        for field, value in updates.items():
            setattr(row, field, value)

        if "stage" in updates and updates["stage"] != old_stage:
            if updates["stage"] == "LOST":
                row.status = PROSPECT_STATUS_LOST
            elif updates["stage"] == "WON":
                row.status = PROSPECT_STATUS_WON
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                elder_prospect_id=row.id,
                activity_type=ACTIVITY_STAGE_CHANGE,
                body=f"Stage changed from {old_stage} to {updates['stage']}",
                actor=user,
                metadata={"from": old_stage, "to": updates["stage"]},
            )

        if "owner_user_id" in updates and updates["owner_user_id"] != old_owner:
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                elder_prospect_id=row.id,
                activity_type=ACTIVITY_OWNER_CHANGE,
                body=f"Owner assigned to user #{updates['owner_user_id']}",
                actor=user,
                metadata={"owner_user_id": updates["owner_user_id"]},
            )

        if "next_follow_up_at" in updates and updates["next_follow_up_at"] != old_follow_up:
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                elder_prospect_id=row.id,
                activity_type=ACTIVITY_FOLLOW_UP,
                body="Follow-up date updated",
                actor=user,
                metadata={"next_follow_up_at": str(updates["next_follow_up_at"])},
            )

        db.commit()
        db.refresh(row)
        return ProspectService._elder_dict(db, row)

    @staticmethod
    def set_elder_stage(
        db: Session,
        prospect_id: int,
        stage: str,
        user: User,
        lost_reason: str | None = None,
    ) -> dict:
        return ProspectService.update_elder_prospect(
            db,
            prospect_id,
            ElderProspectUpdate(stage=stage, lost_reason=lost_reason),
            user,
        )

    @staticmethod
    def convert_elder_prospect(
        db: Session,
        prospect_id: int,
        user: User,
        *,
        link_to_elder_id: int | None = None,
    ) -> dict:
        from app.livewell.family_elder_link import (
            ensure_elder_for_prospect,
            republish_latest_assessment_for_elder,
        )

        row = ProspectService.get_elder_prospect(db, prospect_id, user)
        tenant_id = row.tenant_id
        # Snapshot before absorb deletes the prospect row.
        prospect_snapshot = ProspectService._elder_dict(db, row)
        prospect_snapshot["status"] = PROSPECT_STATUS_WON
        prospect_snapshot["stage"] = "WON"
        elder_id = ensure_elder_for_prospect(
            db,
            user,
            prospect_id,
            auto_from_assessment=False,
            link_to_elder_id=link_to_elder_id,
        )
        prospect_snapshot["converted_elder_id"] = elder_id
        republish_latest_assessment_for_elder(
            db,
            tenant_id=tenant_id,
            elder_id=elder_id,
            prospect_id=None,
        )
        db.commit()
        return {
            "prospect": prospect_snapshot,
            "elder_id": elder_id,
            "absorbed_prospect_id": prospect_id,
            "prospect_absorbed": True,
        }

    @staticmethod
    def unlink_elder_prospect(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> dict:
        from app.livewell.family_elder_link import unlink_elder_from_prospect

        row = ProspectService.get_elder_prospect(db, prospect_id, user)
        unlink_elder_from_prospect(db, user, row.id)
        db.commit()
        db.refresh(row)
        return ProspectService._elder_dict(db, row)

    @staticmethod
    def list_elder_activities(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> list[dict]:
        row = ProspectService.get_elder_prospect(db, prospect_id, user)
        activities = (
            db.query(PipelineActivity)
            .filter(PipelineActivity.elder_prospect_id == row.id)
            .order_by(PipelineActivity.created_at.desc())
            .limit(200)
            .all()
        )
        return [ProspectService._activity_dict(db, a) for a in activities]

    @staticmethod
    def add_elder_activity(
        db: Session,
        prospect_id: int,
        data: ActivityCreate,
        user: User,
    ) -> dict:
        row = ProspectService.get_elder_prospect(db, prospect_id, user)
        activity = ProspectService._log_activity(
            db,
            tenant_id=row.tenant_id,
            elder_prospect_id=row.id,
            activity_type=data.activity_type,
            body=data.body.strip(),
            actor=user,
        )
        db.commit()
        db.refresh(activity)
        return ProspectService._activity_dict(db, activity)

    # --- Caregiver prospects ---

    @staticmethod
    def _caregiver_dict(db: Session, row: CaregiverProspect) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "phone": row.phone,
            "email": row.email,
            "address": row.address,
            "source": row.source,
            "stage": row.stage,
            "status": row.status,
            "owner_user_id": row.owner_user_id,
            "owner_name": ProspectService._owner_name(db, row.owner_user_id),
            "next_follow_up_at": row.next_follow_up_at,
            "lost_reason": row.lost_reason,
            "notes": row.notes,
            "years_experience": row.years_experience,
            "converted_caregiver_id": row.converted_caregiver_id,
            "resume_score": row.resume_score,
            "resume_document_id": row.resume_document_id,
            "has_resume": bool(row.resume_parsed_json),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def list_caregiver_prospects(
        db: Session,
        user: User,
        *,
        status: str | None = None,
        stage: str | None = None,
        owner_user_id: int | None = None,
        overdue_only: bool = False,
    ) -> list[dict]:
        ProspectService._assert_caregiver_prospects(db, user)
        query = db.query(CaregiverProspect)
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(CaregiverProspect.tenant_id == tid)
        if status:
            query = query.filter(CaregiverProspect.status == status)
        if stage:
            query = query.filter(CaregiverProspect.stage == stage)
        if owner_user_id is not None:
            query = query.filter(CaregiverProspect.owner_user_id == owner_user_id)
        if overdue_only:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            query = query.filter(
                CaregiverProspect.status == PROSPECT_STATUS_OPEN,
                CaregiverProspect.next_follow_up_at.isnot(None),
                CaregiverProspect.next_follow_up_at < now,
            )
        rows = query.order_by(CaregiverProspect.updated_at.desc()).all()
        return [ProspectService._caregiver_dict(db, r) for r in rows]

    @staticmethod
    def get_caregiver_prospect(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> CaregiverProspect:
        ProspectService._assert_caregiver_prospects(db, user)
        row = (
            db.query(CaregiverProspect)
            .filter(CaregiverProspect.id == prospect_id)
            .first()
        )
        if not row:
            raise_not_found("Caregiver prospect not found")
        assert_tenant_access(user, row.tenant_id)
        return row

    @staticmethod
    def create_caregiver_prospect(
        db: Session,
        data: CaregiverProspectCreate,
        user: User,
    ) -> dict:
        ProspectService._assert_caregiver_prospects(db, user)
        tenant_id = ProspectService._tenant_id_for_create(user, data.tenant_id)
        if data.stage not in CAREGIVER_PROSPECT_STAGES:
            raise_bad_request(
                f"Invalid stage. Allowed: {', '.join(CAREGIVER_PROSPECT_STAGES)}"
            )
        row = CaregiverProspect(
            tenant_id=tenant_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            source=data.source,
            stage=data.stage,
            status=PROSPECT_STATUS_OPEN,
            owner_user_id=data.owner_user_id or user.id,
            next_follow_up_at=data.next_follow_up_at,
            notes=data.notes,
            years_experience=data.years_experience,
        )
        db.add(row)
        db.flush()
        if data.notes:
            ProspectService._log_activity(
                db,
                tenant_id=tenant_id,
                caregiver_prospect_id=row.id,
                activity_type=ACTIVITY_NOTE,
                body=data.notes,
                actor=user,
            )
        ProspectService._log_activity(
            db,
            tenant_id=tenant_id,
            caregiver_prospect_id=row.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=f"Prospect created in stage {row.stage}",
            actor=user,
            metadata={"stage": row.stage},
        )
        db.commit()
        db.refresh(row)
        return ProspectService._caregiver_dict(db, row)

    @staticmethod
    def update_caregiver_prospect(
        db: Session,
        prospect_id: int,
        data: CaregiverProspectUpdate,
        user: User,
    ) -> dict:
        row = ProspectService.get_caregiver_prospect(db, prospect_id, user)
        if row.status != PROSPECT_STATUS_OPEN:
            raise_bad_request("Cannot edit a closed prospect")
        updates = data.model_dump(exclude_unset=True)
        old_owner = row.owner_user_id
        old_follow_up = row.next_follow_up_at
        old_stage = row.stage

        if "stage" in updates and updates["stage"] not in CAREGIVER_PROSPECT_STAGES:
            raise_bad_request(
                f"Invalid stage. Allowed: {', '.join(CAREGIVER_PROSPECT_STAGES)}"
            )

        for field, value in updates.items():
            setattr(row, field, value)

        if "stage" in updates and updates["stage"] != old_stage:
            if updates["stage"] == "REJECTED":
                row.status = PROSPECT_STATUS_LOST
            elif updates["stage"] == "HIRED":
                row.status = PROSPECT_STATUS_WON
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                caregiver_prospect_id=row.id,
                activity_type=ACTIVITY_STAGE_CHANGE,
                body=f"Stage changed from {old_stage} to {updates['stage']}",
                actor=user,
                metadata={"from": old_stage, "to": updates["stage"]},
            )

        if "owner_user_id" in updates and updates["owner_user_id"] != old_owner:
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                caregiver_prospect_id=row.id,
                activity_type=ACTIVITY_OWNER_CHANGE,
                body=f"Owner assigned to user #{updates['owner_user_id']}",
                actor=user,
                metadata={"owner_user_id": updates["owner_user_id"]},
            )

        if "next_follow_up_at" in updates and updates["next_follow_up_at"] != old_follow_up:
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                caregiver_prospect_id=row.id,
                activity_type=ACTIVITY_FOLLOW_UP,
                body="Follow-up date updated",
                actor=user,
                metadata={"next_follow_up_at": str(updates["next_follow_up_at"])},
            )

        db.commit()
        db.refresh(row)
        return ProspectService._caregiver_dict(db, row)

    @staticmethod
    def convert_caregiver_prospect(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> dict:
        row = ProspectService.get_caregiver_prospect(db, prospect_id, user)
        if row.converted_caregiver_id:
            raise_bad_request("Prospect already converted")
        if row.status == PROSPECT_STATUS_LOST:
            raise_bad_request("Cannot convert a rejected prospect")

        from app.services.recruitment_placement_service import (
            RecruitmentPlacementService,
        )

        resume_attrs = RecruitmentPlacementService.resume_custom_attributes(row)
        caregiver = CaregiverService.create_caregiver(
            db,
            CaregiverCreate(
                tenant_id=row.tenant_id,
                first_name=row.first_name,
                last_name=row.last_name,
                phone=row.phone,
                email=row.email,
                years_experience=row.years_experience,
                custom_attributes=resume_attrs or None,
                status="ACTIVE",
            ),
            user,
        )
        skills_added = RecruitmentPlacementService.apply_resume_skills_to_caregiver(
            db,
            caregiver.id,
            row,
        )
        before = {"stage": row.stage, "status": row.status, "converted_caregiver_id": None}
        row.stage = "HIRED"
        row.status = PROSPECT_STATUS_WON
        row.converted_caregiver_id = caregiver.id
        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=user.id,
            entity_type="caregiver_prospect",
            entity_id=int(row.id),
            action="prospect_converted_to_caregiver",
            old_value=before,
            new_value={
                "stage": row.stage,
                "status": row.status,
                "converted_caregiver_id": int(caregiver.id),
                "skills_mapped": int(skills_added or 0),
            },
        )
        ProspectService._log_activity(
            db,
            tenant_id=row.tenant_id,
            caregiver_prospect_id=row.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=f"Converted to caregiver #{caregiver.id}",
            actor=user,
            metadata={"caregiver_id": caregiver.id},
        )
        if skills_added:
            ProspectService._log_activity(
                db,
                tenant_id=row.tenant_id,
                caregiver_prospect_id=row.id,
                activity_type=ACTIVITY_NOTE,
                body=f"Mapped {skills_added} skill(s) from resume",
                actor=user,
                metadata={"skills_added": skills_added},
            )
        db.commit()
        db.refresh(row)
        return {
            "prospect": ProspectService._caregiver_dict(db, row),
            "caregiver_id": caregiver.id,
            "skills_mapped": skills_added,
        }

    @staticmethod
    def list_caregiver_activities(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> list[dict]:
        row = ProspectService.get_caregiver_prospect(db, prospect_id, user)
        activities = (
            db.query(PipelineActivity)
            .filter(PipelineActivity.caregiver_prospect_id == row.id)
            .order_by(PipelineActivity.created_at.desc())
            .limit(200)
            .all()
        )
        return [ProspectService._activity_dict(db, a) for a in activities]

    @staticmethod
    def add_caregiver_activity(
        db: Session,
        prospect_id: int,
        data: ActivityCreate,
        user: User,
    ) -> dict:
        row = ProspectService.get_caregiver_prospect(db, prospect_id, user)
        activity = ProspectService._log_activity(
            db,
            tenant_id=row.tenant_id,
            caregiver_prospect_id=row.id,
            activity_type=data.activity_type,
            body=data.body.strip(),
            actor=user,
        )
        db.commit()
        db.refresh(activity)
        return ProspectService._activity_dict(db, activity)
