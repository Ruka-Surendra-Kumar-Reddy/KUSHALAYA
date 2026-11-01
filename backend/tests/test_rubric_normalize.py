from app.livewell.rubric_service import normalize_rubric


def test_normalize_rubric_from_list_and_dict():
    raw = [
        {
            "id": "bath",
            "title": "Bathroom",
            "sectionNumber": 2,
            "items": [
                {"id": "b1", "label": "Grab bar", "maxPoints": 4},
                {"id": "", "label": "skip"},
            ],
        },
        {
            "id": "entry",
            "title": "Entry",
            "section_number": 1,
            "items": [{"id": "e1", "label": "Lighting", "max_points": 2, "scoringScale": "weird"}],
        },
    ]
    out = normalize_rubric(raw)
    ids = [c["id"] for c in out["categories"]]
    assert ids == ["entry", "bath"]
    assert out["categories"][0]["maxPoints"] == 2
    assert out["categories"][1]["items"][0]["maxPoints"] == 4

    wrapped = normalize_rubric({"categories": raw})
    assert [c["id"] for c in wrapped["categories"]] == ids


def test_normalize_rubric_skips_empty_categories():
    out = normalize_rubric({"categories": [{"id": "x", "title": "X", "items": []}]})
    assert out["categories"] == []


def test_normalize_parses_skip_rules_and_sources():
    out = normalize_rubric(
        {
            "categories": [
                {
                    "id": "stairs",
                    "title": "Stairs",
                    "skipWhen": "unless_has_stairs",
                    "items": [
                        {
                            "id": "s1",
                            "label": "Handrail",
                            "source": "aarp",
                            "skipWhen": {"when": "unless_has_stairs"},
                            "group": "Rails",
                        }
                    ],
                }
            ]
        }
    )
    cat = out["categories"][0]
    assert cat["skipWhen"] == {"when": "unless_has_stairs"}
    assert cat["items"][0]["source"] == "aarp"
    assert cat["items"][0]["group"] == "Rails"


def test_normalize_keeps_input_type_and_help():
    out = normalize_rubric(
        {
            "categories": [
                {
                    "id": "bath",
                    "title": "Bathroom",
                    "items": [
                        {
                            "id": "b1",
                            "label": "Has grab bar",
                            "inputType": "yesno",
                            "help": "Look beside the toilet.",
                            "maxPoints": 3,
                        },
                        {
                            "id": "b2",
                            "label": "Notes",
                            "input_type": "text",
                            "maxPoints": 2,
                        },
                    ],
                }
            ]
        }
    )
    items = out["categories"][0]["items"]
    assert items[0]["inputType"] == "yesno"
    assert items[0]["help"] == "Look beside the toilet."
    assert items[1]["inputType"] == "text"
    assert "help" not in items[1]


# --- Question wording and answer options (rubric editor, 30 Oct) ---------------------


def _one_item(**extra):
    return normalize_rubric(
        [{"id": "c", "title": "C", "items": [{"id": "q1", "label": "Grab bar", "maxPoints": 2, **extra}]}]
    )["categories"][0]["items"][0]


def test_options_and_ask_are_kept_and_cleaned():
    item = _one_item(
        ask="  Is there a grab bar by the toilet?  ",
        options=[
            {"label": "  Yes, firm  ", "rating": "excellent"},
            {"label": "Yes, loose", "rating": "UNSAFE"},
            {"label": "No bar", "rating": "unsafe"},
            {"label": "   ", "rating": "acceptable"},
            {"label": "Odd", "rating": "great"},
            {"rating": "na"},
            "junk",
            {"label": "Never alone", "rating": "na"},
        ],
    )
    assert item["ask"] == "Is there a grab bar by the toilet?"
    assert item["options"] == [
        {"label": "Yes, firm", "rating": "excellent"},
        {"label": "Yes, loose", "rating": "unsafe"},
        {"label": "No bar", "rating": "unsafe"},
        {"label": "Never alone", "rating": "na"},
    ]


def test_options_limits():
    item = _one_item(ask="x" * 300, options=[{"label": "y" * 150, "rating": "excellent"}] * 12)
    assert len(item["ask"]) == 200
    assert len(item["options"]) == 8
    assert all(len(o["label"]) == 100 for o in item["options"])


def test_no_options_means_no_keys():
    item = _one_item(ask="  ", options=[])
    assert "ask" not in item and "options" not in item
    assert "options" not in _one_item(options="not a list")


def test_options_round_trip_via_api(client, admin_headers):
    cats = [{"id": "c", "title": "Entrance", "items": [{"id": "q1", "label": "Path", "maxPoints": 3}]}]
    first = cats[0]["items"][0]
    first["ask"] = "Is the path clear?"
    first["options"] = [
        {"label": "Clear", "rating": "excellent"},
        {"label": "A few things", "rating": "acceptable"},
        {"label": "Wires everywhere", "rating": "unsafe"},
        {"label": "Bad", "rating": "nope"},
    ]
    res = client.put("/api/v1/home-safety/rubric", headers=admin_headers, json={"categories": cats})
    assert res.status_code == 200, res.text
    again = client.get("/api/v1/home-safety/rubric", headers=admin_headers).json()
    item = next(i for c in again["categories"] for i in c["items"] if i["id"] == first["id"])
    assert item["ask"] == "Is the path clear?"
    assert [o["label"] for o in item["options"]] == ["Clear", "A few things", "Wires everywhere"]
    # Clearing the options removes them again.
    item["options"] = []
    client.put("/api/v1/home-safety/rubric", headers=admin_headers, json=again)
    final = client.get("/api/v1/home-safety/rubric", headers=admin_headers).json()
    item = next(i for c in final["categories"] for i in c["items"] if i["id"] == first["id"])
    assert "options" not in item
