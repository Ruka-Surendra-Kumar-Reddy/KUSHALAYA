"""Unit tests for Gemini vision (C) and fal Kontext (E) providers."""

from unittest.mock import MagicMock, patch

from app.livewell.ai_provider import (
    AIImageJobPayload,
    FalKontextProvider,
    get_ai_provider,
)
from app.livewell.ai_vision_provider import (
    GeminiFlashVisionProvider,
    get_vision_provider,
)
from app.schemas.ai_visualization_contracts import (
    RoomAnalyzeRequest,
    RoomType,
    SourceImageRef,
)

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_get_ai_provider_fal_without_key_is_not_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.FAL_KEY", "")
    monkeypatch.setattr("app.core.config.settings.AI_RENDER_PROVIDER", "")
    provider = get_ai_provider({"default_provider": "fal_kontext"})
    assert provider.name() == "none"
    assert provider.is_configured() is False


def test_get_ai_provider_fal_with_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.FAL_KEY", "test-fal-key")
    monkeypatch.setattr("app.core.config.settings.AI_RENDER_PROVIDER", "")
    provider = get_ai_provider({"default_provider": "fal_kontext"})
    assert provider.name() == "fal_kontext"
    assert provider.is_configured() is True


def test_fal_kontext_generate_image_mocked(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.FAL_KEY", "test-fal-key")
    provider = FalKontextProvider(api_key="test-fal-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "images": [{"url": "https://example.com/out.png", "content_type": "image/png"}]
    }

    mock_img = MagicMock()
    mock_img.status_code = 200
    mock_img.content = TINY_PNG
    mock_img.headers = {"content-type": "image/png"}

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        client.get.return_value = mock_img
        result = provider.generate_image(
            AIImageJobPayload(
                ai_job_id="AIJ-1",
                assessment_id="ASM-1",
                room_type="bathroom",
                package_level="essential",
                original_image_url="/x",
                prompt="Add grab bar beside toilet",
                negative_prompt="",
                workflow="bathroom_essential_v1",
                model_name="flux-kontext",
                extra={"source_image_bytes": TINY_PNG},
            )
        )

    assert result.status == "completed"
    assert result.is_stub is False
    assert result.generated_image_bytes == TINY_PNG
    assert result.render_callback is not None
    assert result.render_callback.provenance is not None
    assert result.render_callback.provenance.is_stub is False
    assert result.render_callback.provenance.provider == "fal_kontext"


def test_get_vision_provider_defaults_to_gemini_when_key_present(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "g-key")
    monkeypatch.setattr("app.core.config.settings.AI_VISION_PROVIDER", "gemini")
    provider = get_vision_provider({"vision_provider": "gemini"})
    assert provider.name() == "gemini"
    assert provider.is_configured() is True


def test_gemini_analyze_filters_unknown_codes(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", "g-key")
    provider = GeminiFlashVisionProvider(api_key="g-key", model="gemini-3.5-flash")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"observations":['
                                '{"observation_code":"no_toilet_grab_bar","evidence":"none",'
                                '"photo_id":"12","confidence":0.91},'
                                '{"observation_code":"made_up_hazard","confidence":0.99}'
                                '],"limitations":["low light"]}'
                            )
                        }
                    ]
                }
            }
        ]
    }

    request = RoomAnalyzeRequest(
        job_id="ANL-1",
        room_id="ROOM-12",
        room_type=RoomType.BATHROOM,
        source_images=[
            SourceImageRef(photo_id="12", download_url="/p/12", sha256="abc")
        ],
    )

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        result = provider.analyze_room(
            request,
            image_bytes_by_photo_id={"12": TINY_PNG},
            allowed_finding_codes=["no_toilet_grab_bar", "no_shower_grab_bar"],
            assessor_confirm_min=0.6,
        )

    assert result.status == "SUCCEEDED"
    assert len(result.observations) == 1
    assert result.observations[0].observation_code == "no_toilet_grab_bar"
    assert result.observations[0].requires_human_verification is False
    assert "low light" in result.limitations
