"""SafeHome-compatible elder/family portal helpers (customer_spine elders only).

Elder Care–only models (incidents, camera events, messages) are not registered
in SAFEHOME360 — methods that depended on them return empty/safe defaults.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.rbac import (
    CARE_MANAGER,
    ELDER_PORTAL,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
)
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import ElderPortalAccountCreate
from app.schemas.elder_portal import RegisterElderPortalRequest
from app.services.tenant_service import TenantService


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


class ElderPortalService:

    @staticmethod
    def list_register_tenants(db: Session) -> list[Tenant]:
        return (
            db.query(Tenant)
            .filter(Tenant.status == "ACTIVE")
            .order_by(Tenant.name)
            .all()
        )

    @staticmethod
    def find_elder_by_phone(
        db: Session,
        tenant_id: int,
        phone: str,
    ) -> Elder:
        needle = _normalize_phone(phone)
        if len(needle) < 8:
            raise_bad_request("Phone number is too short")

        elders = (
            db.query(Elder)
            .filter(Elder.tenant_id == tenant_id, Elder.phone.isnot(None))
            .all()
        )
        for elder in elders:
            if _normalize_phone(elder.phone or "") == needle:
                return elder
        raise_not_found(
            "No client profile found for this phone number at the selected agency"
        )

    @staticmethod
    def register_portal_user(
        db: Session,
        data: RegisterElderPortalRequest,
    ) -> User:
        if db.query(User).filter(User.email == data.email).first():
            raise_conflict("Email already registered")

        tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
        if not tenant:
            raise_bad_request("Agency not found")

        elder = ElderPortalService.find_elder_by_phone(
            db, data.tenant_id, data.phone
        )

        from app.core.security import hash_password

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=ELDER_PORTAL,
            tenant_id=tenant.id,
            elder_id=elder.id,
            portal_relationship=data.portal_relationship or "self",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_portal_account(
        db: Session,
        elder_id: int,
        data: ElderPortalAccountCreate,
        actor: User,
    ) -> dict:
        if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER}:
            raise_bad_request("Only admins can create elder portal accounts")

        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        if actor.role != SYSTEM_ADMIN and actor.tenant_id != elder.tenant_id:
            raise_bad_request("Cannot create account for another tenant")
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, actor, elder.id)

        if db.query(User).filter(User.email == data.email).first():
            raise_conflict("Email already registered")

        from app.core.security import hash_password

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name or elder.first_name,
            last_name=data.last_name or elder.last_name,
            role=ELDER_PORTAL,
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            portal_relationship=data.portal_relationship or "family",
        )
        db.add(user)
        db.flush()
        from app.livewell.family_elder_access import ensure_family_elder_link

        ensure_family_elder_link(db, user, elder)
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
        }

    @staticmethod
    def login_as_family(db: Session, elder_id: int, actor: User, request=None) -> dict:
        """Issue a family-portal session for this client (staff admin only)."""
        from app.livewell.family_elder_access import (
            ensure_family_elder_link,
            find_family_user_for_elder,
        )
        from app.services.auth_service import AuthService

        if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER}:
            raise_bad_request("Only staff admins can log in as a family client")

        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Client not found")
        if actor.role != SYSTEM_ADMIN and actor.tenant_id != elder.tenant_id:
            raise_bad_request("Cannot open another organization's client")
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, actor, elder.id)

        family_user = find_family_user_for_elder(db, elder.id)
        if not family_user:
            raise_not_found("No family login for this client yet")

        ensure_family_elder_link(db, family_user, elder)
        family_user.elder_id = elder.id
        db.commit()
        db.refresh(family_user)
        return AuthService._token_response(family_user, db=db, request=request)

    @staticmethod
    def get_linked_elder(db: Session, user: User) -> Elder:
        from app.livewell.family_elder_access import resolve_active_elder

        return resolve_active_elder(db, user)

    @staticmethod
    def portal_me(db: Session, user: User) -> dict:
        from app.livewell.family_elder_access import elders_payload

        elder = ElderPortalService.get_linked_elder(db, user)
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        branding = TenantService.branding_dict(tenant) if tenant else {}
        linked = elders_payload(db, user)
        return {
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "portal_relationship": user.portal_relationship,
            "elder_id": elder.id,
            "elders": linked,
            "elder_count": len(linked),
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.name if tenant else "",
            "portal_title": branding.get("portal_title", ""),
            "logo_url": branding.get("logo_url"),
            "theme": branding.get("theme", "classic"),
        }

    @staticmethod
    def care_status(db: Session, user: User) -> dict:
        from app.livewell.family_care_hub import FamilyCareHubService

        elder = ElderPortalService.get_linked_elder(db, user)
        unread = FamilyCareHubService.unread_alert_count(elder, user)
        open_incidents = sum(
            1
            for i in FamilyCareHubService.list_incidents(db, user)
            if i.get("status") == "open" and str(i.get("kind") or "sos").lower() == "sos"
        )
        return {
            "elder_id": elder.id,
            "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
            "elder_status": elder.status,
            "care_level": getattr(elder, "care_level", None),
            "mobility_status": getattr(elder, "mobility_status", None),
            "assignment_status": None,
            "caregiver_name": None,
            "match_score": None,
            "open_incidents": open_incidents,
            "unread_notifications": unread,
        }

    @staticmethod
    def list_notifications(db: Session, user: User) -> list:
        from app.livewell.family_care_hub import FamilyCareHubService

        return FamilyCareHubService.list_alerts(db, user)

    @staticmethod
    def mark_notification_read(db: Session, user: User, notification_id: int | str):
        from app.livewell.family_care_hub import FamilyCareHubService

        return FamilyCareHubService.mark_alert_read(db, user, str(notification_id))

    @staticmethod
    def list_messages(db: Session, user: User) -> list[dict]:
        from app.livewell.family_care_hub import FamilyCareHubService

        return FamilyCareHubService.list_messages(db, user)

    @staticmethod
    def activity_summary(db: Session, user: User) -> dict:
        ElderPortalService.get_linked_elder(db, user)
        return {
            "events_last_24h": 0,
            "open_incidents": 0,
            "recent_events": [],
            "recent_incidents": [],
            "events_by_type_24h": {},
        }
