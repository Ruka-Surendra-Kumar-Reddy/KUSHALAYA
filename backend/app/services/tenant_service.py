from sqlalchemy.orm import Session

from app.core.custom_fields import (
    RESERVED_CAREGIVER_KEYS,
    RESERVED_ELDER_KEYS,
    validate_field_schema,
)
from app.core.rbac import CARE_MANAGER, SYSTEM_ADMIN, TENANT_ADMIN, assert_tenant_access
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.core.themes import THEME_CATALOG, VALID_THEMES
from app.core.markets import (
    DEFAULT_MARKET,
    VALID_MARKETS,
    list_markets,
    market_label,
    market_meta,
    normalize_market,
    tenant_market,
)
from app.core.slug import ensure_tenant_register_slug
from app.core.deploy import deploy_vertical
from app.core.verticals import (
    DEFAULT_VERTICAL,
    VALID_VERTICALS,
    normalize_vertical,
)
from app.livewell.brand import brand_name
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.custom_fields import TenantFieldSchemasUpdate
from app.core.security import hash_password
from app.schemas.tenant import TenantBrandingUpdate, TenantCreate, TenantUpdate
from app.services.subscription_service import SubscriptionService

_PRODUCT_PORTAL_ALIASES = {
    "livewell360",
    "livewell 360",
    "livewell360™",
    "livewell 360™",
    "safehome360",
    "safehome 360",
    "safehome 360™",
    "safehome360™",
    "workforceos",
}


def _resolve_portal_title(tenant: Tenant) -> str:
    raw = (tenant.portal_title or tenant.name or "").strip()
    if not raw:
        return brand_name()
    key = raw.lower().replace("®", "").replace("©", "").replace("\u2122", "™")
    key = " ".join(key.split())
    if key in _PRODUCT_PORTAL_ALIASES:
        return brand_name()
    return raw


class TenantService:

    @staticmethod
    def branding_dict(tenant: Tenant) -> dict:
        # Single-vertical deploy: nav/UI follow DEPLOY_VERTICAL, not legacy tenant rows.
        vertical = deploy_vertical()
        market = tenant_market(tenant)
        meta = market_meta(market)
        return {
            "id": tenant.id,
            "name": tenant.name,
            "portal_title": _resolve_portal_title(tenant),
            "logo_url": tenant.logo_url,
            "theme": tenant.theme or "classic",
            "platform_name": "WorkforceOS",
            "vertical": vertical,
            "vertical_label": brand_name(),
            "market": market,
            "market_label": market_label(market),
            "currency": meta["currency"],
            "bench_cost_per_caregiver_month_inr": float(
                tenant.bench_cost_per_caregiver_month_inr or 15_000.0
            ),
            "elder_field_schema": tenant.elder_field_schema or [],
            "caregiver_field_schema": tenant.caregiver_field_schema or [],
        }

    @staticmethod
    def field_schemas_dict(tenant: Tenant) -> dict:
        elder_fields = tenant.elder_field_schema or []
        caregiver_fields = tenant.caregiver_field_schema or []
        return {
            "elder_fields": elder_fields,
            "caregiver_fields": caregiver_fields,
            "demand_fields": elder_fields,
            "supply_fields": caregiver_fields,
        }

    @staticmethod
    def update_field_schemas(
        db: Session,
        tenant: Tenant,
        data: TenantFieldSchemasUpdate,
    ) -> Tenant:
        elder_fields = data.elder_fields if data.elder_fields is not None else data.demand_fields
        caregiver_fields = (
            data.caregiver_fields
            if data.caregiver_fields is not None
            else data.supply_fields
        )
        if elder_fields is not None:
            tenant.elder_field_schema = validate_field_schema(
                [f.model_dump() for f in elder_fields],
                RESERVED_ELDER_KEYS,
            )
        if caregiver_fields is not None:
            tenant.caregiver_field_schema = validate_field_schema(
                [f.model_dump() for f in caregiver_fields],
                RESERVED_CAREGIVER_KEYS,
            )
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def list_tenants(db: Session, user: User) -> list[Tenant]:
        query = db.query(Tenant)
        if user.role != SYSTEM_ADMIN:
            if user.tenant_id is None:
                return []
            query = query.filter(Tenant.id == user.tenant_id)
        return query.all()

    @staticmethod
    def get_tenant(db: Session, tenant_id: int, user: User) -> Tenant:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def get_branding_for_user(db: Session, user: User) -> dict:
        if user.tenant_id is None:
            vertical = deploy_vertical()
            brand = brand_name()
            return {
                "id": None,
                "name": "WorkforceOS",
                "portal_title": brand,
                "logo_url": None,
                "theme": "classic",
                "platform_name": "WorkforceOS",
                "vertical": vertical,
                "vertical_label": brand,
                "bench_cost_per_caregiver_month_inr": 15_000.0,
                "elder_field_schema": [],
                "caregiver_field_schema": [],
            }
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")
        return TenantService.branding_dict(tenant)

    @staticmethod
    def get_field_schemas_for_user(db: Session, user: User) -> dict:
        if user.tenant_id is None:
            return {"elder_fields": [], "caregiver_fields": []}
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")
        return TenantService.field_schemas_dict(tenant)

    @staticmethod
    def update_branding(
        db: Session,
        tenant_id: int,
        data: TenantBrandingUpdate,
        user: User,
    ) -> Tenant:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")
        assert_tenant_access(user, tenant.id)

        if user.role == CARE_MANAGER:
            if any(
                getattr(data, field) is not None
                for field in ("theme", "logo_url", "portal_title")
            ):
                raise_bad_request(
                    "Care managers can only update bench cost per caregiver"
                )
            if data.bench_cost_per_caregiver_month_inr is None:
                raise_bad_request("bench_cost_per_caregiver_month_inr is required")
            tenant.bench_cost_per_caregiver_month_inr = (
                data.bench_cost_per_caregiver_month_inr
            )
            db.commit()
            db.refresh(tenant)
            return tenant

        if user.role not in {SYSTEM_ADMIN, TENANT_ADMIN}:
            raise_bad_request("Only admins can update branding")

        if data.theme is not None:
            theme = data.theme.lower()
            if theme not in VALID_THEMES:
                raise_bad_request(
                    f"theme must be one of: {', '.join(sorted(VALID_THEMES))}"
                )
            tenant.theme = theme

        if data.logo_url is not None:
            tenant.logo_url = data.logo_url or None

        if data.portal_title is not None:
            tenant.portal_title = data.portal_title or None

        if data.bench_cost_per_caregiver_month_inr is not None:
            tenant.bench_cost_per_caregiver_month_inr = (
                data.bench_cost_per_caregiver_month_inr
            )

        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def create_tenant(db: Session, tenant: TenantCreate, user: User) -> Tenant:
        if user.role != SYSTEM_ADMIN:
            raise_bad_request("Only system admins can create tenants")

        if db.query(Tenant).filter(Tenant.name == tenant.name).first():
            raise_conflict("Tenant already exists")

        theme = (tenant.theme or "classic").lower()
        if theme not in VALID_THEMES:
            raise_bad_request(
                f"theme must be one of: {', '.join(sorted(VALID_THEMES))}"
            )

        vertical = deploy_vertical()
        if vertical not in VALID_VERTICALS:
            raise_bad_request(
                f"vertical must be one of: {', '.join(sorted(VALID_VERTICALS))}"
            )

        market = normalize_market(tenant.market, country=tenant.country)
        if market not in VALID_MARKETS:
            raise_bad_request(f"market must be one of: {', '.join(sorted(VALID_MARKETS))}")
        country = tenant.country or (
            "United States" if market == "US" else "India"
        )

        db_tenant = Tenant(
            name=tenant.name,
            email=tenant.email,
            phone=tenant.phone,
            address=tenant.address,
            city=tenant.city,
            state=tenant.state,
            country=country,
            market=market,
            theme=theme,
            vertical=vertical,
        )
        db.add(db_tenant)
        db.flush()
        ensure_tenant_register_slug(db, db_tenant)

        if tenant.admin_email and tenant.admin_password:
            if not tenant.admin_first_name or not tenant.admin_last_name:
                raise_bad_request(
                    "admin_first_name and admin_last_name required with admin_email"
                )
            if db.query(User).filter(User.email == tenant.admin_email).first():
                raise_conflict("Admin email already registered")
            db.add(
                User(
                    email=tenant.admin_email,
                    password_hash=hash_password(tenant.admin_password),
                    first_name=tenant.admin_first_name,
                    last_name=tenant.admin_last_name,
                    role=TENANT_ADMIN,
                    tenant_id=db_tenant.id,
                )
            )

        db.commit()
        db.refresh(db_tenant)
        SubscriptionService.start_trial(db, db_tenant.id)
        return db_tenant

    @staticmethod
    def update_tenant(
        db: Session,
        tenant_id: int,
        data: TenantUpdate,
        user: User,
    ) -> Tenant:
        if user.role != SYSTEM_ADMIN:
            raise_bad_request("Only super admins can update tenants")
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")

        payload = data.model_dump(exclude_unset=True)
        if "status" in payload and payload["status"] not in {
            "ACTIVE",
            "INACTIVE",
        }:
            raise_bad_request("status must be ACTIVE or INACTIVE")
        if "theme" in payload and payload["theme"]:
            theme = payload["theme"].lower()
            if theme not in VALID_THEMES:
                raise_bad_request(
                    f"theme must be one of: {', '.join(sorted(VALID_THEMES))}"
                )
            payload["theme"] = theme
        if "vertical" in payload and payload["vertical"]:
            # SafeHomeOps is a single-vertical deploy — ignore client override.
            payload["vertical"] = deploy_vertical()
        if "market" in payload and payload["market"]:
            market = payload["market"].upper()
            if market not in VALID_MARKETS:
                raise_bad_request(
                    f"market must be one of: {', '.join(sorted(VALID_MARKETS))}"
                )
            payload["market"] = market
        if "logo_url" in payload:
            payload["logo_url"] = payload["logo_url"] or None

        for field, value in payload.items():
            setattr(tenant, field, value)

        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def list_themes() -> list[dict]:
        return THEME_CATALOG

    @staticmethod
    def list_markets() -> list[dict]:
        return list_markets()

    @staticmethod
    def list_verticals() -> list[dict]:
        from app.core.verticals import VERTICAL_LABELS

        descriptions = {
            "ELDER_CARE": "Home care for elders — family portal, monitoring, matching",
            "SECURITY": "Security guard deployment and site operations",
            "HOUSEKEEPING": "Cleaning crews and inspection checklists",
            "DRIVER_SERVICES": "Driver assignments, trips, and fleet ops",
            "HOME_HEALTHCARE": "Clinical home health staffing and compliance",
        }
        return [
            {
                "id": vid,
                "label": VERTICAL_LABELS[vid],
                "description": descriptions.get(vid, ""),
            }
            for vid in sorted(VALID_VERTICALS)
        ]
