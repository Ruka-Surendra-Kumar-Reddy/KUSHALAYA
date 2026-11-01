#!/usr/bin/env python3
"""Bootstrap SafeHomeOps deploy repo from ElderCareOps.

Creates a sibling directory with platform + customer spine + SafeHome 360™ vertical.
Run from ElderCareOps root:

    python scripts/bootstrap_safehomeops.py
    python scripts/bootstrap_safehomeops.py --target C:/pers/SafeHomeOps

After bootstrap:
  1. Apply workforceos-core patches — see scripts/workforceos-core-safehome/README.md
  2. Clone/link workforceos-core, install deps, init DB
  3. git init in SafeHomeOps and push to GitHub

ElderCareOps keeps elder-care domain; remove home_safety routes from ElderCare when
SafeHomeOps is live (see docs/SAFEHOMEOPS_SPLIT.md).
"""

from __future__ import annotations

import argparse
import shutil
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT.parent / "SafeHomeOps"

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
    "safehomeops.db",
    "WorkforceOS.db",
}

# Removed from SafeHome deploy — elder-care / housekeeping / workforce-heavy modules.
ELDER_ONLY_BACKEND_MODELS = {
    "elder_message.py",
    "elder_notification.py",
    "elder_requirement.py",
    "care_plan.py",
    "visit_care_note.py",
    "visit_checklist_log.py",
    "incident.py",
    "monitoring_alert.py",
    "monitoring_consent.py",
    "camera_event.py",
    "family_service_request.py",
    "invoice.py",
    "cleaning_crm_activity.py",
    "cleaning_customer_profile.py",
    "cleaning_lead.py",
    "cleaning_job.py",
    "cleaning_job_cleaner.py",
    "cleaning_property.py",
    "cleaning_quote.py",
    "cleaning_service_item.py",
    "cleaning_caregiver_pay_rate.py",
    "cleaning_property_rate.py",
    "cleaning_recurrence_rule.py",
}

ELDER_ONLY_BACKEND_SERVICES = {
    "monitoring_service.py",
    "monitoring_notifications.py",
    "monitoring_rules.py",
}

ELDER_ONLY_API = {
    "elders.py",
    "family_portal.py",
    "care_plans.py",
    "visit_execution.py",
    "monitoring.py",
    "communications.py",
    "billing.py",
    "matching.py",
    "cleaning.py",
    "cleaning_crm.py",
    "cleaning_pricebook.py",
    "caregiver_portal.py",
    "caregiver_verification.py",
    "caregivers.py",
    "assignments.py",
    "academy.py",
    "recruitment.py",
    "scheduling.py",
    "payroll.py",
    "geofence.py",
    "copilot.py",
    "executive.py",
    "workforce.py",
    "background_jobs.py",
}

ELDER_ONLY_PACKAGES = {
    "care_plans",
    "family_portal",
    "visit_execution",
    "visit_notifications",
    "customer_portal",
}

ELDER_ONLY_FRONTEND_APP = [
    "app/(app)/elders",
    "app/(app)/care-plans",
    "app/(app)/monitoring",
    "app/elder",
    "app/caregiver",
    "app/(app)/billing",
    "app/(app)/matching",
    "app/(app)/communications",
    "app/(app)/cleaning",
    "app/(app)/academy",
    "app/(app)/scheduling",
    "app/(app)/attendance",
    "app/(app)/payroll",
    "app/(app)/workforce",
    "app/(app)/executive",
    "app/(app)/copilot",
    "app/(app)/documents",
    "app/(app)/assignments",
    "app/(app)/caregivers",
    "app/homeowner",
]

ELDER_ONLY_FRONTEND_LIBS = [
    "lib/carePlans.ts",
    "lib/familyPortal.ts",  # SafeHome uses lib/livewell/familyApi + slim elderPortal
    "lib/matching.ts",
    "lib/monitoring.ts",
    "lib/cleaning",
    "lib/billing",
    "lib/staffCommunications.ts",
    "lib/visitExecution.ts",
    "lib/academy.ts",
    "lib/copilot.ts",
    "lib/customerPortalBilling.ts",
    "lib/geofence.ts",
    "lib/caregiverIdentity.ts",
]

# Next.js typechecks all components/; prune elder-only UI so `next build` succeeds.
ELDER_ONLY_FRONTEND_COMPONENTS = [
    "components/carePlans",
    "components/familyPortal",
    "components/visitExecution",
    "components/customerPortal",
    "components/communications",
    "components/MatchScoreBreakdown.tsx",
    "components/ElderShell.tsx",
    "components/ElderCommunications.tsx",
    "components/ElderForm.tsx",
    "components/ElderPortalAccountCard.tsx",
    "components/ElderPwaRegister.tsx",
    "components/MonitoringConsentCard.tsx",
    "components/MonitoringNav.tsx",
    "components/RequireElderAuth.tsx",
    "components/RequireCaregiverAuth.tsx",
    "components/CaregiverShell.tsx",
    "components/CaregiverVerificationWizard.tsx",
    "components/CaregiverPortalAccountCard.tsx",
    "components/CaregiverPwaRegister.tsx",
    "components/CaregiverForm.tsx",
    "components/CaregiverAcademyCard.tsx",
    "components/GeofenceCard.tsx",
    "components/WorkforceCopilotPanel.tsx",
    "components/WorkforceMarketplacePanel.tsx",
    "components/AttendanceNav.tsx",
    "components/OperationsNav.tsx",
]


ELDER_ONLY_TESTS = [
    "test_care_plans.py",
    "test_visit_execution.py",
    "test_monitoring.py",
    "test_monitoring_rules.py",
    "test_family_portal_adapters.py",
    "test_family_portal_service_requests.py",
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
    "test_matching.py",
    "test_billing.py",
    "test_caregiver_portal.py",
    "test_caregiver_pwa_depth.py",
    "test_caregiver_identity.py",
    "test_shift_swap.py",
    "test_auto_scheduling.py",
    "test_unstaffed_match.py",
    "test_geofence.py",
    "test_attendance_workflow.py",
    "test_statutory_payroll.py",
    "test_finance_outputs.py",
    "test_care_plan_editor.py",
    "test_staff_communications.py",
    "test_whatsapp_notifications.py",
    "test_copilot.py",
    "test_executive.py",
    "test_workforce.py",
    "test_academy.py",
    "test_recruitment_polish.py",
    "test_resume_parsing.py",
    "test_assignments.py",
    "test_background_jobs.py",
    "test_workforceos_core_jobs.py",
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

    print(f"Creating SafeHomeOps at {target}")
    target.mkdir(parents=True)

    for folder in ("backend", "frontend", "scripts", "docs", ".github"):
        _copy_tree(REPO_ROOT / folder, target / folder)

    for rel in ("backend/requirements.txt", "backend/pytest.ini", "backend/.env.example"):
        src = REPO_ROOT / rel
        if src.exists():
            shutil.copy2(src, target / rel)

    if (REPO_ROOT / "docker-compose.yml").exists():
        shutil.copy2(REPO_ROOT / "docker-compose.yml", target / "docker-compose.yml")

    # Copy workforceos-core patch kit into the new repo.
    patch_src = REPO_ROOT / "scripts" / "workforceos-core-safehome"
    if patch_src.is_dir():
        _copy_tree(patch_src, target / "workforceos-core-safehome")

    backend = target / "backend" / "app"
    models = backend / "models"
    for name in ELDER_ONLY_BACKEND_MODELS:
        _remove_path(models, name)

    services = backend / "services"
    for name in ELDER_ONLY_BACKEND_SERVICES:
        _remove_path(services, name)

    # Avoid eager imports of MatchingEngine / Monitoring / Scheduling (elder-only models).
    _write(
        services / "__init__.py",
        '''
        """Service layer — import modules directly (no eager elder-care re-exports)."""

        __all__: list[str] = []
        ''',
    )

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
        p = frontend / rel
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    for rel in ELDER_ONLY_FRONTEND_COMPONENTS:
        _remove_path(frontend, rel)

    _remove_path(frontend, "scripts/capture-cleaning-screenshots.mjs")
    _remove_path(frontend, "scripts/capture-pitch-screenshots.mjs")

    # Keep docs/livewell; drop elder-only vertical docs clutter optional
    _remove_path(target / "docs", "HOUSEKEEPINGOPS_SPLIT.md")

    _write(
        backend / "models" / "packs.py",
        '''
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
            "app.models.workflow_event",
            "app.models.workflow_task",
            "app.models.background_job",
            "app.models.subscription_plan",
            "app.models.tenant_subscription",
            "app.models.subscription_invoice",
            "app.models.skill",
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
        )

        SAFEHOME_MODULES: tuple[str, ...] = (
            "app.models.home_safety_ai_job",
            "app.models.home_safety_assessment",
        )

        PACK_MODULES: dict[str, tuple[str, ...]] = {
            "platform": PLATFORM_MODULES,
            "workforce": WORKFORCE_MODULES,
            "customer_spine": CUSTOMER_SPINE_MODULES,
            "safehome360": SAFEHOME_MODULES,
        }

        ALL_MODEL_MODULES: tuple[str, ...] = tuple(
            dict.fromkeys(module for modules in PACK_MODULES.values() for module in modules)
        )

        PACK_ORDER: tuple[str, ...] = (
            "platform",
            "workforce",
            "customer_spine",
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
        ''',
    )

    _write(
        backend / "core" / "safehome_constants.py",
        '''
        """Re-export SafeHome contract constants from workforceos-core."""

        from workforceos_core.safehome.config_keys import (
            AI_CONFIG_KEY,
            CATALOG_KEY,
            CONFIG_KEYS,
            PRICING_KEY,
            RUBRIC_KEY,
            SOLUTIONS_KEY,
            STAGING_KEY,
            SUPPLIERS_KEY,
            VERSIONS_KEY,
        )
        from workforceos_core.safehome.document_types import (
            HOME_SAFETY_CATALOG_IMAGE,
            HOME_SAFETY_PHOTO,
        )

        __all__ = [
            "AI_CONFIG_KEY",
            "CATALOG_KEY",
            "CONFIG_KEYS",
            "PRICING_KEY",
            "RUBRIC_KEY",
            "SOLUTIONS_KEY",
            "STAGING_KEY",
            "SUPPLIERS_KEY",
            "VERSIONS_KEY",
            "HOME_SAFETY_CATALOG_IMAGE",
            "HOME_SAFETY_PHOTO",
        ]
        ''',
    )

    _write(
        api / "router.py",
        '''
        from fastapi import APIRouter

        from app.api.v1 import (
            auth,
            documents,
            geocode,
            home_safety_ai,
            home_safety_assessments,
            home_safety_catalog,
            home_safety_family,
            home_safety_master_data,
            home_safety_pricing,
            home_safety_rubric,
            home_safety_solutions,
            home_safety_suppliers,
            home_safety_visits,
            platform,
            prospects,
            subscriptions,
            tenants,
            users,
            webhooks,
            workflows,
        )

        api_router = APIRouter(prefix="/api/v1")

        api_router.include_router(auth.router)
        api_router.include_router(tenants.router)
        api_router.include_router(users.router)
        api_router.include_router(prospects.router)
        api_router.include_router(documents.router)
        api_router.include_router(geocode.router)
        api_router.include_router(webhooks.router)
        api_router.include_router(subscriptions.router)
        api_router.include_router(workflows.router)
        api_router.include_router(platform.router)

        api_router.include_router(home_safety_catalog.router)
        api_router.include_router(home_safety_solutions.router)
        api_router.include_router(home_safety_pricing.router)
        api_router.include_router(home_safety_suppliers.router)
        api_router.include_router(home_safety_master_data.router)
        api_router.include_router(home_safety_rubric.router)
        api_router.include_router(home_safety_family.router)
        api_router.include_router(home_safety_visits.router)
        api_router.include_router(home_safety_family.photos_router)
        api_router.include_router(home_safety_ai.router)
        api_router.include_router(home_safety_assessments.router)
        ''',
    )

    _patch_file(
        backend / "main.py",
        [
            ('title="WorkforceOS API"', 'title="SafeHomeOps API"'),
            (
                'description="WorkforceOS API — Elder Care vertical"',
                'description="SafeHomeOps API — SafeHome 360™ assessments, catalog, and family app"',
            ),
        ],
    )

    _patch_file(
        backend / "core" / "config.py",
        [
            ('DEPLOY_VERTICAL: str = "ELDER_CARE"', 'DEPLOY_VERTICAL: str = "SAFEHOME360"'),
        ],
    )

    _patch_file(
        target / "backend" / ".env.example",
        [
            ("DEPLOY_VERTICAL=ELDER_CARE", "DEPLOY_VERTICAL=SAFEHOME360"),
            ("eldercareops.db", "safehomeops.db"),
        ],
    )

    _patch_file(
        frontend / "package.json",
        [
            ('"name": "eldercareops"', '"name": "safehomeops"'),
        ],
    )

    _patch_file(
        frontend / "app" / "layout.tsx",
        [
            ("ElderCareOps", "SafeHomeOps"),
            ("WorkforceOS", "SafeHomeOps"),
        ],
    )

    _write(
        target / "README.md",
        '''
        # SafeHomeOps

        > **Platform:** [WorkforceOS](https://github.com/krishnaposa/workforceos-core) · **Product:** SafeHome 360™

        Deploy repo for the SafeHome vertical — field assessments, solution catalog, pricing quotes,
        master workbook import, AI visualizations, and family PWA.

        Shared platform contracts live in **workforceos-core** (`SAFEHOME360` vertical pack).
        Elder care operations remain in [ElderCareOps](https://github.com/krishnaposa/ElderCareOps).

        ## Bootstrap source

        Generated from ElderCareOps:

        ```bash
        python scripts/bootstrap_safehomeops.py --target ../SafeHomeOps
        ```

        ## Prerequisites

        1. Apply patches in `workforceos-core-safehome/` to your **workforceos-core** clone (see README there).
        2. Link or clone workforceos-core beside this repo.

        ## Setup

        ```bash
        export WORKFORCEOS_CORE=../workforceos-core   # or /opt/workforceos-core
        bash scripts/link-workforceos-core.sh
        cd "$WORKFORCEOS_CORE/typescript" && npm ci && npm run build

        cd backend
        bash ../scripts/install-backend-deps.sh
        python -m app.init_db
        # Seed via Master Data admin UI, or POST /api/v1/home-safety/master-data/seed-defaults
        uvicorn app.main:app --reload --port 8010
        ```

        ```bash
        cd frontend && npm install && npm run dev -- -p 3010
        ```

        ## Environment

        ```env
        DEPLOY_VERTICAL=SAFEHOME360
        DATABASE_URL=sqlite:///./safehomeops.db
        ```

        ## URLs

        | App | Path |
        |-----|------|
        | Assessor PWA | `/home-safety` |
        | Family PWA | `/home-safety/family` |
        | Admin | `/home-safety/rubric`, `/catalog`, `/master-data`, … |

        See [docs/livewell/README.md](docs/livewell/README.md).
        ''',
    )

    _write(
        target / "docs" / "VERTICAL_BOUNDARIES.md",
        '''
        # SafeHomeOps boundaries

        | Layer | Location |
        |-------|----------|
        | Feature pack, nav, DB pack IDs | `workforceos-core/contracts/` |
        | Config key names, document types | `workforceos-core/python/.../safehome/` |
        | Assessment, catalog, AI, APIs | **this repo** (`backend/app/livewell/`) |
        | Assessor + family PWAs | **this repo** (`frontend/app/home-safety/`) |
        | Prospect / client spine | Shared `elders` + `elder_prospects` tables (customer_spine pack) |

        ## ElderCareOps integration (optional)

        When both products run for one agency, use prospect IDs from ElderCareOps CRM or
        run SafeHomeOps standalone with its own prospect pipeline (`/api/v1/prospects`).
        ''',
    )

    # Slim install script name in target
    if (target / "scripts" / "link-workforceos-core.sh").exists():
        pass

    print("Done. Next steps:")
    print(f"  1. Apply workforceos-core-safehome patches (see {target / 'workforceos-core-safehome' / 'README.md'})")
    print(f"  2. cd {target} && git init && git add .")
    print("  3. Clone workforceos-core, install deps, python -m app.init_db")
    print("  4. Remove home_safety from ElderCareOps when SafeHome deploy is live (docs/SAFEHOMEOPS_SPLIT.md)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    bootstrap(args.target.resolve())


if __name__ == "__main__":
    main()
