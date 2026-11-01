from app.core.verticals import (
    ELDER_CARE,
    LIVEWELL360,
    VALID_VERTICALS,
    has_feature,
    normalize_vertical,
    vertical_label,
)


def test_livewell_constant_in_contract():
    assert LIVEWELL360 in VALID_VERTICALS
    assert normalize_vertical("livewell360") == LIVEWELL360
    assert "LiveWell" in vertical_label(LIVEWELL360)


def test_livewell_has_core_product_features():
    assert has_feature(LIVEWELL360, "livewell") is True
    assert has_feature(ELDER_CARE, "elders") is True
    assert has_feature(LIVEWELL360, "cleaning_dispatch") is False
