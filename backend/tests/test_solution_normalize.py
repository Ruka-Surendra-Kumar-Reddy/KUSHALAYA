from app.livewell.solution_service import normalize_solutions


def test_normalize_solutions_fills_name_finding_and_priority():
    out = normalize_solutions(
        {
            "schemaVersion": 2,
            "libraryVersion": "9.0",
            "solutions": [
                {
                    "id": "LW-1",
                    "solutionName": "Grab bar",
                    "priority": "URGENT",
                    "evidence_level": "z",
                    "aiVisualization": "yes",
                    "follow_up_days": "7",
                    "legacyIds": ["OLD-1", "OLD-1"],
                    "rubricItemIds": ["r1", ""],
                },
                {"id": "", "name": "skip me"},
                {"id": "LW-2", "finding": "No rail", "ai_visualization": False},
            ],
        }
    )
    assert out["schemaVersion"] == 2
    assert out["libraryVersion"] == "9.0"
    ids = [s["id"] for s in out["solutions"]]
    assert ids == ["LW-1", "LW-2"]
    first = out["solutions"][0]
    assert first["name"] == "Grab bar"
    assert first["finding"] == "Grab bar"
    assert first["priority"] == "medium"
    assert first["evidenceLevel"] == "B"
    assert first["aiVisualization"] is True
    assert first["followUpDays"] == 7
    assert first["legacyIds"] == ["OLD-1"]
    assert first["rubricItemIds"] == ["r1"]
    assert out["solutions"][1]["name"] == "No rail"


def test_normalize_solutions_empty():
    assert normalize_solutions({})["solutions"] == []
