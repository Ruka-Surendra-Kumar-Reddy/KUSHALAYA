from app.core.config import settings
from app.core.deploy import deploy_has_feature, deploy_vertical, resolved_database_url


def test_deploy_vertical_normalizes(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOY_VERTICAL", "livewell360")
    assert deploy_vertical() == "LIVEWELL360"


def test_resolved_database_url_explicit(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./custom.db")
    assert resolved_database_url() == "sqlite:///./custom.db"


def test_resolved_database_url_default_when_empty(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "  ")
    monkeypatch.setattr(settings, "DEPLOY_VERTICAL", "LIVEWELL360")
    url = resolved_database_url()
    assert "sqlite" in url.lower()


def test_deploy_has_feature_livewell(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOY_VERTICAL", "LIVEWELL360")
    assert deploy_has_feature("livewell") is True
    assert deploy_has_feature("cleaning_dispatch") is False
