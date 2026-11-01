"""SafeHome 360™ pricing configuration — per-tenant workflow_config storage."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request
from app.livewell.pricing_defaults import DEFAULT_PRICING
from app.livewell.stored_config import read_stored_config
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import AuditService

from app.livewell.config_keys import PRICING_KEY

VALID_MARGIN_TYPES = frozenset({"percent", "fixed"})
VALID_ROUND_OFF = frozenset({"none", "nearest_50", "nearest_100"})


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def normalize_pricing(raw: dict) -> dict:
    margin_type = str(raw.get("margin_type", "percent")).lower()
    if margin_type not in VALID_MARGIN_TYPES:
        margin_type = "percent"
    round_off = str(raw.get("round_off_rule", "nearest_100"))
    if round_off not in VALID_ROUND_OFF:
        round_off = "nearest_100"

    return {
        "default_margin_percent": int(
            _clamp(float(raw.get("default_margin_percent", 25)), 0, 100)
        ),
        "min_margin_percent": int(_clamp(float(raw.get("min_margin_percent", 15)), 0, 100)),
        "max_margin_percent": int(_clamp(float(raw.get("max_margin_percent", 50)), 0, 100)),
        "margin_type": margin_type,
        "fixed_margin_inr": max(0, int(raw.get("fixed_margin_inr") or 0)),
        "travel_rate_per_km_inr": max(0, int(raw.get("travel_rate_per_km_inr") or 0)),
        "minimum_service_charge_inr": max(0, int(raw.get("minimum_service_charge_inr") or 0)),
        "labor_rate_per_hour_inr": max(0, int(raw.get("labor_rate_per_hour_inr") or 0)),
        "default_labor_hours_per_solution": max(
            0, float(raw.get("default_labor_hours_per_solution") or 2)
        ),
        "default_consumables_inr": max(0, int(raw.get("default_consumables_inr") or 0)),
        "default_miscellaneous_inr": max(0, int(raw.get("default_miscellaneous_inr") or 0)),
        "emergency_surcharge_percent": int(
            _clamp(float(raw.get("emergency_surcharge_percent", 25)), 0, 100)
        ),
        "weekend_surcharge_percent": int(
            _clamp(float(raw.get("weekend_surcharge_percent", 15)), 0, 100)
        ),
        "gst_percent": int(_clamp(float(raw.get("gst_percent", 18)), 0, 100)),
        "round_off_rule": round_off,
        "default_travel_km": max(0, float(raw.get("default_travel_km") or 0)),
        "use_vendor_cost_for_margin": bool(raw.get("use_vendor_cost_for_margin", False)),
    }


class HomeSafetyPricingService:

    @staticmethod
    def _tenant(db: Session, user: User) -> Tenant:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_bad_request("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def get_pricing(db: Session, user: User) -> dict:
        tenant = HomeSafetyPricingService._tenant(db, user)
        stored = read_stored_config(tenant.workflow_config or {})["pricing"]
        if not stored:
            return {}
        return normalize_pricing(stored)

    @staticmethod
    def save_pricing(db: Session, user: User, payload: dict) -> dict:
        tenant = HomeSafetyPricingService._tenant(db, user)
        normalized = normalize_pricing(payload)
        cfg = dict(tenant.workflow_config or {})
        previous_raw = read_stored_config(cfg)["pricing"]
        previous = normalize_pricing(previous_raw) if previous_raw else None
        cfg[PRICING_KEY] = normalized
        tenant.workflow_config = cfg
        AuditService.log(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            entity_type="tenant_pricing",
            entity_id=int(tenant.id),
            action="pricing_saved",
            old_value=previous,
            new_value=normalized,
        )
        db.commit()
        db.refresh(tenant)
        return normalized
