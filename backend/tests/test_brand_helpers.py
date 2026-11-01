from app.core.config import settings
from app.livewell.brand import BRAND_TOKEN, DEFAULT_BRAND_NAME, brand_name, with_brand


def test_brand_name_default(monkeypatch):
    monkeypatch.setattr(settings, "BRAND_NAME", "")
    assert brand_name() == DEFAULT_BRAND_NAME
    assert DEFAULT_BRAND_NAME == "KushAlaya"


def test_brand_name_override(monkeypatch):
    monkeypatch.setattr(settings, "BRAND_NAME", "  SafeHome  ")
    assert brand_name() == "SafeHome"


def test_brand_name_blank_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "BRAND_NAME", "   ")
    assert brand_name() == DEFAULT_BRAND_NAME


def test_with_brand_replaces_token_and_trademark(monkeypatch):
    monkeypatch.setattr(settings, "BRAND_NAME", "AcmeCare")
    text = f"Welcome to {BRAND_TOKEN}™ and {BRAND_TOKEN} assessments"
    out = with_brand(text)
    assert "AcmeCare" in out
    assert BRAND_TOKEN not in out


def test_with_brand_noop_when_same(monkeypatch):
    monkeypatch.setattr(settings, "BRAND_NAME", "LiveWell360")
    text = "LiveWell360 home visit"
    assert with_brand(text) == text
