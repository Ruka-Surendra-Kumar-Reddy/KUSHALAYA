from app.livewell.solution_id_aliases import (
    LEGACY_TO_V1,
    remap_solution_ids,
    reload_aliases_from_solutions,
    resolve_solution_id,
)


def test_reload_and_resolve_legacy_ids():
    reload_aliases_from_solutions(
        [
            {"id": "LW-CAT-BTH-001", "legacyIds": ["LW-1", "LW-OLD"]},
            {"id": "", "legacyIds": ["skip"]},
            {"id": "LW-CAT-BTH-001", "legacyIds": ["LW-CAT-BTH-001"]},
        ]
    )
    assert resolve_solution_id("LW-1") == "LW-CAT-BTH-001"
    assert resolve_solution_id("LW-OLD") == "LW-CAT-BTH-001"
    assert resolve_solution_id("LW-CAT-BTH-001") == "LW-CAT-BTH-001"
    assert resolve_solution_id("unknown") == "unknown"
    assert resolve_solution_id("  LW-1  ") == "LW-CAT-BTH-001"
    assert resolve_solution_id("") == ""
    assert LEGACY_TO_V1["LW-1"] == "LW-CAT-BTH-001"


def test_remap_solution_ids_dedupes_and_skips_blank():
    reload_aliases_from_solutions(
        [{"id": "NEW-1", "legacyIds": ["OLD-1", "OLD-2"]}]
    )
    assert remap_solution_ids(["OLD-1", "OLD-2", "NEW-1", ""]) == ["NEW-1"]
    assert remap_solution_ids(None) == []
    assert remap_solution_ids([]) == []
