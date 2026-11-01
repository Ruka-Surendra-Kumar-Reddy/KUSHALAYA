"""Admin-managed catalog types (SKU prefixes)."""

from __future__ import annotations

SERVICE_PREFIXES = frozenset({"SVC", "WEL", "NUR", "PHY", "DX", "HM", "PM", "TRN"})

_DEFAULT_TYPE_ROWS: tuple[tuple[str, str, int], ...] = (
    ("SVC", "Kushalaya Services", 0),
    ("BTH", "Bathroom Safety", 1),
    ("BED", "Bedroom Safety", 2),
    ("LIV", "Living Room", 3),
    ("EXT", "Entry & Exterior", 4),
    ("HAL", "Hallway Safety", 5),
    ("KIT", "Kitchen Safety", 6),
    ("BAL", "Balcony Safety", 7),
    ("MOB", "Mobility", 8),
    ("SMT", "Smart Home", 9),
    ("EMG", "Emergency Safety", 10),
    ("WEL", "Care & Wellness Services", 11),
    ("HM", "Home Maintenance", 12),
    ("NUR", "Nursing", 13),
    ("PHY", "Physiotherapy", 14),
    ("DX", "Doctor & Diagnostics", 15),
    ("PM", "Property Management", 16),
    ("TRN", "Transportation", 17),
    ("HLT", "Health Monitoring", 18),
)


def default_category_types() -> list[dict]:
    return [
        {
            "prefix": prefix,
            "label": label,
            "kind": "service" if prefix in SERVICE_PREFIXES else "product",
            "sort": sort,
            "active": True,
        }
        for prefix, label, sort in _DEFAULT_TYPE_ROWS
    ]


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)


def normalize_category_type(raw: dict, index: int = 0) -> dict | None:
    prefix = str(raw.get("prefix") or "").strip().upper()
    if not prefix:
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in ("service", "product"):
        kind = "service" if prefix in SERVICE_PREFIXES else "product"
    try:
        sort = int(raw.get("sort", index))
    except (TypeError, ValueError):
        sort = index
    return {
        "prefix": prefix,
        "label": str(raw.get("label") or "").strip() or prefix,
        "kind": kind,
        "sort": sort,
        "active": _as_bool(raw.get("active"), True),
    }


def resolve_category_types(raw_types: list | None, products: list[dict]) -> list[dict]:
    seen: set[str] = set()
    types: list[dict] = []
    for i, row in enumerate(raw_types or []):
        if not isinstance(row, dict):
            continue
        normalized = normalize_category_type(row, i)
        if not normalized or normalized["prefix"] in seen:
            continue
        seen.add(normalized["prefix"])
        types.append(normalized)

    if not types:
        types = default_category_types()
        seen = {t["prefix"] for t in types}

    extras = sorted(
        {
            str(p.get("category_prefix") or "").strip().upper()
            for p in products
            if str(p.get("category_prefix") or "").strip()
        }
        - seen
    )
    for i, prefix in enumerate(extras):
        types.append(
            {
                "prefix": prefix,
                "label": prefix,
                "kind": "service" if prefix in SERVICE_PREFIXES else "product",
                "sort": 100 + i,
                "active": True,
            }
        )

    types.sort(key=lambda t: (t["sort"], t["prefix"]))
    return types
