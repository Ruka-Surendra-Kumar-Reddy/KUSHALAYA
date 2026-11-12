"""One-time, per-tenant addition of assessment questions that raise unreached findings.

The rubric and solution library are stored per tenant in ``workflow_config``, so the
seed files alone do not reach live tenants. ``apply_rubric_gap_fixes_once`` runs when a
tenant's rubric or solutions are read: it appends the questions below to the stored
rubric only if their id is missing (existing items are never changed), appends the
listed question ids to each solution's ``rubricItemIds`` if missing (never removes),
logs what changed and records a marker in workflow_config so it never runs again.

Audit: docs/ASSESSMENT_PRODUCT_LINKS.md (2026-10-11).
"""

from __future__ import annotations

import logging
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.livewell.config_keys import RUBRIC_KEY, SOLUTIONS_KEY
from app.livewell.scoring import QUESTIONS_ADDED_ON

log = logging.getLogger(__name__)

RUBRIC_GAP_FIXES_KEY = "rubric_gap_fixes"
RUBRIC_GAP_FIXES_VERSION = 4  # v2: link unused solutions; v3: merge duplicates, drop 2 with no question (2026-10-13);
# v4: "Wandering risk" no longer raised by the stove/doors answer; plain entrance wording (2026-11-12)

# (category id, insert after this item id, item). Ids match frontend lwa-rubric.ts.
NEW_ITEMS: list[tuple[str, str, dict]] = [
    (
        "home_safety",
        "home_safety_hot_water_scald_risk_controlled",
        {
            "id": "home_safety_bathroom_well_ventilated",
            "label": "Bathroom well ventilated",
            "group": "Bath & wet areas",
            "help": "Exhaust fan or opening window clears steam; no damp floor, mould or musty smell after bathing.",
        },
    ),
    (
        "health_wellness",
        "health_wellness_nutrition_adequate",
        {
            "id": "health_wellness_bp_sugar_checked_regularly",
            "label": "BP / sugar checked regularly",
            "group": "Clinical baseline",
            "help": "Blood pressure / sugar checked at home as the doctor advised, with a working BP monitor or glucometer and a log.",
        },
    ),
    (
        "cognitive_emotional",
        "cognitive_emotional_social_engagement_present",
        {
            "id": "cognitive_emotional_safe_from_wandering_getting_lost",
            "label": "Safe from wandering / getting lost",
            "help": "Ask family about leaving home alone, getting lost or going out at night; check for a door alert and ID with a contact number.",
        },
    ),
    (
        "technology",
        "technology_wi_fi_power_backup_considered",
        {
            "id": "technology_light_switches_easy_to_reach_and_operate",
            "label": "Light switches easy to reach and operate",
            "help": "Can the elder reach and work the bedside, bathroom and hallway switches, including at night, without crossing a dark room?",
        },
    ),
    (
        "technology",
        "technology_light_switches_easy_to_reach_and_operate",
        {
            "id": "technology_home_secure_locks_visitor_check",
            "label": "Home secure (locks, visitor check)",
            "help": "Sturdy door locks in use and a way to see visitors before opening (peephole, chain, video doorbell).",
        },
    ),
]

# solution id -> rubric item ids that raise it (same as default_solutions.json).
SOLUTION_LINKS: dict[str, list[str]] = {
    "LW-COG-WAN-001": ["cognitive_emotional_safe_from_wandering_getting_lost"],
    "LW-EMG-COM-001": ["emergency_sos_alert_method_available", "technology_can_use_phone_for_emergencies"],
    "LW-TECH-LIT-001": ["technology_light_switches_easy_to_reach_and_operate"],
    "LW-TECH-FAL-001": ["technology_smart_safety_devices_appropriate"],
    "LW-TECH-SEC-001": ["technology_home_secure_locks_visitor_check"],
    "LW-HS-BTH-010": ["home_safety_bathroom_well_ventilated"],
    "LW-HL-MON-001": ["health_wellness_bp_sugar_checked_regularly"],
    # v2 (2026-10-13): see docs/ASSESSMENT_PRODUCT_LINKS.md and the question-reduction review.
    "LW-HS-BED-001": ["mobility_transfers_bed_chair_safely"],
    "LW-HS-BTH-001": ["adl_toileting_independently_or_with_plan"],
    "LW-HS-KIT-001": ["cognitive_emotional_judgment_safe_for_leaving_stove_doors"],
    "LW-EMG-PLN-001": ["emergency_emergency_contacts_posted", "emergency_family_response_plan_documented", "emergency_evacuation_path_understood"],
    "LW-HC-PT-001": ["mobility_transfers_bed_chair_safely", "mobility_stands_from_chair_without_arm_push", "adl_transfer_mobility_for_adls"],
    "LW-HS-BTH-007": ["mobility_door_widths_thresholds_accessible"],
    "LW-MOB-BAL-001": ["mobility_balance_adequate_for_home"],
    "LW-MOB-WCH-001": ["mobility_wheelchair_or_walker_path_clear"],
    "LW-HL-NUT-001": ["health_wellness_nutrition_adequate"],
    "LW-ADL-BAT-001": ["adl_bathing_independently_or_with_plan"],
    "LW-ADL-DRS-001": ["adl_dressing_independently_or_with_plan"],
    "LW-IADL-MEAL-001": ["iadl_prepares_or_receives_meals_safely"],
    "LW-IADL-SHOP-001": ["iadl_handles_shopping_errands"],
    "LW-COG-MEM-001": ["cognitive_emotional_memory_adequate_for_daily_safety", "cognitive_emotional_orientation_to_person_place_time"],
    "LW-SOC-LON-001": ["cognitive_emotional_social_engagement_present", "lifestyle_social_contacts_weekly"],
    "LW-HM-ELE-001": ["home_condition_electrical_outlets_wiring_safe"],
    "LW-HM-PLB-001": ["home_condition_plumbing_reliable", "home_condition_damp_mold_controlled"],
    "LW-HM-CLN-001": ["home_condition_repairs_backlog_acceptable", "iadl_light_housework_manageable"],
    "LW-PM-INSP-001": ["home_condition_no_major_structural_hazards"],
    "LW-FAM-ECM-001": ["family_support_willing_to_engage_ecm_if_recommended", "family_support_primary_caregiver_family_identified", "family_support_nri_remote_family_plan_if_applicable"],
    "LW-FAM-COM-001": ["family_support_check_in_frequency_adequate"],
    "LW-HC-PCP-001": ["health_wellness_chronic_conditions_documented", "health_wellness_pain_managed_acceptably", "health_wellness_vision_hearing_supports_in_place", "health_wellness_foot_sensation_adequate_for_walking"],
    "LW-FIN-GOV-001": ["financial_benefits_eligible_government_benefits_identified", "financial_benefits_income_pension_status_known"],
    "LW-FIN-DOC-001": ["financial_benefits_documents_available_for_applications", "financial_benefits_health_insurance_schemes_reviewed"],
    "LW-WELL-AGE-001": ["lifestyle_day_structure_routine_present", "lifestyle_sleep_environment_supportive"],
    "LW-WELL-SOC-001": ["lifestyle_meaningful_activities_available", "lifestyle_outdoor_community_access"],
}


def _neighbour_points(items: list[dict]) -> int | float:
    points = [i.get("maxPoints") for i in items if isinstance(i.get("maxPoints"), (int, float))]
    return Counter(points).most_common(1)[0][0] if points else 1


def apply_rubric_gap_fixes(cfg: dict | None, *, add_questions: bool = True) -> tuple[dict, list[str]]:
    """Return (workflow_config with the additions, change log). Idempotent; additive only.

    ``add_questions=False`` only appends solution links (used for v2 on tenants that
    already had v1, so a question an admin removed since is never put back).
    """
    out = deepcopy(cfg or {})
    changes: list[str] = []

    rubric = out.get(RUBRIC_KEY)
    if add_questions and isinstance(rubric, dict) and rubric.get("categories"):
        cats = [c for c in rubric["categories"] if isinstance(c, dict)]
        existing = {str(i.get("id")) for c in cats for i in c.get("items") or [] if isinstance(i, dict)}
        for cat_id, after_id, template in NEW_ITEMS:
            if template["id"] in existing:
                continue
            cat = next((c for c in cats if c.get("id") == cat_id), None)
            if cat is None:
                changes.append(f"rubric: {template['id']} skipped (no category {cat_id})")
                continue
            items = cat.setdefault("items", [])
            item = {
                "id": template["id"],
                "label": template["label"],
                "maxPoints": _neighbour_points(items),
                "scoringScale": "standard",
                "source": "livewell360",
                "help": template["help"],
                "addedOn": QUESTIONS_ADDED_ON.get(template["id"], ""),
            }
            if template.get("group") and any(i.get("group") == template["group"] for i in items):
                item["group"] = template["group"]
            pos = next((n + 1 for n, i in enumerate(items) if i.get("id") == after_id), len(items))
            items.insert(pos, item)
            if "maxPoints" in cat:
                cat["maxPoints"] = sum(float(i.get("maxPoints") or 0) for i in items)
                if float(cat["maxPoints"]).is_integer():
                    cat["maxPoints"] = int(cat["maxPoints"])
            existing.add(item["id"])
            changes.append(f"rubric: added {item['id']} to {cat_id}")

    library = out.get(SOLUTIONS_KEY)
    if isinstance(library, dict):
        for sol in library.get("solutions") or []:
            if not isinstance(sol, dict) or sol.get("id") not in SOLUTION_LINKS:
                continue
            before = list(sol.get("rubricItemIds") or [])
            after = before + [i for i in SOLUTION_LINKS[sol["id"]] if i not in before]
            if after != before:
                sol["rubricItemIds"] = after
                changes.append(f"solution {sol['id']}: rubricItemIds {before} -> {after}")
    return out, changes


# v3: duplicate solutions merged into the live one (old id kept as a legacy alias, so
# saved reports and product links still resolve); two with no question removed.
SOLUTION_MERGES: dict[str, str] = {
    "LW-HS-BTH-008": "LW-HS-BTH-011",
    "LW-HS-BED-007": "LW-HS-BED-002",
    "LW-HS-BTH-005": "LW-HS-BED-002",
    "LW-HS-LIV-002": "LW-HS-LIV-001",
    "LW-HS-BED-003": "LW-HS-LIV-001",
    "LW-HS-LIV-003": "LW-HS-LIV-001",
    "LW-HS-BTH-006": "LW-EMG-COM-001",
}
SOLUTION_DELETES: tuple[str, ...] = ("LW-HS-BTH-009", "LW-HS-BED-004")


# v4: a question that wrongly raised a solution. Removed only if still linked (an admin
# can link it again). The stove/doors answer keeps its own kitchen finding (LW-HS-KIT-001).
SOLUTION_UNLINKS: dict[str, list[str]] = {
    "LW-COG-WAN-001": ["cognitive_emotional_judgment_safe_for_leaving_stove_doors"],
}
# v4: finding wording, changed only where it is still the old seed text.
FINDING_RENAMES: dict[str, tuple[str, str]] = {
    "LW-HS-ENT-004": ("No accessible main entry", "Steps at the main entrance"),
}


def apply_finding_corrections(cfg: dict | None) -> tuple[dict, list[str]]:
    """v4 corrections on a stored library. Idempotent; leaves admin wording alone."""
    out = deepcopy(cfg or {})
    changes: list[str] = []
    library = out.get(SOLUTIONS_KEY)
    if not isinstance(library, dict):
        return out, changes
    for sol in library.get("solutions") or []:
        if not isinstance(sol, dict):
            continue
        drop = SOLUTION_UNLINKS.get(sol.get("id"), [])
        before = list(sol.get("rubricItemIds") or [])
        after = [i for i in before if i not in drop]
        if after != before:
            sol["rubricItemIds"] = after
            changes.append(f"solution {sol['id']}: unlinked {sorted(set(before) - set(after))}")
        rename = FINDING_RENAMES.get(sol.get("id"))
        if rename and sol.get("finding") == rename[0]:
            sol["finding"] = rename[1]
            changes.append(f"solution {sol['id']}: finding -> {rename[1]!r}")
    return out, changes


def apply_solution_cleanup(cfg: dict | None) -> tuple[dict, list[str]]:
    """Merge / remove the solutions above in a stored library. A source an admin has
    linked to questions since is left alone. Idempotent."""
    out = deepcopy(cfg or {})
    changes: list[str] = []
    library = out.get(SOLUTIONS_KEY)
    if not isinstance(library, dict):
        return out, changes
    sols = [s for s in library.get("solutions") or [] if isinstance(s, dict)]
    by_id = {str(s.get("id")): s for s in sols}
    gone: set[str] = set()
    for src, dst in SOLUTION_MERGES.items():
        source, target = by_id.get(src), by_id.get(dst)
        if source is None or target is None or source.get("rubricItemIds"):
            continue
        for field in ("recommendedSolutions", "productCategories"):
            cur = list(target.get(field) or [])
            target[field] = cur + [x for x in source.get(field) or [] if x not in cur]
        legacy = list(target.get("legacyIds") or [])
        for x in [src, *(source.get("legacyIds") or [])]:
            if x not in legacy and x != dst:
                legacy.append(x)
        target["legacyIds"] = legacy
        gone.add(src)
        changes.append(f"solution {src}: merged into {dst}")
    for sid in SOLUTION_DELETES:
        sol = by_id.get(sid)
        if sol is not None and not sol.get("rubricItemIds"):
            gone.add(sid)
            changes.append(f"solution {sid}: removed (no question)")
    if gone:
        library["solutions"] = [s for s in library.get("solutions") or [] if not (isinstance(s, dict) and s.get("id") in gone)]
    return out, changes


def mark_rubric_gap_fixes_current(cfg: dict, reason: str) -> dict:
    """An admin saved / imported the rubric or solutions: never append to them later."""
    marker = cfg.get(RUBRIC_GAP_FIXES_KEY)
    if not (isinstance(marker, dict) and int(marker.get("version") or 0) >= RUBRIC_GAP_FIXES_VERSION):
        cfg[RUBRIC_GAP_FIXES_KEY] = {
            "version": RUBRIC_GAP_FIXES_VERSION,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "changes": 0,
            "superseded_by": reason,
        }
    return cfg


def apply_rubric_gap_fixes_once(db: Session, tenant) -> bool:
    """Apply the additions to this tenant's stored rubric/solutions the first time. True if run."""
    cfg = tenant.workflow_config or {}
    marker = cfg.get(RUBRIC_GAP_FIXES_KEY)
    if isinstance(marker, dict) and int(marker.get("version") or 0) >= RUBRIC_GAP_FIXES_VERSION:
        return False
    had_v1 = isinstance(marker, dict) and int(marker.get("version") or 0) >= 1
    fixed, changes = apply_rubric_gap_fixes(cfg, add_questions=not had_v1)
    fixed, cleanup = apply_solution_cleanup(fixed)
    fixed, corrections = apply_finding_corrections(fixed)
    cleanup = cleanup + corrections
    changes += cleanup
    fixed[RUBRIC_GAP_FIXES_KEY] = {
        "version": RUBRIC_GAP_FIXES_VERSION,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "changes": len(changes),
    }
    tenant.workflow_config = fixed
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)
    for line in changes:
        log.info("rubric gap fix (tenant %s): %s", tenant.id, line)
    log.info("rubric gap fixes v%s applied to tenant %s: %d change(s)", RUBRIC_GAP_FIXES_VERSION, tenant.id, len(changes))
    return True
