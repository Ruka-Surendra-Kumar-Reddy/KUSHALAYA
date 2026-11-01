"""Unit tests for spreadsheet money / ID / prefix parsers."""

from app.livewell.catalog_service import normalize_catalog
from app.livewell.workbook_format import (
    normalize_category_prefix,
    normalize_id_token,
    parse_money_inr,
    parse_percent,
)


def test_parse_money_inr_formats():
    assert parse_money_inr("3500") == 3500
    assert parse_money_inr("3,500") == 3500
    assert parse_money_inr("₹3,500") == 3500
    assert parse_money_inr("Rs. 3,500") == 3500
    assert parse_money_inr("INR 3500") == 3500
    assert parse_money_inr(3500) == 3500
    assert parse_money_inr(3500.0) == 3500
    assert parse_money_inr(0) == 0
    assert parse_money_inr("") is None
    assert parse_money_inr("Quote") is None
    assert parse_money_inr("n/a") is None
    assert parse_money_inr("not-a-price") is None


def test_parse_percent():
    assert parse_percent("25") == 25.0
    assert parse_percent("25%") == 25.0
    assert parse_percent(18) == 18.0
    assert parse_percent("") is None


def test_normalize_id_token():
    assert normalize_id_token(12345.0) == "12345"
    assert normalize_id_token("12345.0") == "12345"
    assert normalize_id_token("1.2345e4") == "12345"
    assert normalize_id_token("PROD-01") == "PROD-01"
    assert normalize_id_token(None) == ""


def test_normalize_category_prefix():
    assert normalize_category_prefix("bth") == "BTH"
    assert normalize_category_prefix("BTH") == "BTH"
    assert normalize_category_prefix("") is None
    assert normalize_category_prefix("none") is None


def test_normalize_catalog_coerces_money_and_prefix():
    catalog = normalize_catalog(
        {
            "products": [
                {
                    "id": "p1",
                    "name": "Grab bar",
                    "short_description": "Bar",
                    "price_inr": "₹3,500",
                    "category_prefix": "bth",
                }
            ],
            "packages": [
                {
                    "id": "pkg1",
                    "name": "Starter",
                    "price_inr": "12,000",
                    "product_ids": ["p1"],
                }
            ],
        }
    )
    assert catalog["products"][0]["price_inr"] == 3500
    assert catalog["products"][0]["category_prefix"] == "BTH"
    assert catalog["packages"][0]["price_inr"] == 12000
    prefixes = {row["prefix"] for row in catalog["category_types"]}
    assert "SVC" in prefixes
    assert "BTH" in prefixes
    kinds = {row["prefix"]: row["kind"] for row in catalog["category_types"]}
    assert kinds["SVC"] == "service"
    assert kinds["BTH"] == "product"
