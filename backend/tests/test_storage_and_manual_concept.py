"""Storage backends and manual concept upload."""

from io import BytesIO
from unittest.mock import MagicMock, patch

from app.core.storage import LocalStorageBackend, get_storage
from app.models.user import User


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_get_storage_defaults_to_local(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.STORAGE_BACKEND", "local")
    storage = get_storage()
    assert isinstance(storage, LocalStorageBackend)


def test_get_storage_r2_requires_credentials(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.STORAGE_BACKEND", "r2")
    monkeypatch.setattr("app.core.config.settings.S3_ENDPOINT_URL", "")
    monkeypatch.setattr("app.core.config.settings.S3_BUCKET", "")
    monkeypatch.setattr("app.core.config.settings.S3_ACCESS_KEY_ID", "")
    monkeypatch.setattr("app.core.config.settings.S3_SECRET_ACCESS_KEY", "")
    try:
        get_storage()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "S3_ENDPOINT_URL" in str(exc)


def test_s3_backend_save_read_mocked(monkeypatch):
    pytest = __import__("pytest")
    try:
        import boto3  # noqa: F401
    except ImportError:
        pytest.skip("boto3 not installed")

    monkeypatch.setattr("app.core.config.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr(
        "app.core.config.settings.S3_ENDPOINT_URL",
        "https://example.r2.cloudflarestorage.com",
    )
    monkeypatch.setattr("app.core.config.settings.S3_BUCKET", "livewell")
    monkeypatch.setattr("app.core.config.settings.S3_ACCESS_KEY_ID", "ak")
    monkeypatch.setattr("app.core.config.settings.S3_SECRET_ACCESS_KEY", "sk")
    monkeypatch.setattr("app.core.config.settings.S3_REGION", "auto")
    monkeypatch.setattr("app.core.config.settings.S3_PUBLIC_BASE_URL", "")

    mock_client = MagicMock()
    mock_client.head_bucket.return_value = {}
    mock_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: TINY_PNG),
        "ContentType": "image/png",
    }

    with patch("boto3.client", return_value=mock_client):
        storage = get_storage()
        key, url = storage.save(1, "elder", 9, "after.png", TINY_PNG, "image/png")
        assert key.startswith("1/elder/9/")
        assert url.startswith("s3://livewell/")
        mock_client.put_object.assert_called_once()
        content, mime = storage.read(key)
        assert content == TINY_PNG
        assert mime == "image/png"


def test_upload_concept_creates_manual_job(db, client, seed_tenant):
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath.png", BytesIO(TINY_PNG), "image/png")},
        data={
            "elder_id": str(elder_id),
            "assessment_id": "ASM-MANUAL-1",
            "caption": "Before",
            "room_type": "bathroom",
        },
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    concept = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/upload-concept",
        headers=headers,
        files={"file": ("after.png", BytesIO(TINY_PNG), "image/png")},
        data={
            "assessment_id": "ASM-MANUAL-1",
            "source_document_id": str(doc_id),
            "room_type": "bathroom",
            "package_level": "essential",
            "approved_solution_ids": '["SH-TEST"]',
            "elder_id": str(elder_id),
        },
    )
    assert concept.status_code == 200, concept.text
    body = concept.json()
    assert body["provider"] == "manual_upload"
    assert body["status"] == "needs_review"
    assert body["generated_document_id"]
    assert body["review_status"] == "pending"

    approved = client.post(
        f"/api/v1/home-safety/ai/visualization-jobs/{body['ai_job_id']}/review",
        headers=headers,
        json={"action": "approve", "notes": "manual after photo ok"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["status"] == "completed"
