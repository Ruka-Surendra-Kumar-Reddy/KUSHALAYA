from app.livewell.master_data_drift import compute_field_drift, config_is_effectively_empty


def test_empty_configs_are_effectively_empty():
    assert config_is_effectively_empty(None) is True
    assert config_is_effectively_empty({}) is True


def test_drift_detects_added_and_changed_rubric_item():
    baseline = {
        "rubric": {
            "categories": [
                {
                    "id": "bath",
                    "title": "Bathroom",
                    "maxPoints": 4,
                    "items": [{"id": "b1", "label": "Grab bar", "maxPoints": 4}],
                }
            ]
        }
    }
    current = {
        "rubric": {
            "categories": [
                {
                    "id": "bath",
                    "title": "Bathroom Safety",
                    "maxPoints": 8,
                    "items": [
                        {"id": "b1", "label": "Grab bars", "maxPoints": 4},
                        {"id": "b2", "label": "Non-slip", "maxPoints": 4},
                    ],
                }
            ]
        }
    }
    drift = compute_field_drift(baseline, current)
    assert drift["dirty"] is True
    assert drift["change_count"] >= 2
    entities = {c["entity"] for c in drift["changes"]}
    assert "rubric_category" in entities or "rubric_question" in entities


def test_identical_configs_not_dirty():
    cfg = {
        "rubric": {
            "categories": [
                {
                    "id": "bath",
                    "title": "Bathroom",
                    "items": [{"id": "b1", "label": "Grab bar", "maxPoints": 4}],
                }
            ]
        }
    }
    drift = compute_field_drift(cfg, cfg)
    assert drift["dirty"] is False
    assert drift["change_count"] == 0
