import pytest

from app.livewell.catalog_types import (
    SERVICE_PREFIXES,
    default_category_types,
    normalize_category_type,
    resolve_category_types,
)


def test_default_category_types_cover_service_and_product():
    types = default_category_types()
    prefixes = [t["prefix"] for t in types]
    assert prefixes[0] == "SVC"
    assert "BTH" in prefixes
    assert all(t["active"] is True for t in types)
    services = {t["prefix"] for t in types if t["kind"] == "service"}
    assert SERVICE_PREFIXES <= services


@pytest.mark.parametrize(
    "raw,expected_kind,expected_sort",
    [
        ({"prefix": "bth", "label": "Bath"}, "product", 0),
        ({"prefix": "NUR", "label": "Nursing"}, "service", 0),
        ({"prefix": "XYZ", "kind": "service"}, "service", 0),
        ({"prefix": "XYZ", "kind": "weird", "sort": "3"}, "product", 3),
        ({"prefix": "ABC", "sort": "nope"}, "product", 5),
        ({"prefix": "SVC", "active": "false"}, "service", 0),
        ({"prefix": "BTH", "active": "0"}, "product", 0),
        ({"prefix": "BTH", "active": "yes"}, "product", 0),
    ],
)
def test_normalize_category_type(raw, expected_kind, expected_sort):
    out = normalize_category_type(raw, index=5)
    assert out["prefix"] == raw["prefix"].upper()
    assert out["kind"] == expected_kind
    if raw.get("sort") == "nope":
        assert out["sort"] == 5
    elif str(raw.get("sort", "")).isdigit() or isinstance(raw.get("sort"), int):
        assert out["sort"] == expected_sort
    assert isinstance(out["active"], bool)


def test_normalize_empty_prefix_returns_none():
    assert normalize_category_type({"prefix": "  "}) is None
    assert normalize_category_type({}) is None


def test_resolve_uses_defaults_when_empty():
    types = resolve_category_types(None, [])
    assert [t["prefix"] for t in types][0] == "SVC"


def test_resolve_skips_duplicates_and_non_dicts():
    types = resolve_category_types(
        [{"prefix": "BTH", "label": "Bath", "sort": 1}, "skip", {"prefix": "BTH"}],
        [],
    )
    assert [t["prefix"] for t in types].count("BTH") == 1


def test_resolve_adds_unknown_product_prefixes():
    types = resolve_category_types(
        [{"prefix": "BTH", "label": "Bath", "sort": 1}],
        [{"category_prefix": "ZZZ"}, {"category_prefix": "nUR"}],
    )
    prefixes = [t["prefix"] for t in types]
    assert "ZZZ" in prefixes
    assert "NUR" in prefixes
    zzz = next(t for t in types if t["prefix"] == "ZZZ")
    assert zzz["kind"] == "product"
    nur = next(t for t in types if t["prefix"] == "NUR")
    assert nur["kind"] == "service"
