"""Register SQLAlchemy models for SafeHomeOps deploy."""

from __future__ import annotations

import importlib
import os

from workforceos_core.database_packs import packs_for_deploy

_registered = False

PLATFORM_MODULES: tuple[str, ...] = (
    "app.models.tenant",
    "app.models.user",
    "app.models.document",
    "app.models.audit_log",
    "app.models.user_session",
    "app.models.recommendation_chat",
    "app.models.workflow_event",
    "app.models.workflow_task",
    "app.models.background_job",
    "app.models.subscription_plan",
    "app.models.tenant_subscription",
    "app.models.subscription_invoice",
    "app.models.skill",
    "app.models.app_global_setting",
    "app.models.auth_attempt",
    "app.models.blog",
)

# Minimal workforce — assessor staff accounts only (no caregiver dispatch pack).
WORKFORCE_MODULES: tuple[str, ...] = (
    "app.models.caregiver",
    "app.models.caregiver_prospect",
    "app.models.pipeline_activity",
)

CUSTOMER_SPINE_MODULES: tuple[str, ...] = (
    "app.models.elder",
    "app.models.elder_prospect",
    "app.models.elder_location",
    "app.models.family_elder_link",
    "app.models.care_job",
    "app.models.care_series",
    "app.models.leave_request",
    "app.models.kushlife_weekly",
    "app.models.kushlife_quality",
    "app.models.commerce",
    "app.models.tax_invoice",
    "app.models.customer_plan",
    "app.models.vendor",
    "app.models.contract",
    "app.models.privacy",
)

SAFEHOME_MODULES: tuple[str, ...] = (
    "app.models.home_safety_ai_job",
    "app.models.home_safety_vision_analysis",
    "app.models.ai_usage",
    "app.models.ai_hazard_check",
    "app.models.home_safety_assessment",
    "app.models.iot_device",
    "app.models.family_wallet",
    "app.models.incident",
    "app.models.family_contact",
    "app.models.client_care",
    "app.models.incident_report",
    "app.models.staff_alert",
    "app.models.push_device",
)

PACK_MODULES: dict[str, tuple[str, ...]] = {
    "platform": PLATFORM_MODULES,
    "workforce": WORKFORCE_MODULES,
    "customer_spine": CUSTOMER_SPINE_MODULES,
    "livewell360": SAFEHOME_MODULES,
    "safehome360": SAFEHOME_MODULES,
}

ALL_MODEL_MODULES: tuple[str, ...] = tuple(
    dict.fromkeys(module for modules in PACK_MODULES.values() for module in modules)
)

PACK_ORDER: tuple[str, ...] = (
    "platform",
    "workforce",
    "customer_spine",
    "livewell360",
    "safehome360",
)


def _import_modules(modules: tuple[str, ...]) -> None:
    for module in modules:
        importlib.import_module(module)


def modules_for_deploy(vertical: str | None) -> tuple[str, ...]:
    pack_ids = packs_for_deploy(vertical)
    ordered: list[str] = []
    seen: set[str] = set()
    for pack_id in PACK_ORDER:
        if pack_id not in pack_ids:
            continue
        for module in PACK_MODULES.get(pack_id, ()):
            if module not in seen:
                seen.add(module)
                ordered.append(module)
    return tuple(ordered)


def ensure_models_registered(vertical: str | None = None) -> None:
    global _registered
    if _registered:
        return
    if os.getenv("REGISTER_ALL_MODELS") == "1":
        _import_modules(ALL_MODEL_MODULES)
    else:
        from app.core.deploy import deploy_vertical

        resolved = vertical or deploy_vertical()
        _import_modules(modules_for_deploy(resolved))
    _registered = True


def reset_model_registration_for_tests() -> None:
    global _registered
    _registered = False
