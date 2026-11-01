import pytest
from workforceos_core.exceptions import WorkforceHTTPError

from app.core.custom_fields import (
    RESERVED_CAREGIVER_KEYS,
    RESERVED_ELDER_KEYS,
    VALID_FIELD_TYPES,
    _slug_key,
    validate_field_schema,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Diet Notes", "diet_notes"),
        ("  Blood Type  ", "blood_type"),
        ("Fall-Risk?", "fallrisk"),
        ("GPS_LAT", "gps_lat"),
        ("123abc", "123abc"),
        ("***", ""),
        ("A B C", "a_b_c"),
        ("Preferred Hospital!", "preferred_hospital"),
    ],
)
def test_slug_key(raw, expected):
    assert _slug_key(raw) == expected


def test_valid_field_types_cover_ui_set():
    assert VALID_FIELD_TYPES == {
        "text",
        "textarea",
        "number",
        "email",
        "phone",
        "date",
        "select",
        "boolean",
    }


def test_reserved_keys_are_frozen():
    assert "latitude" in RESERVED_ELDER_KEYS
    assert "languages" in RESERVED_CAREGIVER_KEYS
    assert "average_rating" in RESERVED_CAREGIVER_KEYS


def test_validate_happy_path_normalizes_defaults():
    out = validate_field_schema(
        [{"key": "Diet Notes", "label": "Diet", "type": "TEXT"}],
        frozenset(),
    )
    assert out == [
        {
            "key": "diet_notes",
            "label": "Diet",
            "type": "text",
            "required": False,
            "section": "Custom",
        }
    ]


def test_validate_select_requires_and_stringifies_options():
    out = validate_field_schema(
        [
            {
                "key": "mobility",
                "label": "Mobility",
                "type": "select",
                "options": ["Walker", 2],
                "required": True,
                "section": "Clinical",
            }
        ],
        frozenset(),
    )
    assert out[0]["options"] == ["Walker", "2"]
    assert out[0]["required"] is True
    assert out[0]["section"] == "Clinical"


@pytest.mark.parametrize(
    "fields,reserved,fragment",
    [
        ("not-a-list", frozenset(), "must be a list"),
        (["x"], frozenset(), "must be an object"),
        ([{"key": "***", "label": "X"}], frozenset(), "Field key is required"),
        ([{"key": "latitude", "label": "Lat"}], RESERVED_ELDER_KEYS, "reserved"),
        (
            [
                {"key": "notes", "label": "A"},
                {"key": "Notes", "label": "B"},
            ],
            frozenset(),
            "Duplicate",
        ),
        ([{"key": "notes", "label": "A", "type": "file"}], frozenset(), "Invalid type"),
        ([{"key": "notes", "label": "  "}], frozenset(), "Label required"),
        (
            [{"key": "mobility", "label": "M", "type": "select", "options": []}],
            frozenset(),
            "needs options",
        ),
    ],
)
def test_validate_rejects_invalid_schemas(fields, reserved, fragment):
    with pytest.raises(WorkforceHTTPError) as exc:
        validate_field_schema(fields, reserved)
    assert exc.value.status_code == 400
    assert fragment.lower() in str(exc.value.detail).lower()


def test_multiple_valid_fields():
    out = validate_field_schema(
        [
            {"key": "notes", "label": "Notes", "type": "textarea"},
            {"key": "allergies", "label": "Allergies", "type": "text"},
            {"key": "insulin", "label": "Insulin", "type": "boolean", "required": 1},
        ],
        RESERVED_ELDER_KEYS,
    )
    assert [f["key"] for f in out] == ["notes", "allergies", "insulin"]
    assert out[2]["required"] is True
