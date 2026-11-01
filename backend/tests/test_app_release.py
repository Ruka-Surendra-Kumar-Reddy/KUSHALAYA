"""Android app self-update: version check + APK download (public, no sign-in)."""

from __future__ import annotations

import json

import pytest

from app.api.v1 import app_release


@pytest.fixture
def releases(tmp_path, monkeypatch):
    monkeypatch.setattr(app_release, "releases_dir", lambda: tmp_path)
    return tmp_path


def test_nothing_published_is_404(client, releases):
    assert client.get("/api/v1/app-release/android/ops").status_code == 404
    assert client.get("/api/v1/app-release/android/ops/download").status_code == 404


def test_manifest_without_apk_is_404(client, releases):
    (releases / "ops.json").write_text(json.dumps({"version_code": 3}))
    assert client.get("/api/v1/app-release/android/ops").status_code == 404


def test_latest_and_download(client, releases):
    (releases / "family.json").write_text(json.dumps(
        {"version_code": 3, "version_name": "1.2", "sha256": "ab" * 32, "notes": "Faster SOS"}))
    (releases / "kushalaya-family.apk").write_bytes(b"PK-apk-bytes")

    res = client.get("/api/v1/app-release/android/family")
    assert res.status_code == 200
    assert res.json() == {
        "version_code": 3, "version_name": "1.2", "sha256": "ab" * 32, "notes": "Faster SOS",
        "url": "/api/v1/app-release/android/family/download",
    }
    apk = client.get("/api/v1/app-release/android/family/download")
    assert apk.status_code == 200 and apk.content == b"PK-apk-bytes"
    assert apk.headers["content-type"] == "application/vnd.android.package-archive"
    # The other app has nothing published; unknown apps are rejected.
    assert client.get("/api/v1/app-release/android/ops").status_code == 404
    assert client.get("/api/v1/app-release/android/evil").status_code == 422


def test_bad_manifest_is_404(client, releases):
    (releases / "ops.json").write_text("{not json")
    (releases / "kushalaya-ops.apk").write_bytes(b"x")
    assert client.get("/api/v1/app-release/android/ops").status_code == 404
