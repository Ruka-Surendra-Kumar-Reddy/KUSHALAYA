"""LiveWell360 solution library — per-tenant workflow_config storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request
from app.livewell.config_keys import SOLUTIONS_KEY
from app.livewell.solution_id_aliases import reload_aliases_from_solutions
from app.livewell.stored_config import read_stored_config
from app.models.tenant import Tenant
from app.models.user import User

_DATA_FILE = Path(__file__).resolve().parent / "default_solutions.json"

VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
VALID_EVIDENCE = frozenset({"A", "B", "C"})


def _load_file_defaults() -> dict:
    with _DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


DEFAULT_SOLUTIONS: dict = _load_file_defaults()
reload_aliases_from_solutions(DEFAULT_SOLUTIONS.get("solutions") or [])


def _normalize_solution(raw: dict, index: int) -> dict:
    rec_solutions = [str(x).strip() for x in raw.get("recommendedSolutions") or [] if str(x).strip()]
    products = [str(x).strip() for x in raw.get("productCategories") or [] if str(x).strip()]
    rubric_ids = list(
        dict.fromkeys(str(x).strip() for x in raw.get("rubricItemIds") or [] if str(x).strip())
    )
    legacy_ids = list(
        dict.fromkeys(str(x).strip() for x in raw.get("legacyIds") or [] if str(x).strip())
    )
    priority = str(raw.get("priority", "medium")).lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"
    evidence = str(raw.get("evidenceLevel") or raw.get("evidence_level") or "B").strip().upper()
    if evidence not in VALID_EVIDENCE:
        evidence = "B"
    name = str(raw.get("name") or raw.get("solutionName") or "").strip()
    finding = str(raw.get("finding", "")).strip()
    if not finding and name:
        finding = name
    if not name and finding:
        name = finding
    ai_raw = raw.get("aiVisualization", raw.get("ai_visualization", False))
    if isinstance(ai_raw, str):
        ai_flag = ai_raw.strip().lower() in ("yes", "y", "true", "1")
    else:
        ai_flag = bool(ai_raw)
    try:
        follow_up = max(0, int(raw.get("followUpDays", raw.get("follow_up_days", 30)) or 0))
    except (TypeError, ValueError):
        follow_up = 30
    return {
        "id": str(raw.get("id", "")).strip(),
        "section": str(raw.get("section", "")).strip(),
        "subcategory": str(raw.get("subcategory", raw.get("Subcategory", ""))).strip(),
        "name": name,
        "finding": finding,
        "riskDescription": str(raw.get("riskDescription", "")).strip(),
        "priority": priority,
        "recommendedSolutions": rec_solutions or ([name] if name else []),
        "contractorType": str(raw.get("contractorType", "")).strip(),
        "productCategories": products,
        "estimatedCost": str(raw.get("estimatedCost", "")).strip(),
        "installationTime": str(raw.get("installationTime", "")).strip(),
        "scoreImprovement": max(0, int(raw.get("scoreImprovement") or 0)),
        "maintenanceRequirement": str(raw.get("maintenanceRequirement", "")).strip(),
        "futureUpgrades": str(raw.get("futureUpgrades", "")).strip(),
        "rubricItemIds": rubric_ids,
        "sort_order": int(raw.get("sort_order", index)),
        "legacyIds": legacy_ids,
        "evidenceLevel": evidence,
        "membershipImpact": str(
            raw.get("membershipImpact") or raw.get("membership_impact") or ""
        ).strip(),
        "aiVisualization": ai_flag,
        "followUpDays": follow_up,
    }


def normalize_solutions(raw: dict) -> dict:
    solutions = [_normalize_solution(s, i) for i, s in enumerate(raw.get("solutions") or [])]
    solutions = [s for s in solutions if s["id"] and (s["finding"] or s["name"])]
    solutions.sort(key=lambda s: s["sort_order"])
    reload_aliases_from_solutions(solutions)
    return {
        "solutions": solutions,
        "schemaVersion": int(raw.get("schemaVersion") or 1),
        "libraryVersion": str(raw.get("libraryVersion") or "1.0"),
    }


def _apply_gap_fixes(db: Session, tenant: Tenant) -> None:
    """Add the 2026-10-11 assessment questions / links once per tenant (rubric_gap_fixes)."""
    from app.livewell.rubric_gap_fixes import apply_rubric_gap_fixes_once

    try:
        apply_rubric_gap_fixes_once(db, tenant)
    except Exception:  # never block reading config
        db.rollback()
        logging.getLogger(__name__).exception("rubric gap fixes failed for tenant %s", tenant.id)


class HomeSafetySolutionService:

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
    def get_solutions(db: Session, user: User) -> dict:
        tenant = HomeSafetySolutionService._tenant(db, user)
        _apply_gap_fixes(db, tenant)
        stored = read_stored_config(tenant.workflow_config or {})["solutions"]
        return normalize_solutions(stored)

    @staticmethod
    def save_solutions(db: Session, user: User, payload: dict) -> dict:
        tenant = HomeSafetySolutionService._tenant(db, user)
        normalized = normalize_solutions(payload)
        if not normalized["solutions"]:
            raise_bad_request("At least one solution is required")
        cfg = dict(tenant.workflow_config or {})
        cfg[SOLUTIONS_KEY] = normalized
        from app.livewell.rubric_gap_fixes import mark_rubric_gap_fixes_current

        mark_rubric_gap_fixes_current(cfg, "admin solutions save")
        tenant.workflow_config = cfg
        db.commit()
        db.refresh(tenant)
        return normalized
