#!/usr/bin/env python3
"""Bootstrap HousekeepingOps deploy repo from ElderCareOps.

Creates a sibling directory with platform + workforce + housekeeping vertical only.
Run from ElderCareOps root:

    python scripts/bootstrap_housekeepingops.py
    python scripts/bootstrap_housekeepingops.py --target C:/pers/HousekeepingOps
"""

from __future__ import annotations

import argparse
import re
import shutil
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT.parent / "HousekeepingOps"

SKIP_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".next",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "workforceos-core",
    "uploads",
    "test_uploads",
    "eldercareops.db",
    "housekeepingops.db",
    "WorkforceOS.db",
}

ELDER_ONLY_BACKEND_MODELS = {
    "elder_message.py",
    "elder_notification.py",
    "care_plan.py",
    "visit_care_note.py",
    "visit_checklist_log.py",
    "incident.py",
    "monitoring_alert.py",
    "monitoring_consent.py",
    "camera_event.py",
    "family_service_request.py",
}

ELDER_ONLY_BACKEND_SERVICES = {
    "monitoring_service.py",
    "monitoring_notifications.py",
    "monitoring_rules.py",
}

ELDER_ONLY_API = {
    "elders.py",
    "elder_portal.py",
    "family_portal.py",
    "care_plans.py",
    "visit_execution.py",
    "monitoring.py",
    "communications.py",
    "billing.py",
}

ELDER_ONLY_PACKAGES = {
    "care_plans",
    "family_portal",
    "visit_execution",
    "visit_notifications",
}

ELDER_ONLY_FRONTEND_APP = [
    "app/(app)/elders",
    "app/(app)/care-plans",
    "app/(app)/monitoring",
    "app/elder",
    "app/(app)/billing",
    "app/(app)/matching",
    "app/(app)/prospects",
]

ELDER_ONLY_FRONTEND_LIBS = [
    "lib/carePlans.ts",
    "lib/familyPortal.ts",
    "lib/elderPortal.ts",
    "lib/matching.ts",
    "lib/monitoring.ts",
]

ELDER_ONLY_TESTS = [
    "test_care_plans.py",
    "test_visit_execution.py",
    "test_monitoring.py",
    "test_family_portal_adapters.py",
    "test_elder_portal.py",
    "test_cleaning_vertical.py",
    "test_cleaning_recurrence.py",
    "test_cleaning_crm.py",
    "test_cleaning_quotes.py",
    "test_cleaning_billing.py",
    "test_caregiver_cleaning_jobs.py",
    "test_homeowner_jobs.py",
    "test_homeowner_registration.py",
    "test_contractor_pay.py",
    "test_deploy_database.py",
]


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if item.is_dir():
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, out)


def _remove_path(root: Path, rel: str) -> None:
    path = root / rel
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _patch_file(path: Path, replacements: list[tuple[str, str]]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def bootstrap(target: Path) -> None:
    if target.exists():
        raise SystemExit(f"Target already exists: {target}. Remove it or pick another --target.")

    print(f"Creating HousekeepingOps at {target}")
    target.mkdir(parents=True)

    for folder in ("backend", "frontend", "scripts", "docs", ".github"):
        _copy_tree(REPO_ROOT / folder, target / folder)

    for rel in ("backend/requirements.txt", "backend/pytest.ini", "backend/.env.example"):
        src = REPO_ROOT / rel
        if src.exists():
            shutil.copy2(src, target / rel)

    if (REPO_ROOT / "docker-compose.yml").exists():
        shutil.copy2(REPO_ROOT / "docker-compose.yml", target / "docker-compose.yml")

    backend = target / "backend" / "app"
    models = backend / "models"
    for name in ELDER_ONLY_BACKEND_MODELS:
        _remove_path(models, name)

    services = backend / "services"
    for name in ELDER_ONLY_BACKEND_SERVICES:
        _remove_path(services, name)

    api = backend / "api" / "v1"
    for name in ELDER_ONLY_API:
        _remove_path(api, name)

    for pkg in ELDER_ONLY_PACKAGES:
        _remove_path(backend, pkg)

    _remove_path(backend, "seed_db.py")
    _remove_path(backend, "seed_academy.py")

    tests = target / "backend" / "tests"
    for name in ELDER_ONLY_TESTS:
        _remove_path(tests, name)

    frontend = target / "frontend"
    for rel in ELDER_ONLY_FRONTEND_APP:
        _remove_path(frontend, rel)
    for rel in ELDER_ONLY_FRONTEND_LIBS:
        _remove_path(frontend, rel)

    _remove_path(frontend, "scripts/capture-cleaning-screenshots.mjs")

    # Housekeeping model packs (customer spine + housekeeping domain).
    _write(
        backend / "models" / "packs.py",
        '''
        """Register SQLAlchemy models for HousekeepingOps deploy."""

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
            "app.models.workflow_event",
            "app.models.workflow_task",
            "app.models.subscription_plan",
            "app.models.tenant_subscription",
            "app.models.subscription_invoice",
            "app.models.skill",
        )

        WORKFORCE_MODULES: tuple[str, ...] = (
            "app.models.caregiver",
            "app.models.caregiver_prospect",
            "app.models.caregiver_skill",
            "app.models.caregiver_rating",
            "app.models.caregiver_certification",
            "app.models.caregiver_pay_rate",
            "app.models.caregiver_identity",
            "app.models.caregiver_device",
            "app.models.caregiver_location_event",
            "app.models.assignment",
            "app.models.visit",
            "app.models.attendance_record",
            "app.models.attendance_alert",
            "app.models.leave_request",
            "app.models.shift_swap_request",
            "app.models.payroll_run",
            "app.models.payroll_deduction",
            "app.models.contractor_pay",
            "app.models.match",
            "app.models.match_result",
            "app.models.match_run",
            "app.models.recommendation_feedback",
            "app.models.placement_history",
            "app.models.prediction_result",
            "app.models.pipeline_activity",
            "app.models.qualification_pack",
            "app.models.training_program",
            "app.models.us_workforce_compliance",
        )

        CUSTOMER_SPINE_MODULES: tuple[str, ...] = ("app.models.elder",)

        HOUSEKEEPING_MODULES: tuple[str, ...] = (
            "app.models.cleaning_crm_activity",
            "app.models.cleaning_customer_profile",
            "app.models.cleaning_lead",
            "app.models.cleaning_job",
            "app.models.cleaning_job_cleaner",
            "app.models.cleaning_property",
            "app.models.cleaning_quote",
            "app.models.cleaning_service_item",
            "app.models.cleaning_caregiver_pay_rate",
            "app.models.cleaning_property_rate",
            "app.models.cleaning_recurrence_rule",
        )

        PACK_MODULES: dict[str, tuple[str, ...]] = {
            "platform": PLATFORM_MODULES,
            "workforce": WORKFORCE_MODULES,
            "customer_spine": CUSTOMER_SPINE_MODULES,
            "housekeeping": HOUSEKEEPING_MODULES,
        }

        ALL_MODEL_MODULES: tuple[str, ...] = tuple(
            dict.fromkeys(
                module for modules in PACK_MODULES.values() for module in modules
            )
        )


        def _import_modules(modules: tuple[str, ...]) -> None:
            for module in modules:
                importlib.import_module(module)


        def modules_for_deploy(vertical: str | None) -> tuple[str, ...]:
            pack_ids = packs_for_deploy(vertical)
            ordered: list[str] = []
            seen: set[str] = set()
            for pack_id in ("platform", "workforce", "customer_spine", "housekeeping"):
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
        ''',
    )

    _write(
        backend / "customer_portal" / "adapters.py",
        '''
        """Housekeeping vertical adapter for customer portal billing."""

        from __future__ import annotations

        from app.core.verticals import HOUSEKEEPING, has_feature, normalize_vertical
        from app.models.tenant import Tenant
        from workforceos_core.adapters.customer_portal import (
            CustomerPortalVerticalAdapter,
            DefaultCustomerPortalAdapter,
            get_customer_portal_adapter,
            register_customer_portal_adapter,
        )

        __all__ = [
            "CustomerPortalVerticalAdapter",
            "DefaultCustomerPortalAdapter",
            "HousekeepingPortalAdapter",
            "get_customer_portal_adapter",
            "register_customer_portal_adapter",
        ]


        class HousekeepingPortalAdapter(CustomerPortalVerticalAdapter):
            vertical = HOUSEKEEPING

            def billing_enabled(self, tenant: Tenant) -> bool:
                if normalize_vertical(tenant.vertical) != HOUSEKEEPING:
                    return False
                return has_feature(tenant.vertical, "cleaning_billing") or has_feature(
                    tenant.vertical, "customer_portal_billing"
                )

            def portal_label(self) -> str:
                return "homeowner"


        register_customer_portal_adapter(HOUSEKEEPING, HousekeepingPortalAdapter())
        ''',
    )

    _write(
        backend / "core" / "cleaning_crm_constants.py",
        '''
        """Re-export housekeeping CRM constants from workforceos-core."""

        from workforceos_core.housekeeping.crm_constants import (
            CLEANING_LEAD_SOURCES,
            CLEANING_LEAD_STAGES,
            CRM_ACTIVITY_CALL,
            CRM_ACTIVITY_EMAIL,
            CRM_ACTIVITY_FOLLOW_UP,
            CRM_ACTIVITY_MESSAGE,
            CRM_ACTIVITY_NOTE,
            CRM_ACTIVITY_STAGE_CHANGE,
            CRM_STATUS_LOST,
            CRM_STATUS_OPEN,
            CRM_STATUS_WON,
            CUSTOMER_SEGMENTS,
        )

        __all__ = [
            "CLEANING_LEAD_SOURCES",
            "CLEANING_LEAD_STAGES",
            "CRM_ACTIVITY_CALL",
            "CRM_ACTIVITY_EMAIL",
            "CRM_ACTIVITY_FOLLOW_UP",
            "CRM_ACTIVITY_MESSAGE",
            "CRM_ACTIVITY_NOTE",
            "CRM_ACTIVITY_STAGE_CHANGE",
            "CRM_STATUS_LOST",
            "CRM_STATUS_OPEN",
            "CRM_STATUS_WON",
            "CUSTOMER_SEGMENTS",
        ]
        ''',
    )

    _write(
        backend / "core" / "cleaning_pricebook_constants.py",
        '''
        """Re-export housekeeping price book constants from workforceos-core."""

        from workforceos_core.housekeeping.pricebook_constants import (
            LINE_TYPES,
            PRICING_MODELS,
            QUOTE_STATUSES,
            SERVICE_CATEGORIES,
        )

        __all__ = [
            "LINE_TYPES",
            "PRICING_MODELS",
            "QUOTE_STATUSES",
            "SERVICE_CATEGORIES",
        ]
        ''',
    )

    _write(
        api / "router.py",
        '''
        from fastapi import APIRouter

        from app.api.v1 import (
            academy,
            assignments,
            auth,
            cleaning,
            cleaning_crm,
            cleaning_pricebook,
            caregiver_portal,
            caregiver_verification,
            caregivers,
            copilot,
            customer_portal,
            documents,
            executive,
            geocode,
            geofence,
            payroll,
            platform,
            prospects,
            recruitment,
            scheduling,
            subscriptions,
            skills,
            tenants,
            users,
            workforce,
            webhooks,
            workflows,
        )

        api_router = APIRouter(prefix="/api/v1")

        api_router.include_router(auth.router)
        api_router.include_router(tenants.router)
        api_router.include_router(users.router)
        api_router.include_router(caregivers.router, prefix="/caregivers")
        api_router.include_router(
            caregivers.router,
            prefix="/workers",
            tags=["Workforce Members (alias)"],
        )
        api_router.include_router(caregiver_verification.router)
        api_router.include_router(academy.router)
        api_router.include_router(skills.router)
        api_router.include_router(assignments.router)
        api_router.include_router(prospects.router)
        api_router.include_router(recruitment.router)
        api_router.include_router(documents.router)
        api_router.include_router(geocode.router)
        api_router.include_router(geofence.router)
        api_router.include_router(scheduling.router, prefix="/scheduling")
        api_router.include_router(
            scheduling.router,
            prefix="/shifts",
            tags=["Shifts (WorkforceOS alias)"],
        )
        api_router.include_router(payroll.router)
        api_router.include_router(caregiver_portal.router)
        api_router.include_router(customer_portal.router)
        api_router.include_router(copilot.router)
        api_router.include_router(executive.router)
        api_router.include_router(workforce.router)
        api_router.include_router(cleaning.router)
        api_router.include_router(cleaning_crm.router)
        api_router.include_router(cleaning_pricebook.router)
        api_router.include_router(webhooks.router)
        api_router.include_router(subscriptions.router)
        api_router.include_router(workflows.router)
        api_router.include_router(platform.router)
        ''',
    )

    _patch_file(
        backend / "main.py",
        [
            ('title="WorkforceOS API"', 'title="HousekeepingOps API"'),
            ('description="WorkforceOS API — Elder Care vertical"', 'description="HousekeepingOps API — residential cleaning vertical"'),
        ],
    )

    _patch_file(
        backend / "core" / "config.py",
        [
            ('DEPLOY_VERTICAL: str = "ELDER_CARE"', 'DEPLOY_VERTICAL: str = "HOUSEKEEPING"'),
        ],
    )

    _patch_file(
        target / "backend" / ".env.example",
        [
            ("DEPLOY_VERTICAL=ELDER_CARE", "DEPLOY_VERTICAL=HOUSEKEEPING"),
            ("eldercareops.db", "housekeepingops.db"),
        ],
    )

    _patch_file(
        frontend / "package.json",
        [
            ('"name": "eldercareops"', '"name": "housekeepingops"'),
        ],
    )

    _write(
        target / "README.md",
        '''
        # HousekeepingOps

        > **Platform:** [WorkforceOS](https://github.com/krishnaposa/workforceos-core) · **Vertical:** Residential cleaning / housekeeping

        Deploy repo for the Housekeeping vertical. Shared platform code lives in
        [workforceos-core](https://github.com/krishnaposa/workforceos-core); this repo
        contains housekeeping domain models, APIs, and UI.

        ## Setup

        ```bash
        git clone -b develop https://github.com/krishnaposa/workforceos-core.git workforceos-core
        cd workforceos-core/typescript && npm install && npm run build
        cd ../../backend && pip install -r requirements.txt
        pip install -e ../workforceos-core/python
        python -m app.init_db
        python -m app.seed_cleaning_demo
        uvicorn app.main:app --reload
        ```

        ```bash
        cd frontend && npm install && npm run dev
        ```

        ## Environment

        ```env
        DEPLOY_VERTICAL=HOUSEKEEPING
        DATABASE_URL=sqlite:///./housekeepingops.db
        ```

        See [docs/DATABASE_ARCHITECTURE.md](docs/DATABASE_ARCHITECTURE.md) and
        [workforceos-core/BOUNDARIES.md](workforceos-core/BOUNDARIES.md).
        ''',
    )

    _write(
        target / "docs" / "VERTICAL_BOUNDARIES.md",
        '''
        # HousekeepingOps boundaries

        - **In this repo:** cleaning CRM, dispatch, price book, homeowner portal, cleaner PWA jobs
        - **In workforceos-core:** vertical features, nav, workflow templates, CRM/pricebook constants, adapter ABCs
        - **Customer spine:** `elders` table (interim) — properties link via `elder_id` until a native `Customer` model ships
        ''',
    )

    print("Done. Next steps:")
    print(f"  cd {target}")
    print("  git init && git add .")
    print("  Clone workforceos-core beside this repo, then install and test.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    bootstrap(args.target.resolve())


if __name__ == "__main__":
    main()
