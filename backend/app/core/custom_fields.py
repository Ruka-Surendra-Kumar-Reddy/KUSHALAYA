import re

from app.core.responses import raise_bad_request

VALID_FIELD_TYPES = frozenset({
    "text",
    "textarea",
    "number",
    "email",
    "phone",
    "date",
    "select",
    "boolean",
})

RESERVED_ELDER_KEYS = frozenset({
    "language_preference",
    "required_experience_years",
    "latitude",
    "longitude",
    "care_type",
    "schedule_requirements",
})

RESERVED_CAREGIVER_KEYS = frozenset({
    "languages",
    "latitude",
    "longitude",
    "availability",
    "average_rating",
})


def _slug_key(key: str) -> str:
    k = key.strip().lower().replace(" ", "_")
    k = re.sub(r"[^a-z0-9_]", "", k)
    return k


def validate_field_schema(
    fields: list[dict],
    reserved: frozenset[str],
) -> list[dict]:
    if not isinstance(fields, list):
        raise_bad_request("Field schema must be a list")

    seen: set[str] = set()
    normalized: list[dict] = []

    for raw in fields:
        if not isinstance(raw, dict):
            raise_bad_request("Each field definition must be an object")

        key = _slug_key(str(raw.get("key", "")))
        if not key:
            raise_bad_request("Field key is required")
        if key in reserved:
            raise_bad_request(f"Key '{key}' is reserved for system use")
        if key in seen:
            raise_bad_request(f"Duplicate field key: {key}")
        seen.add(key)

        field_type = str(raw.get("type", "text")).lower()
        if field_type not in VALID_FIELD_TYPES:
            raise_bad_request(
                f"Invalid type '{field_type}'. "
                f"Use: {', '.join(sorted(VALID_FIELD_TYPES))}"
            )

        label = str(raw.get("label", "")).strip()
        if not label:
            raise_bad_request(f"Label required for field '{key}'")

        entry = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(raw.get("required", False)),
            "section": raw.get("section") or "Custom",
        }
        if field_type == "select":
            options = raw.get("options") or []
            if not options:
                raise_bad_request(f"Select field '{key}' needs options")
            entry["options"] = [str(o) for o in options]

        normalized.append(entry)

    return normalized
