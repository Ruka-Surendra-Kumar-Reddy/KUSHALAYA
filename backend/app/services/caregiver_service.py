from sqlalchemy.orm import Session

from app.core.geocoding import apply_coords_to_attributes
from fastapi import HTTPException
from sqlalchemy import func

from app.core.rbac import SYSTEM_ADMIN, TENANT_ADMIN, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.models.caregiver import Caregiver
from app.models.user import User
from app.schemas.caregiver import CaregiverCreate, CaregiverUpdate


from app.core.team_scope import scope_caregiver_query

CAREGIVER_STATUSES = frozenset({"ACTIVE", "INACTIVE"})


class CaregiverService:
    # --- shared by /caregivers and /team/caregivers ---------------------------

    @staticmethod
    def login_for(db: Session, caregiver: Caregiver) -> User | None:
        return (
            db.query(User)
            .filter(User.caregiver_id == caregiver.id, User.role == "CAREGIVER")
            .first()
        )

    @staticmethod
    def snapshot(caregiver: Caregiver, login: User | None) -> dict:
        return {
            "first_name": caregiver.first_name,
            "last_name": caregiver.last_name,
            "phone": caregiver.phone,
            "email": caregiver.email,
            "status": caregiver.status,
            "manager_user_id": caregiver.manager_user_id,
            "login_user_id": login.id if login else None,
            "login_email": login.email if login else None,
            "login_status": login.status if login else None,
        }

    @staticmethod
    def audit(db: Session, actor: User, caregiver: Caregiver, action: str, before: dict | None, after: dict) -> None:
        if before == after:
            return
        from app.services.audit_service import AuditService

        AuditService.log(
            db,
            tenant_id=caregiver.tenant_id,
            user_id=actor.id,
            entity_type="caregiver",
            entity_id=int(caregiver.id),
            action=action,
            old_value=before,
            new_value=after,
        )

    @staticmethod
    def apply_email(db: Session, caregiver: Caregiver, login: User | None, email) -> None:
        """Profile email and sign-in email move together."""
        email = str(email).strip().lower() if email else None
        if login:
            if not email:
                raise_bad_request("This caregiver signs in with their email, so it can't be blank")
            if email != (login.email or "").lower():
                clash = db.query(User).filter(func.lower(User.email) == email, User.id != login.id).first()
                if clash:
                    raise_conflict("Email already registered")
                login.email = email
        caregiver.email = email

    @staticmethod
    def apply_status(caregiver: Caregiver, login: User | None, status: str, actor: User) -> None:
        """Managers may mark someone as left; only admins bring a caregiver (and login) back."""
        status = (status or "").strip().upper()
        if status not in CAREGIVER_STATUSES:
            raise_bad_request("status must be ACTIVE or INACTIVE")
        is_admin = actor.role in (SYSTEM_ADMIN, TENANT_ADMIN)
        reactivating = status == "ACTIVE" and caregiver.status != "ACTIVE"
        if reactivating and not is_admin:
            raise HTTPException(status_code=403, detail="Only an admin can bring back a caregiver who left")
        caregiver.status = status
        if login:
            if status == "INACTIVE":
                login.status = "INACTIVE"
            elif reactivating:
                login.status = "ACTIVE"

    # Keys managed by Academy / verification — not overwritten by profile edit.
    _PRESERVED_CUSTOM_ATTR_KEYS = frozenset({"academy", "verified_documents"})

    @staticmethod
    def _tenant_id_for_create(user: User, data: CaregiverCreate) -> int:
        tid = resolve_tenant_id(user, data.tenant_id)
        if tid is None:
            raise_bad_request("tenant_id is required")
        return tid

    @staticmethod
    def list_caregivers(db: Session, user: User) -> list[Caregiver]:
        query = db.query(Caregiver)
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Caregiver.tenant_id == tid)
        query = scope_caregiver_query(db, user, query)
        return query.order_by(Caregiver.id).all()

    @staticmethod
    def get_caregiver(db: Session, caregiver_id: int, user: User) -> Caregiver:
        caregiver = (
            db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        )
        if not caregiver:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, caregiver.tenant_id)
        from app.core.team_scope import assert_caregiver_in_team

        assert_caregiver_in_team(db, user, caregiver.id)
        return caregiver

    @staticmethod
    def create_caregiver(db: Session, data: CaregiverCreate, user: User) -> Caregiver:
        tenant_id = CaregiverService._tenant_id_for_create(user, data)
        custom_attributes = CaregiverService._geocode_custom_attributes(
            None,
            data.custom_attributes,
        )
        caregiver = Caregiver(
            tenant_id=tenant_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            email=str(data.email).strip().lower() if data.email else None,
            aadhaar_number=data.aadhaar_number,
            years_experience=data.years_experience,
            background_check_status=data.background_check_status,
            police_verification_status=data.police_verification_status,
            custom_attributes=custom_attributes,
            status=data.status,
            # A care manager's new caregiver joins their own team (else it would vanish from their list).
            manager_user_id=user.id if user.role == "CARE_MANAGER" else None,
        )
        db.add(caregiver)
        db.flush()
        CaregiverService.audit(db, user, caregiver, "caregiver_created", None, CaregiverService.snapshot(caregiver, None))
        db.commit()
        db.refresh(caregiver)
        return caregiver

    @staticmethod
    def _merge_custom_attributes(
        existing: dict | None,
        incoming: dict | None,
    ) -> dict | None:
        if incoming is None:
            return existing
        merged = dict(existing or {})
        for key, value in incoming.items():
            merged[key] = value
        for key in CaregiverService._PRESERVED_CUSTOM_ATTR_KEYS:
            if key in (existing or {}) and key not in incoming:
                merged[key] = existing[key]
        return merged or None

    @staticmethod
    def _geocode_custom_attributes(
        existing: dict | None,
        incoming: dict | None,
    ) -> dict | None:
        merged = CaregiverService._merge_custom_attributes(existing, incoming)
        if merged is None:
            return None

        previous_address = (existing or {}).get("address")
        if isinstance(previous_address, str):
            previous_address = previous_address.strip()
        else:
            previous_address = None

        address = merged.get("address")
        if isinstance(address, str):
            address = address.strip()
        else:
            address = None

        return apply_coords_to_attributes(
            merged,
            address,
            previous_address=previous_address,
        )

    @staticmethod
    def update_caregiver(
        db: Session,
        caregiver_id: int,
        data: CaregiverUpdate,
        user: User,
    ) -> Caregiver:
        caregiver = CaregiverService.get_caregiver(db, caregiver_id, user)
        login = CaregiverService.login_for(db, caregiver)
        before = CaregiverService.snapshot(caregiver, login)
        updates = data.model_dump(exclude_unset=True)
        if "email" in updates:
            CaregiverService.apply_email(db, caregiver, login, updates.pop("email"))
        if "status" in updates:
            status = updates.pop("status")
            if status is not None:
                CaregiverService.apply_status(caregiver, login, status, user)
        if "custom_attributes" in updates:
            updates["custom_attributes"] = CaregiverService._geocode_custom_attributes(
                caregiver.custom_attributes,
                updates["custom_attributes"],
            )
        for field, value in updates.items():
            setattr(caregiver, field, value)
        if login:
            login.first_name, login.last_name = caregiver.first_name, caregiver.last_name
        CaregiverService.audit(
            db, user, caregiver, "caregiver_updated", before, CaregiverService.snapshot(caregiver, login)
        )
        db.commit()
        db.refresh(caregiver)
        return caregiver

    @staticmethod
    def delete_caregiver(db: Session, caregiver_id: int, user: User) -> None:
        caregiver = CaregiverService.get_caregiver(db, caregiver_id, user)
        login = CaregiverService.login_for(db, caregiver)
        before = CaregiverService.snapshot(caregiver, login)
        CaregiverService.apply_status(caregiver, login, "INACTIVE", user)
        CaregiverService.audit(
            db, user, caregiver, "caregiver_left", before, CaregiverService.snapshot(caregiver, login)
        )
        db.commit()
