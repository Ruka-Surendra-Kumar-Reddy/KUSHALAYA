"""GPT Image room-preview provider: selection, input_fidelity retry, fal fallback."""

import base64

import pytest

from app.core.config import settings
from app.livewell import ai_provider
from app.livewell.ai_provider import AIImageJobPayload, FalKontextProvider, GptImageProvider, get_ai_provider


def _payload():
    return AIImageJobPayload(
        ai_job_id="AIJ-1", assessment_id="a", room_type="bathroom", package_level="comfort",
        original_image_url="", prompt="Add a grab bar", negative_prompt="", workflow="ROOM-PRESERVE",
        model_name="gpt_image", extra={"source_image_bytes": b"\xff\xd8fakejpeg"},
    )


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_OPENAI_IMAGE_DEPLOYMENT", "gpt-image-1-mini")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setattr(settings, "AI_RENDER_PROVIDER", "gpt_image")


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body
        self.text = str(body)

    def json(self):
        return self._body


def test_selected_and_retries_without_input_fidelity(azure, monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, params=None, headers=None, data=None, files=None):
            calls.append((url, dict(data)))
            if len(calls) == 1:
                return _Resp(400, {"error": "Unknown parameter: input_fidelity"})
            return _Resp(200, {"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]})

    import httpx

    monkeypatch.setattr(httpx, "Client", Client)
    provider = get_ai_provider({})
    assert isinstance(provider, GptImageProvider)
    res = provider.generate_image(_payload())
    assert res.status == "completed" and res.generated_image_bytes == b"PNGDATA"
    assert calls[0][0] == "https://example.openai.azure.com/openai/deployments/gpt-image-1-mini/images/edits"
    assert "input_fidelity" in calls[0][1] and "input_fidelity" not in calls[1][1]
    assert res.render_callback.provenance.provider == "gpt_image"


def test_falls_back_to_fal_when_gpt_fails(azure, monkeypatch):
    monkeypatch.setattr(GptImageProvider, "_edit", lambda self, s, p: (None, "boom", True))
    monkeypatch.setattr(settings, "FAL_KEY", "fal-key")
    monkeypatch.setattr(FalKontextProvider, "generate_image", lambda self, payload: ai_provider.AIImageJobResult(status="completed", generated_image_bytes=b"FAL"))
    res = GptImageProvider().generate_image(_payload())
    assert res.generated_image_bytes == b"FAL"


def test_not_configured_uses_fal(monkeypatch):
    monkeypatch.setattr(settings, "AI_RENDER_PROVIDER", "gpt_image")
    monkeypatch.setattr(settings, "AZURE_OPENAI_IMAGE_DEPLOYMENT", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "FAL_KEY", "fal-key")
    assert isinstance(get_ai_provider({}), FalKontextProvider)


# --- Gemini image (live renderer since 2026-10-11) ---------------------------------------


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(settings, "AI_RENDER_PROVIDER", "gemini_image")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "g")
    monkeypatch.setattr(settings, "AI_IMAGE_GEMINI_MODEL", "flash")
    monkeypatch.setattr(settings, "AI_IMAGE_GEMINI_RETRY_MODEL", "pro")


def test_gemini_fast_model_first_strong_model_on_retry(gemini, monkeypatch):
    from app.livewell.ai_provider import GeminiImageProvider

    used = []
    monkeypatch.setattr(GeminiImageProvider, "_edit", lambda self, m, s, p: (used.append(m) or b"IMG", "image/png", None))
    provider = get_ai_provider({})
    assert isinstance(provider, GeminiImageProvider)
    first = provider.generate_image(_payload())
    retry_payload = _payload()
    retry_payload.extra["attempt"] = 2
    second = provider.generate_image(retry_payload)
    assert used == ["flash", "pro"]
    assert first.model_used == "flash" and second.model_used == "pro"
    assert first.render_callback.provenance.provider == "gemini_image"


def test_gemini_tries_other_model_then_fal(gemini, monkeypatch):
    from app.livewell.ai_provider import GeminiImageProvider

    used = []
    monkeypatch.setattr(GeminiImageProvider, "_edit", lambda self, m, s, p: (used.append(m) or None, "", "down"))
    monkeypatch.setattr(settings, "FAL_KEY", "fal-key")
    monkeypatch.setattr(FalKontextProvider, "generate_image", lambda self, payload: ai_provider.AIImageJobResult(status="completed", generated_image_bytes=b"FAL"))
    res = GeminiImageProvider().generate_image(_payload())
    assert used == ["flash", "pro"] and res.generated_image_bytes == b"FAL"
