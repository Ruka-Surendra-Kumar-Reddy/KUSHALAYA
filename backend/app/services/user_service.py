from sqlalchemy.orm import Session

from app.core.rbac import (
    CARE_MANAGER,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    VIEWER,
    assert_tenant_access,
    resolve_tenant_id,
)
from fastapi import HTTPException
from sqlalchemy import func

from app.core.rbac import CAREGIVER
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.core.security import hash_password
from app.core.team_scope import team_caregiver_ids, team_elder_ids
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.livewell.family_contacts import clean_phone
from app.models.user import User
from app.services.audit_service import AuditService

# Staff roles a tenant admin may hand out inside their own tenant. Portal roles
# (family / assessor) are bound to an elder or caregiver record and are created
# through their own flows; SYSTEM_ADMIN is never assignable through the API.
TENANT_ASSIGNABLE_ROLES = frozenset({TENANT_ADMIN, CARE_MANAGER, VIEWER})

USER_STATUS_ACTIVE = "ACTIVE"
USER_STATUS_INACTIVE = "INACTIVE"
ADMIN_ROLE_SET = frozenset({SYSTEM_ADMIN, TENANT_ADMIN})


def _forbid(detail: str) -> None:
    raise HTTPException(status_code=403, detail=detail)


def _user_audit_snapshot(user: User) -> dict:
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "status": user.status,
        "tenant_id": user.tenant_id,
    }


class UserService:

    @staticmethod
    def list_users(db: Session, actor: User) -> list[User]:
        query = db.query(User)
        tid = resolve_tenant_id(actor)
        if tid is not None:
            query = query.filter(User.tenant_id == tid)
        return query.order_by(User.id).all()

    @staticmethod
    def _managed_user(db: Session, actor: User, user_id: int) -> User:
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            raise_not_found("User not found")
        if target.tenant_id is None:
            # Platform accounts are not tenant-managed.
            raise_bad_request("This account cannot be managed here")
        assert_tenant_access(actor, target.tenant_id)
        if target.role == SYSTEM_ADMIN:
            raise_bad_request("System admin accounts cannot be managed here")
        return target

    @staticmethod
    def update_role(
        db: Session, actor: User, user_id: int, role: str, reassign_to: int | None = None, commit: bool = True
    ) -> User:
        new_role = (role or "").strip().upper()
        if new_role not in TENANT_ASSIGNABLE_ROLES:
            raise_bad_request(
                "role must be one of: " + ", ".join(sorted(TENANT_ASSIGNABLE_ROLES))
            )
        if actor.id == user_id:
            raise_bad_request("You cannot change your own role")
        target = UserService._managed_user(db, actor, user_id)
        if target.role not in TENANT_ASSIGNABLE_ROLES:
            raise_bad_request("Only staff accounts can have their role changed")
        if target.role == new_role:
            return target
        if target.role == TENANT_ADMIN:
            UserService._assert_not_last_admin(db, target)
        if target.role == CARE_MANAGER:
            UserService._hand_over_team(db, actor, target, reassign_to)
        before = _user_audit_snapshot(target)
        target.role = new_role
        AuditService.log(
            db,
            tenant_id=target.tenant_id,
            user_id=actor.id,
            entity_type="user",
            entity_id=int(target.id),
            action="user_role_changed",
            old_value=before,
            new_value=_user_audit_snapshot(target),
        )
        if commit:
            db.commit()
            db.refresh(target)
        return target

    @staticmethod
    def set_active(
        db: Session, actor: User, user_id: int, active: bool, reassign_to: int | None = None
    ) -> User:
        if actor.id == user_id:
            raise_bad_request("You cannot deactivate your own account")
        target = UserService._managed_user(db, actor, user_id)
        new_status = USER_STATUS_ACTIVE if active else USER_STATUS_INACTIVE
        if target.status == new_status:
            return target
        if not active:
            if target.role == TENANT_ADMIN:
                UserService._assert_not_last_admin(db, target)
            if target.role == CARE_MANAGER:
                # Caregivers and clients move to another manager in the same transaction.
                UserService._hand_over_team(db, actor, target, reassign_to)
        before = _user_audit_snapshot(target)
        target.status = new_status
        AuditService.log(
            db,
            tenant_id=target.tenant_id,
            user_id=actor.id,
            entity_type="user",
            entity_id=int(target.id),
            action="user_reactivated" if active else "user_deactivated",
            old_value=before,
            new_value=_user_audit_snapshot(target),
        )
        db.commit()
        db.refresh(target)
        return target

    # --- Phase 1C: guards, profile edit, password, caseload ------------------

    @staticmethod
    def _assert_not_last_admin(db: Session, target: User) -> None:
        # Lock the agency's admin rows so two concurrent demotions can't both pass.
        admins = (
            db.query(User)
            .filter(
                User.tenant_id == target.tenant_id,
                User.role == TENANT_ADMIN,
                User.status == USER_STATUS_ACTIVE,
            )
            .with_for_update()
            .all()
        )
        others = [u for u in admins if u.id != target.id]
        if not others:
            raise_bad_request("This is the agency's last admin. Make someone else an admin first.")

    @staticmethod
    def caseload(db: Session, manager: User) -> dict:
        return {
            "clients": len(team_elder_ids(db, manager) or set()),
            # Same rule as /team/managers: caregivers who left don't count.
            "caregivers": db.query(Caregiver)
            .filter(Caregiver.manager_user_id == manager.id, Caregiver.status != "INACTIVE")
            .count(),
        }

    @staticmethod
    def _hand_over_team(db: Session, actor: User, manager: User, reassign_to: int | None) -> None:
        """Move a leaving manager's caregivers and clients to another active manager.

        No commit here: the caller commits together with the status/role change."""
        load = UserService.caseload(db, manager)
        if not load["clients"] and not load["caregivers"]:
            return
        if reassign_to is None:
            raise_bad_request(
                f"Reassign their {load['clients']} clients and {load['caregivers']} caregivers "
                "to another manager first"
            )
        if reassign_to == manager.id:
            raise_bad_request("Choose a different manager to take over the team")
        new_mgr = (
            db.query(User)
            .filter(
                User.id == reassign_to,
                User.role == CARE_MANAGER,
                User.status == USER_STATUS_ACTIVE,
                User.tenant_id == manager.tenant_id,
            )
            .first()
        )
        if not new_mgr:
            raise_bad_request("Choose an active manager in this agency")
        db.query(Caregiver).filter(Caregiver.manager_user_id == manager.id).update(
            {Caregiver.manager_user_id: new_mgr.id}, synchronize_session=False
        )
        db.query(Elder).filter(Elder.manager_user_id == manager.id).update(
            {Elder.manager_user_id: new_mgr.id}, synchronize_session=False
        )
        AuditService.log(
            db,
            tenant_id=manager.tenant_id,
            user_id=actor.id,
            entity_type="user",
            entity_id=int(manager.id),
            action="manager_team_reassigned",
            old_value={"manager_user_id": manager.id, **load},
            new_value={"manager_user_id": new_mgr.id},
        )

    @staticmethod
    def _editable_user(db: Session, actor: User, user_id: int) -> User:
        """Admins manage anyone in their agency; managers only their own caregivers' logins."""
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            raise_not_found("User not found")
        if actor.role in ADMIN_ROLE_SET:
            if actor.id == target.id:
                return target
            return UserService._managed_user(db, actor, user_id)
        if actor.role != CARE_MANAGER:
            _forbid("Not allowed")
        if target.tenant_id != actor.tenant_id:
            raise_not_found("User not found")
        if target.role in ADMIN_ROLE_SET:
            _forbid("Managers cannot change an admin's account")
        if target.id == actor.id:
            return target
        if target.role == CAREGIVER and target.caregiver_id in (team_caregiver_ids(db, actor) or set()):
            return target
        _forbid("You can only manage caregivers in your team")
        return target  # pragma: no cover

    @staticmethod
    def update_profile(db: Session, actor: User, user_id: int, data: dict) -> User:
        target = UserService._editable_user(db, actor, user_id)
        before = _user_audit_snapshot(target)
        if data.get("role") is not None and data["role"].strip().upper() != target.role:
            if actor.role not in ADMIN_ROLE_SET:
                _forbid("Only admins can change roles")
            UserService.update_role(
                db, actor, user_id, data["role"], data.get("reassign_to_manager_id"), commit=False
            )
        for field in ("first_name", "last_name"):
            if data.get(field) is not None:
                value = data[field].strip()
                if field == "first_name" and not value:
                    raise_bad_request("First name is required")
                setattr(target, field, value)
        if data.get("email") is not None:
            email = str(data["email"]).strip().lower()
            if email != (target.email or "").lower():
                clash = (
                    db.query(User)
                    .filter(func.lower(User.email) == email, User.id != target.id)
                    .first()
                )
                if clash:
                    raise_conflict("Email already registered")
                target.email = email
        if "phone" in data:
            target.phone = clean_phone(data["phone"]) or None
        if target.role == CAREGIVER and target.caregiver_id:
            cg = db.query(Caregiver).filter(Caregiver.id == target.caregiver_id).first()
            if cg:
                cg.first_name, cg.last_name = target.first_name, target.last_name
                if data.get("email") is not None:
                    cg.email = target.email
        after = _user_audit_snapshot(target)
        if after != before:
            AuditService.log(
                db,
                tenant_id=target.tenant_id,
                user_id=actor.id,
                entity_type="user",
                entity_id=int(target.id),
                action="user_updated",
                old_value=before,
                new_value=after,
            )
        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def set_password(db: Session, actor: User, user_id: int, password: str) -> User:
        if actor.id == user_id:
            raise_bad_request("Change your own password from the account menu")
        target = UserService._editable_user(db, actor, user_id)
        target.password_hash = hash_password(password)
        AuditService.log(
            db,
            tenant_id=target.tenant_id,
            user_id=actor.id,
            entity_type="user",
            entity_id=int(target.id),
            action="user_password_reset",
            old_value=None,
            new_value={"email": target.email},
        )
        db.commit()
        db.refresh(target)
        return target
