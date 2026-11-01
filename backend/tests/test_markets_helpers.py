from app.core.markets import (
    DEFAULT_MARKET,
    MARKET_IN,
    MARKET_US,
    market_currency,
    market_from_regional,
    market_label,
    market_meta,
    normalize_market,
)


def test_normalize_market_codes_and_country():
    assert normalize_market("us") == MARKET_US
    assert normalize_market("IN") == MARKET_IN
    assert normalize_market(None, country="United States") == MARKET_US
    assert normalize_market("XX") == DEFAULT_MARKET


def test_market_meta_currency():
    assert market_currency("IN") in {"INR", "₹"} or market_meta("IN")["currency"] == "INR"
    assert market_currency("US") == "USD"
    assert "India" in market_label("IN") or market_label("IN")


def test_market_from_regional():
    assert market_from_regional("USA") == MARKET_US
    assert market_from_regional("US") == MARKET_US
    assert market_from_regional("IND") == MARKET_IN
    assert market_from_regional(None) == MARKET_IN
