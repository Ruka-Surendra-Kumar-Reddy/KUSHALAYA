"""Assessment questions for findings no question raised (docs/ASSESSMENT_PRODUCT_LINKS.md, 2026-10-11)."""

import json
from copy import deepcopy
from pathlib import Path

from sqlalchemy.orm.attributes import flag_modified

from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.config_keys import RUBRIC_KEY, SOLUTIONS_KEY
from app.livewell.rubric_defaults import DEFAULT_RUBRIC
from app.livewell.rubric_gap_fixes import (
    SOLUTION_DELETES,
    SOLUTION_MERGES,
    apply_solution_cleanup,
    NEW_ITEMS,
    RUBRIC_GAP_FIXES_KEY,
    RUBRIC_GAP_FIXES_VERSION,
    SOLUTION_LINKS,
    apply_rubric_gap_fixes,
)

DATA = Path(__file__).resolve().parents[1] / "app" / "livewell"
SEED_RUBRIC = json.loads((DATA / "default_rubric.json").read_text(encoding="utf-8"))
SEED_SOLUTIONS = json.loads((DATA / "default_solutions.json").read_text(encoding="utf-8"))
NEW_IDS = {item["id"] for _, _, item in NEW_ITEMS}


def _items(rubric: dict) -> dict[str, tuple[str, dict]]:
    return {i["id"]: (c["id"], i) for c in rubric["categories"] for i in c["items"]}


def _solutions_for(item_id: str, library: dict = SEED_SOLUTIONS) -> set[str]:
    """What buildImprovementPlan does: a Risk / Needs attention rating raises these solutions."""
    return {s["id"] for s in library["solutions"] if item_id in (s.get("rubricItemIds") or [])}


def _products_for(solution_id: str) -> set[str]:
    return {p["product_code"] for p in DEFAULT_CATALOG["products"] if solution_id in (p.get("solution_ids") or [])}


def test_seed_rubric_has_new_questions_in_the_right_sections():
    items = _items(SEED_RUBRIC)
    for cat_id, _after, item in NEW_ITEMS:
        assert item["id"] in items, item["id"]
        got_cat, got = items[item["id"]]
        assert got_cat == cat_id and got["label"] == item["label"]
        assert not got.get("hidden") and got["maxPoints"] > 0
    # Factory weights still sum to 100 (Independence Score).
    assert round(sum(i["maxPoints"] for c in SEED_RUBRIC["categories"] for i in c["items"]), 2) == 100


def test_every_solution_link_points_at_a_real_question():
    items = _items(SEED_RUBRIC)
    for sol in SEED_SOLUTIONS["solutions"]:
        for item_id in sol.get("rubricItemIds") or []:
            assert item_id in items, (sol["id"], item_id)
    for sol_id, ids in SOLUTION_LINKS.items():
        sol = next(s for s in SEED_SOLUTIONS["solutions"] if s["id"] == sol_id)
        assert set(ids) <= set(sol["rubricItemIds"]), sol_id


def test_wandering_emergency_and_tech_findings_are_reachable():
    assert "LW-COG-WAN-001" in _solutions_for("cognitive_emotional_safe_from_wandering_getting_lost")
    assert "LW-EMG-COM-001" in _solutions_for("emergency_sos_alert_method_available")
    assert "LW-EMG-COM-001" in _solutions_for("technology_can_use_phone_for_emergencies")
    assert "LW-TECH-LIT-001" in _solutions_for("technology_light_switches_easy_to_reach_and_operate")
    assert "LW-TECH-FAL-001" in _solutions_for("technology_smart_safety_devices_appropriate")
    assert "LW-TECH-SEC-001" in _solutions_for("technology_home_secure_locks_visitor_check")
    assert "SMT-012" in _products_for("LW-COG-WAN-001")
    assert "EMG-006" in _products_for("LW-EMG-COM-001")


def test_ventilation_transfer_and_health_findings_recommend_new_products():
    vent = set().union(*(_products_for(s) for s in _solutions_for("home_safety_bathroom_well_ventilated")))
    assert "BTH-013" in vent
    shower = set().union(*(_products_for(s) for s in _solutions_for("home_safety_shower_grab_bar_installed")))
    assert "BTH-012" in shower
    health = set().union(*(_products_for(s) for s in _solutions_for("health_wellness_bp_sugar_checked_regularly")))
    assert {"HLT-001", "HLT-002", "HLT-003"} <= health
    meds = set().union(*(_products_for(s) for s in _solutions_for("health_wellness_medications_reconciled")))
    assert "HLT-004" in meds


def _old_tenant_config() -> dict:
    """A tenant saved before the fix: no new questions, no links, plus admin edits."""
    rubric = deepcopy(DEFAULT_RUBRIC)  # normalized: integer points, as tenants store it
    for cat in rubric["categories"]:
        cat["items"] = [i for i in cat["items"] if i["id"] not in NEW_IDS]
        if cat["id"] == "technology":
            cat["items"][0]["label"] = "Admin-edited phone question"
            cat["items"][0]["maxPoints"] = 3
    sols = deepcopy(SEED_SOLUTIONS)
    for s in sols["solutions"]:
        if s["id"] in SOLUTION_LINKS:
            s["rubricItemIds"] = []
        if s["id"] == "LW-TECH-FAL-001":
            s["rubricItemIds"] = ["admin_custom_question"]
    return {RUBRIC_KEY: rubric, SOLUTIONS_KEY: sols, "other": {"keep": True}}


def test_apply_adds_questions_and_links_keeps_admin_edits_and_is_idempotent():
    old = _old_tenant_config()
    fixed, changes = apply_rubric_gap_fixes(old)
    assert changes
    items = _items(fixed[RUBRIC_KEY])
    for cat_id, after, item in NEW_ITEMS:
        got_cat, got = items[item["id"]]
        assert got_cat == cat_id and got["help"] and not got.get("hidden")
        cat = next(c for c in fixed[RUBRIC_KEY]["categories"] if c["id"] == cat_id)
        ids = [i["id"] for i in cat["items"]]
        assert ids.index(item["id"]) == ids.index(after) + 1
    # neighbour weight (integer 1), not the admin's 3
    assert items["technology_home_secure_locks_visitor_check"][1]["maxPoints"] == 1
    assert items["technology_can_use_phone_for_emergencies"][1]["label"] == "Admin-edited phone question"
    fal = next(s for s in fixed[SOLUTIONS_KEY]["solutions"] if s["id"] == "LW-TECH-FAL-001")
    assert fal["rubricItemIds"] == ["admin_custom_question", "technology_smart_safety_devices_appropriate"]
    assert _solutions_for("cognitive_emotional_safe_from_wandering_getting_lost", fixed[SOLUTIONS_KEY]) == {
        "LW-COG-WAN-001"
    }
    assert fixed["other"] == {"keep": True}

    again, changes2 = apply_rubric_gap_fixes(fixed)
    assert changes2 == [] and again == fixed


def test_apply_skips_tenants_without_stored_rubric():
    fixed, changes = apply_rubric_gap_fixes({})
    assert changes == [] and fixed == {}


def test_live_tenant_gets_questions_once_via_api(client, admin_headers, seed_tenant, db):
    tenant = seed_tenant["tenant"]
    tenant.workflow_config = _old_tenant_config()
    flag_modified(tenant, "workflow_config")
    db.commit()

    rubric = client.get("/api/v1/home-safety/rubric", headers=admin_headers).json()
    assert NEW_IDS <= set(_items(rubric))
    sols = client.get("/api/v1/home-safety/solutions", headers=admin_headers).json()
    wan = next(s for s in sols["solutions"] if s["id"] == "LW-COG-WAN-001")
    assert wan["rubricItemIds"] == SOLUTION_LINKS["LW-COG-WAN-001"]
    db.refresh(tenant)
    marker = tenant.workflow_config[RUBRIC_GAP_FIXES_KEY]
    assert marker["version"] == RUBRIC_GAP_FIXES_VERSION and marker["changes"] > 0

    # Admin removes a new question afterwards: it is not added back.
    cfg = deepcopy(tenant.workflow_config)
    for cat in cfg[RUBRIC_KEY]["categories"]:
        cat["items"] = [i for i in cat["items"] if i["id"] != "technology_home_secure_locks_visitor_check"]
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    rubric = client.get("/api/v1/home-safety/rubric", headers=admin_headers).json()
    assert "technology_home_secure_locks_visitor_check" not in _items(rubric)


# ---------------------------------------------------------------------------
# Scoring: old completed assessments do not lose points to the new questions.
# Same cases as frontend lib/livewell/conditional.added-on.test.ts.
# ---------------------------------------------------------------------------
from app.livewell.rubric_service import normalize_rubric  # noqa: E402
from app.livewell.scoring import score_assessment  # noqa: E402


def _old_ratings() -> dict:
    ratings = {}
    for n, (_cid, item) in enumerate(_items(SEED_RUBRIC).items()):
        if item[1]["id"] in NEW_IDS:
            continue
        ratings[item[1]["id"]] = ("excellent", "acceptable", "unsafe")[n % 3]
    return ratings


def test_old_completed_assessment_score_unchanged_by_gap_fix():
    old_cfg = _old_tenant_config()
    new_cfg, _ = apply_rubric_gap_fixes(old_cfg)
    before_cats = normalize_rubric(old_cfg[RUBRIC_KEY])["categories"]
    after_cats = normalize_rubric(new_cfg[RUBRIC_KEY])["categories"]
    payload = {
        "status": "completed",
        "createdAt": "2026-09-20T05:00:00Z",
        "completedAt": "2026-09-20T08:00:00Z",
        "ratings": _old_ratings(),
    }
    before = score_assessment(payload, before_cats)
    after = score_assessment(payload, after_cats)
    for key in ("independence_score", "domain_scores", "earned", "max", "critical_unsafe"):
        assert before[key] == after[key], key


def test_new_and_draft_assessments_count_the_new_questions():
    new_cfg, _ = apply_rubric_gap_fixes(_old_tenant_config())
    cats = normalize_rubric(new_cfg[RUBRIC_KEY])["categories"]
    old_completed = {"status": "completed", "createdAt": "2026-09-20T05:00:00Z", "ratings": _old_ratings()}
    base = score_assessment(old_completed, cats)
    # New assessment, new questions left unanswered: they count (0 points, full weight).
    fresh = score_assessment({**old_completed, "createdAt": "2026-10-12T05:00:00Z"}, cats)
    assert fresh["max"] == base["max"] + 5 and fresh["independence_score"] < base["independence_score"]
    # Old draft still in progress: the new questions are asked and count.
    draft = score_assessment({"status": "draft", "createdAt": "2026-09-20T05:00:00Z", "ratings": _old_ratings()}, cats)
    assert draft["max"] == fresh["max"]
    # Old completed assessment that did answer a new question keeps it.
    answered = dict(_old_ratings(), technology_home_secure_locks_visitor_check="unsafe")
    kept = score_assessment({**old_completed, "ratings": answered}, cats)
    assert kept["max"] == base["max"] + 1


def test_tiny_rubric_parity_case():
    """Fixed numbers shared with the frontend test (backend/frontend compute the same)."""
    cats = [
        {
            "id": "technology",
            "title": "Tech",
            "maxPoints": 2,
            "items": [
                {"id": "technology_can_use_phone_for_emergencies", "label": "Phone", "maxPoints": 1},
                {"id": "technology_home_secure_locks_visitor_check", "label": "Secure", "maxPoints": 1},
            ],
        }
    ]
    ratings = {"technology_can_use_phone_for_emergencies": "excellent"}
    old = {"status": "completed", "createdAt": "2026-10-01", "ratings": ratings}
    assert score_assessment(old, cats)["independence_score"] == 100
    assert score_assessment({**old, "createdAt": "2026-10-11"}, cats)["independence_score"] == 50
    assert score_assessment({**old, "status": "draft", "completedAt": None}, cats)["independence_score"] == 50


def test_admin_save_before_first_read_is_never_appended_to(db, seed_tenant):
    from app.livewell.rubric_service import HomeSafetyRubricService
    from app.livewell.solution_service import HomeSafetySolutionService

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    old = _old_tenant_config()
    HomeSafetyRubricService.save_rubric(db, admin, old[RUBRIC_KEY])
    HomeSafetySolutionService.save_solutions(db, admin, old[SOLUTIONS_KEY])
    db.refresh(tenant)
    assert tenant.workflow_config[RUBRIC_GAP_FIXES_KEY]["superseded_by"].startswith("admin")
    assert not NEW_IDS & set(_items(HomeSafetyRubricService.get_rubric(db, admin)))
    wan = next(s for s in HomeSafetySolutionService.get_solutions(db, admin)["solutions"] if s["id"] == "LW-COG-WAN-001")
    assert wan["rubricItemIds"] == []


def test_critical_questions_all_have_a_fix():
    """Question-reduction review (2026-10-13): a critical finding always has a recommended fix."""
    linked = {i for sol in SEED_SOLUTIONS["solutions"] for i in sol.get("rubricItemIds") or []}
    critical = [
        i["id"]
        for c in SEED_RUBRIC["categories"]
        for i in c["items"]
        if i.get("scoringScale") == "critical"
    ]
    assert critical and [i for i in critical if i not in linked] == []


def test_v2_on_a_v1_tenant_adds_links_but_never_questions():
    cfg = _old_tenant_config()
    cfg[RUBRIC_GAP_FIXES_KEY] = {"version": 1, "applied_at": "2026-10-11T00:00:00+00:00", "changes": 3}
    fixed, changes = apply_rubric_gap_fixes(cfg, add_questions=False)
    assert all(not c.startswith("rubric:") for c in changes)
    assert set(_items(fixed[RUBRIC_KEY])) == set(_items(cfg[RUBRIC_KEY]))
    pt = next(s for s in fixed[SOLUTIONS_KEY]["solutions"] if s["id"] == "LW-HC-PT-001")
    assert "mobility_transfers_bed_chair_safely" in pt["rubricItemIds"]


def test_seed_has_no_merged_or_deleted_solutions_and_aliases_resolve():
    ids = {s["id"] for s in SEED_SOLUTIONS["solutions"]}
    assert not (set(SOLUTION_MERGES) | set(SOLUTION_DELETES)) & ids
    for src, dst in SOLUTION_MERGES.items():
        target = next(s for s in SEED_SOLUTIONS["solutions"] if s["id"] == dst)
        assert src in target["legacyIds"], (src, dst)


def test_cleanup_merges_duplicates_and_keeps_admin_linked_ones():
    cfg = {
        SOLUTIONS_KEY: {
            "solutions": [
                {"id": "LW-HS-BED-002", "recommendedSolutions": ["Night light"], "rubricItemIds": ["x"]},
                {"id": "LW-HS-BED-007", "recommendedSolutions": ["Brighter bulbs", "Night light"], "rubricItemIds": []},
                {"id": "LW-HS-BTH-005", "recommendedSolutions": ["Motion sensor light"], "rubricItemIds": ["admin_linked"]},
                {"id": "LW-HS-BTH-009", "recommendedSolutions": ["Lever tap"], "rubricItemIds": []},
            ]
        }
    }
    out, changes = apply_solution_cleanup(cfg)
    sols = {s["id"]: s for s in out[SOLUTIONS_KEY]["solutions"]}
    assert "LW-HS-BED-007" not in sols and "LW-HS-BTH-009" not in sols
    assert sols["LW-HS-BED-002"]["recommendedSolutions"] == ["Night light", "Brighter bulbs"]
    assert "LW-HS-BED-007" in sols["LW-HS-BED-002"]["legacyIds"]
    assert "LW-HS-BTH-005" in sols  # an admin linked it to a question: left alone
    again, changes2 = apply_solution_cleanup(out)
    assert changes2 == [] and again == out
