"""Pluggable AI image generation — Contract E compatible; local stub default."""

from __future__ import annotations

import base64
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.livewell.ai_stub_image import build_local_stub_concept
from app.schemas.ai_visualization_contracts import (
    QualityScores,
    RenderJobAccepted,
    RenderJobCallback,
    RenderJobRequest,
    RenderJobStatus,
    RenderOutputCandidate,
    RenderProvenance,
)


@dataclass
class AIImageJobPayload:
    """Legacy payload kept for compatibility; prefer RenderJobRequest."""

    ai_job_id: str
    assessment_id: str
    room_type: str
    package_level: str
    original_image_url: str
    prompt: str
    negative_prompt: str
    workflow: str
    model_name: str
    width: int = 1024
    height: int = 1024
    extra: dict[str, Any] = field(default_factory=dict)
    render_request: RenderJobRequest | None = None


@dataclass
class AIImageJobResult:
    status: str
    generated_image_url: str | None = None
    generated_image_bytes: bytes | None = None
    generated_content_type: str | None = None
    generation_time_seconds: int | None = None
    provider_job_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    is_stub: bool = False
    render_accepted: RenderJobAccepted | None = None
    render_callback: RenderJobCallback | None = None
    model_used: str | None = None


class AIProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        pass

    def submit_render(
        self,
        request: RenderJobRequest,
        *,
        source_image_bytes: bytes,
        extra: dict | None = None,
    ) -> AIImageJobResult:
        """Contract E entrypoint — default bridges to generate_image."""
        payload = AIImageJobPayload(
            ai_job_id=request.job_id,
            assessment_id=request.visualization_plan_id,
            room_type=(request.room_type or "OTHER").lower(),
            package_level=(request.package_level or "essential").lower(),
            original_image_url=request.source_image.download_url,
            prompt=request.prompt_text or "",
            negative_prompt=request.negative_prompt_text or "",
            workflow=request.generation.profile,
            model_name=self.name(),
            width=request.generation.output_width,
            height=request.generation.output_height,
            extra={
                "source_image_bytes": source_image_bytes,
                "modification_labels": [
                    (i.label or (i.product.product_code if i.product else i.render_item_id))
                    for i in request.render_items
                ],
                **(extra or {}),
            },
            render_request=request,
        )
        return self.generate_image(payload)


class LocalStubProvider(AIProvider):
    """Working Contract E stand-in when no GPU provider is configured."""

    def name(self) -> str:
        return "local_stub"

    def is_configured(self) -> bool:
        return True

    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        started = time.monotonic()
        request = payload.render_request
        source = payload.extra.get("source_image_bytes")
        if not isinstance(source, (bytes, bytearray)) or not source:
            return AIImageJobResult(
                status="failed",
                error_code="SOURCE_IMAGE_MISSING",
                error_message="Local stub requires source_image_bytes on the job payload.",
                retryable=False,
                is_stub=True,
            )

        if payload.extra.get("preview_mode"):
            # AI room preview: same room with numbered tags, so the slider lines up.
            from app.livewell.ai_room_preview import build_preview_stub

            labels = [str(x) for x in (payload.extra.get("product_names") or []) if str(x).strip()]
            try:
                img = build_preview_stub(bytes(source), labels)
            except Exception:
                img = None
            if img:
                return AIImageJobResult(
                    status="completed",
                    generated_image_bytes=img,
                    generated_content_type="image/png",
                    generation_time_seconds=max(1, int(round(time.monotonic() - started))),
                    provider_job_id=request.job_id if request else payload.ai_job_id,
                    error_message="Local stub preview (offline stand-in for the AI edit).",
                    is_stub=True,
                )

        mods = payload.extra.get("modification_labels") or []
        if not isinstance(mods, list):
            mods = []
        if request:
            mods = [
                (i.label or (i.product.product_code if i.product else i.render_item_id))
                for i in request.render_items
            ] or mods

        image_bytes, content_type, used_board = build_local_stub_concept(
            bytes(source),
            room_type=payload.room_type,
            package_level=payload.package_level,
            modifications=[str(m) for m in mods],
            width=payload.width,
            height=payload.height,
        )
        elapsed = max(1, int(round(time.monotonic() - started)))
        now = datetime.now(timezone.utc)
        job_id = request.job_id if request else payload.ai_job_id
        accepted = RenderJobAccepted(
            job_id=job_id,
            status=RenderJobStatus.QUEUED,
            status_url=f"/gpu/v1/jobs/{job_id}",
            accepted_at=now,
        )
        callback = RenderJobCallback(
            job_id=job_id,
            status=RenderJobStatus.SUCCEEDED,
            completed_at=now,
            outputs=[
                RenderOutputCandidate(
                    candidate_id="CAND-01",
                    image_bytes_b64=base64.b64encode(image_bytes).decode("ascii"),
                    content_type=content_type,
                    width_px=payload.width,
                    height_px=payload.height,
                    quality=QualityScores(
                        room_preservation_score=1.0,
                        placement_score=0.85,
                        artifact_score=0.05,
                    ),
                    review_required=True,
                )
            ],
            provenance=RenderProvenance(
                model_set_version="local-stub-1",
                prompt_template_version="ROOM-PRESERVE-STUB",
                seed=request.generation.seed if request else None,
                gpu_type="LOCAL_STUB",
                provider="local_stub",
                is_stub=True,
            ),
        )
        note = (
            "Local Contract E stub generated a before/after board for review. "
            "Set default_provider=fal_kontext and FAL_KEY for hosted FLUX Kontext edits."
            if used_board
            else (
                "Local Contract E stub stored a pass-through concept image "
                "(install Pillow for the labeled before/after board)."
            )
        )
        return AIImageJobResult(
            status="completed",
            generated_image_bytes=image_bytes,
            generated_content_type=content_type,
            generation_time_seconds=elapsed,
            provider_job_id=job_id,
            error_message=note,
            is_stub=True,
            render_accepted=accepted,
            render_callback=callback,
        )


class NotConfiguredProvider(AIProvider):
    """Prompts-only mode — no image produced."""

    def name(self) -> str:
        return "none"

    def is_configured(self) -> bool:
        return False

    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        return AIImageJobResult(
            status="awaiting_provider",
            error_code="PROVIDER_NOT_CONFIGURED",
            error_message=(
                "AI image provider is set to none. Use default_provider=local_stub "
                "for offline Contract E concepts, or configure FAL_KEY with "
                "default_provider=fal_kontext for hosted FLUX Kontext edits."
            ),
            retryable=False,
        )


class FalKontextProvider(AIProvider):
    """Contract E — FLUX.1 Kontext [pro] via fal.ai (hosted image edit)."""

    FAL_MODEL_PATH = "fal-ai/flux-pro/kontext"
    FAL_RUN_URL = f"https://fal.run/{FAL_MODEL_PATH}"

    def __init__(self, *, api_key: str | None = None) -> None:
        from app.core.config import settings as app_settings

        self._api_key = (api_key if api_key is not None else app_settings.FAL_KEY).strip()

    def name(self) -> str:
        return "fal_kontext"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        import base64
        import logging

        import httpx

        logger = logging.getLogger(__name__)
        if not self.is_configured():
            return AIImageJobResult(
                status="awaiting_provider",
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="FAL_KEY is not set; cannot call fal-ai/flux-pro/kontext.",
                retryable=False,
                is_stub=False,
            )

        source = payload.extra.get("source_image_bytes")
        if not isinstance(source, (bytes, bytearray)) or not source:
            return AIImageJobResult(
                status="failed",
                error_code="SOURCE_IMAGE_MISSING",
                error_message="Fal Kontext requires source_image_bytes on the job payload.",
                retryable=False,
                is_stub=False,
            )

        request = payload.render_request
        started = time.monotonic()
        mime = "image/png" if bytes(source)[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        data_uri = f"data:{mime};base64,{base64.b64encode(bytes(source)).decode('ascii')}"
        prompt = (payload.prompt or "").strip() or "Preserve the room; apply approved safety modifications."
        mods = payload.extra.get("modification_labels") or []
        if isinstance(mods, list) and mods and not payload.extra.get("preview_mode"):
            mod_lines = "\n".join(f"- {m}" for m in mods if str(m).strip())
            if mod_lines and "INSERT these specific safety products" not in prompt:
                prompt = (
                    "Visually insert these products into the room photo (keep layout/camera):\n"
                    f"{mod_lines}\n\n"
                    + prompt
                )
        body: dict[str, Any] = {
            "prompt": prompt,
            "image_url": data_uri,
            "num_images": 1,
            "output_format": "png",
        }
        # Guidance for aspect; fal accepts optional width/height on some models
        if payload.width and payload.height:
            body["image_size"] = {
                "width": int(payload.width),
                "height": int(payload.height),
            }

        try:
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(
                    self.FAL_RUN_URL,
                    headers={
                        "Authorization": f"Key {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if resp.status_code >= 400:
                    logger.warning("fal Kontext HTTP %s: %s", resp.status_code, resp.text[:400])
                    return AIImageJobResult(
                        status="failed",
                        error_code="FAL_HTTP_ERROR",
                        error_message=f"fal.ai returned HTTP {resp.status_code}: {resp.text[:300]}",
                        retryable=resp.status_code >= 500,
                        is_stub=False,
                    )
                payload_json = resp.json()
        except Exception as exc:
            logger.exception("fal Kontext request failed")
            return AIImageJobResult(
                status="failed",
                error_code="FAL_REQUEST_FAILED",
                error_message=str(exc),
                retryable=True,
                is_stub=False,
            )

        image_url, image_bytes, content_type = _extract_fal_image(payload_json)
        if not image_bytes and image_url:
            try:
                with httpx.Client(timeout=120.0) as client:
                    img_resp = client.get(image_url)
                    if img_resp.status_code < 400 and img_resp.content:
                        image_bytes = img_resp.content
                        content_type = img_resp.headers.get("content-type") or "image/png"
            except Exception as exc:
                logger.warning("fal image download failed: %s", exc)

        if not image_bytes:
            return AIImageJobResult(
                status="failed",
                error_code="FAL_NO_IMAGE",
                error_message="fal.ai response did not include a downloadable image.",
                retryable=True,
                is_stub=False,
            )

        elapsed = max(1, int(round(time.monotonic() - started)))
        now = datetime.now(timezone.utc)
        job_id = request.job_id if request else payload.ai_job_id
        accepted = RenderJobAccepted(
            job_id=job_id,
            status=RenderJobStatus.QUEUED,
            status_url=f"/gpu/v1/jobs/{job_id}",
            accepted_at=now,
        )
        callback = RenderJobCallback(
            job_id=job_id,
            status=RenderJobStatus.SUCCEEDED,
            completed_at=now,
            outputs=[
                RenderOutputCandidate(
                    candidate_id="CAND-01",
                    image_bytes_b64=base64.b64encode(image_bytes).decode("ascii"),
                    content_type=content_type or "image/png",
                    width_px=payload.width,
                    height_px=payload.height,
                    quality=QualityScores(
                        room_preservation_score=0.9,
                        placement_score=0.8,
                        artifact_score=0.1,
                    ),
                    review_required=True,
                )
            ],
            provenance=RenderProvenance(
                model_set_version="flux-kontext-pro",
                prompt_template_version=payload.workflow or "ROOM-PRESERVE",
                seed=request.generation.seed if request else None,
                gpu_type="FAL_HOSTED",
                provider="fal_kontext",
                is_stub=False,
            ),
        )
        return AIImageJobResult(
            status="completed",
            generated_image_bytes=image_bytes,
            generated_content_type=content_type or "image/png",
            generated_image_url=image_url,
            generation_time_seconds=elapsed,
            provider_job_id=job_id,
            is_stub=False,
            render_accepted=accepted,
            render_callback=callback,
        )


def _completed(job_id: str, image_bytes: bytes, content_type: str, payload: AIImageJobPayload, *,
               provider: str, model: str, host: str, started: float) -> AIImageJobResult:
    """Successful render result in the Contract E shape the visualization service expects."""
    import base64

    now = datetime.now(timezone.utc)
    return AIImageJobResult(
        status="completed",
        generated_image_bytes=image_bytes,
        generated_content_type=content_type,
        generation_time_seconds=max(1, int(round(time.monotonic() - started))),
        provider_job_id=job_id,
        model_used=model,
        render_accepted=RenderJobAccepted(
            job_id=job_id, status=RenderJobStatus.QUEUED, status_url=f"/gpu/v1/jobs/{job_id}", accepted_at=now
        ),
        render_callback=RenderJobCallback(
            job_id=job_id,
            status=RenderJobStatus.SUCCEEDED,
            completed_at=now,
            outputs=[
                RenderOutputCandidate(
                    candidate_id="CAND-01",
                    image_bytes_b64=base64.b64encode(image_bytes).decode("ascii"),
                    content_type=content_type,
                    width_px=payload.width,
                    height_px=payload.height,
                    quality=QualityScores(room_preservation_score=0.9, placement_score=0.8, artifact_score=0.1),
                    review_required=True,
                )
            ],
            provenance=RenderProvenance(
                model_set_version=model,
                prompt_template_version=payload.workflow or "ROOM-PRESERVE",
                seed=None,
                gpu_type=host,
                provider=provider,
                is_stub=False,
            ),
        ),
    )


class GeminiImageProvider(AIProvider):
    """Google Gemini image edit. In trials (2026-10-11, 3 demo rooms) it showed every requested
    product without changing the room, where fal Kontext dropped products and removed objects.

    The first render uses the fast model (AI_IMAGE_GEMINI_MODEL); the automatic retry, made when
    the QA finds a missing product or a changed room, uses the stronger AI_IMAGE_GEMINI_RETRY_MODEL.
    If both fail and FAL_KEY is set, fal Kontext renders instead.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self) -> None:
        from app.core.config import settings as s

        self._key = (s.GEMINI_API_KEY or "").strip()
        self._first = (s.AI_IMAGE_GEMINI_MODEL or "gemini-3.1-flash-image").strip()
        self._retry = (s.AI_IMAGE_GEMINI_RETRY_MODEL or "gemini-3-pro-image").strip()

    def name(self) -> str:
        return "gemini_image"

    def is_configured(self) -> bool:
        return bool(self._key)

    def _edit(self, model: str, source: bytes, prompt: str) -> tuple[bytes | None, str, str | None]:
        """One edit call → (image bytes, content type, error text)."""
        import base64
        import logging

        import httpx

        mime = "image/png" if source[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": base64.b64encode(source).decode("ascii")}},
                    ],
                }
            ],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        try:
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(self.URL.format(model=model), params={"key": self._key}, json=body)
        except Exception as exc:
            logging.getLogger(__name__).warning("Gemini image request failed: %s", type(exc).__name__)
            return None, "", f"Gemini image request failed: {type(exc).__name__}"
        if resp.status_code >= 400:
            logging.getLogger(__name__).warning("Gemini image HTTP %s: %s", resp.status_code, resp.text[:300])
            return None, "", f"Gemini image returned HTTP {resp.status_code}"
        try:
            for part in resp.json()["candidates"][0]["content"]["parts"]:
                data = part.get("inlineData") or part.get("inline_data")
                if data and data.get("data"):
                    return base64.b64decode(data["data"]), data.get("mimeType") or data.get("mime_type") or "image/png", None
        except Exception:
            pass
        return None, "", "Gemini image response did not include an image."

    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        if not self.is_configured():
            return AIImageJobResult(
                status="awaiting_provider",
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="GEMINI_API_KEY is not set; cannot render with Gemini.",
            )
        source = payload.extra.get("source_image_bytes")
        if not isinstance(source, (bytes, bytearray)) or not source:
            return AIImageJobResult(
                status="failed",
                error_code="SOURCE_IMAGE_MISSING",
                error_message="Gemini image requires source_image_bytes on the job payload.",
            )
        prompt = (payload.prompt or "").strip() or "Preserve the room; apply approved safety modifications."
        retry = int(payload.extra.get("attempt") or 1) > 1
        models = [self._retry, self._first] if retry else [self._first, self._retry]
        request = payload.render_request
        job_id = request.job_id if request else payload.ai_job_id
        started = time.monotonic()
        error = None
        for model in dict.fromkeys(m for m in models if m):
            image, ctype, error = self._edit(model, bytes(source), prompt)
            if image:
                return _completed(job_id, image, ctype or "image/png", payload, provider="gemini_image",
                                  model=model, host="GOOGLE_GEMINI", started=started)
        fal = FalKontextProvider()
        if fal.is_configured():
            return fal.generate_image(payload)
        return AIImageJobResult(status="failed", error_code="GEMINI_IMAGE_FAILED", error_message=error, retryable=True)


class GptImageProvider(AIProvider):
    """OpenAI GPT Image edit (e.g. gpt-image-2) via Azure OpenAI or the OpenAI API.

    Azure is used when AZURE_OPENAI_IMAGE_DEPLOYMENT is set (endpoint/key default to the
    chat ones); otherwise OPENAI_API_KEY + OPENAI_IMAGE_MODEL. If the GPT call fails and
    FAL_KEY is set, the render falls back to fal Kontext so a preview still comes back.
    """

    def __init__(self) -> None:
        from app.core.config import settings as s

        self._az_deployment = (s.AZURE_OPENAI_IMAGE_DEPLOYMENT or "").strip()
        self._az_endpoint = (s.AZURE_OPENAI_IMAGE_ENDPOINT or s.AZURE_OPENAI_ENDPOINT or "").strip().rstrip("/")
        self._az_key = (s.AZURE_OPENAI_IMAGE_API_KEY or s.AZURE_OPENAI_API_KEY or "").strip()
        self._az_version = (s.AZURE_OPENAI_IMAGE_API_VERSION or "2025-04-01-preview").strip()
        self._oa_key = (s.OPENAI_API_KEY or "").strip()
        self._oa_model = (s.OPENAI_IMAGE_MODEL or "gpt-image-1-mini").strip()
        self._quality = (s.AI_IMAGE_QUALITY or "medium").strip().lower()

    def name(self) -> str:
        return "gpt_image"

    def _azure(self) -> bool:
        return bool(self._az_deployment and self._az_endpoint and self._az_key)

    def is_configured(self) -> bool:
        return self._azure() or bool(self._oa_key)

    def model_label(self) -> str:
        return self._az_deployment if self._azure() else self._oa_model

    @staticmethod
    def _size(source: bytes) -> str:
        """Closest GPT Image size to the photo's shape (the API takes three sizes)."""
        try:
            import io

            from PIL import Image

            w, h = Image.open(io.BytesIO(source)).size
        except Exception:
            return "1024x1024"
        if w > h * 1.15:
            return "1536x1024"
        if h > w * 1.15:
            return "1024x1536"
        return "1024x1024"

    def _edit(self, source: bytes, prompt: str) -> tuple[bytes | None, str | None, bool]:
        """One edit call → (png bytes, error text, retryable)."""
        import base64
        import logging

        import httpx

        logger = logging.getLogger(__name__)
        mime = "image/png" if source[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        if self._azure():
            url = f"{self._az_endpoint}/openai/deployments/{self._az_deployment}/images/edits"
            params = {"api-version": self._az_version}
            headers = {"api-key": self._az_key}
            fields = {}
        else:
            url = "https://api.openai.com/v1/images/edits"
            params = {}
            headers = {"Authorization": f"Bearer {self._oa_key}"}
            fields = {"model": self._oa_model}
        fields.update({"prompt": prompt, "n": "1", "size": self._size(source), "quality": self._quality, "input_fidelity": "high"})
        for attempt in range(2):
            try:
                with httpx.Client(timeout=240.0) as client:
                    resp = client.post(
                        url,
                        params=params,
                        headers=headers,
                        data=fields,
                        files={"image": (f"room.{mime.split('/')[1]}", source, mime)},
                    )
            except Exception as exc:
                logger.warning("GPT image request failed: %s", type(exc).__name__)
                return None, f"GPT image request failed: {type(exc).__name__}", True
            # Older/other models reject input_fidelity: drop it once and retry.
            if resp.status_code == 400 and attempt == 0 and "input_fidelity" in resp.text:
                fields.pop("input_fidelity", None)
                continue
            break
        if resp.status_code >= 400:
            logger.warning("GPT image HTTP %s: %s", resp.status_code, resp.text[:300])
            return None, f"GPT image returned HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code >= 500 or resp.status_code == 429
        try:
            b64 = resp.json()["data"][0]["b64_json"]
            return base64.b64decode(b64), None, False
        except Exception:
            return None, "GPT image response did not include an image.", True

    def generate_image(self, payload: AIImageJobPayload) -> AIImageJobResult:
        import base64

        if not self.is_configured():
            return AIImageJobResult(
                status="awaiting_provider",
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="Set AZURE_OPENAI_IMAGE_DEPLOYMENT (or OPENAI_API_KEY) to use GPT Image.",
            )
        source = payload.extra.get("source_image_bytes")
        if not isinstance(source, (bytes, bytearray)) or not source:
            return AIImageJobResult(
                status="failed",
                error_code="SOURCE_IMAGE_MISSING",
                error_message="GPT Image requires source_image_bytes on the job payload.",
            )
        prompt = (payload.prompt or "").strip() or "Preserve the room; apply approved safety modifications."
        started = time.monotonic()
        image_bytes, error, retryable = self._edit(bytes(source), prompt)
        if not image_bytes:
            fal = FalKontextProvider()
            if fal.is_configured():
                return fal.generate_image(payload)
            return AIImageJobResult(status="failed", error_code="GPT_IMAGE_FAILED", error_message=error, retryable=retryable)

        elapsed = max(1, int(round(time.monotonic() - started)))
        now = datetime.now(timezone.utc)
        request = payload.render_request
        job_id = request.job_id if request else payload.ai_job_id
        return AIImageJobResult(
            status="completed",
            generated_image_bytes=image_bytes,
            generated_content_type="image/png",
            generation_time_seconds=elapsed,
            provider_job_id=job_id,
            render_accepted=RenderJobAccepted(
                job_id=job_id, status=RenderJobStatus.QUEUED, status_url=f"/gpu/v1/jobs/{job_id}", accepted_at=now
            ),
            render_callback=RenderJobCallback(
                job_id=job_id,
                status=RenderJobStatus.SUCCEEDED,
                completed_at=now,
                outputs=[
                    RenderOutputCandidate(
                        candidate_id="CAND-01",
                        image_bytes_b64=base64.b64encode(image_bytes).decode("ascii"),
                        content_type="image/png",
                        width_px=payload.width,
                        height_px=payload.height,
                        quality=QualityScores(room_preservation_score=0.9, placement_score=0.8, artifact_score=0.1),
                        review_required=True,
                    )
                ],
                provenance=RenderProvenance(
                    model_set_version=self.model_label(),
                    prompt_template_version=payload.workflow or "ROOM-PRESERVE",
                    seed=None,
                    gpu_type="AZURE_OPENAI" if self._azure() else "OPENAI",
                    provider="gpt_image",
                    is_stub=False,
                ),
            ),
        )


def _extract_fal_image(payload_json: dict) -> tuple[str | None, bytes | None, str | None]:
    """Return (url, bytes, content_type) from a fal run response."""
    import base64

    images = payload_json.get("images") or payload_json.get("image") or []
    if isinstance(images, dict):
        images = [images]
    if not images and payload_json.get("url"):
        images = [{"url": payload_json["url"]}]
    if not images:
        return None, None, None
    first = images[0] if isinstance(images[0], dict) else {"url": str(images[0])}
    url = first.get("url") or first.get("file_url")
    content_type = first.get("content_type") or "image/png"
    b64 = first.get("file_data") or first.get("data")
    if isinstance(b64, str) and b64:
        raw = b64
        if "," in raw and raw.startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            return url, base64.b64decode(raw), content_type
        except Exception:
            pass
    return (str(url) if url else None), None, content_type


def get_ai_provider(settings: dict | None = None) -> AIProvider:
    from app.core.config import settings as app_settings

    cfg = settings or {}
    # Env override wins when set (deploy-friendly).
    env_override = (app_settings.AI_RENDER_PROVIDER or "").strip().lower()
    provider_id = env_override or str(
        cfg.get("render_provider") or cfg.get("default_provider") or "local_stub"
    ).strip().lower()

    if provider_id in ("none", "off", "disabled"):
        return NotConfiguredProvider()
    if provider_id in ("local_stub", "stub", ""):
        return LocalStubProvider()
    if provider_id in ("fal_kontext", "fal", "flux-kontext", "flux_kontext"):
        fal = FalKontextProvider()
        # Spec: explicit fal selection without key → not configured (no silent stub).
        if not fal.is_configured():
            return NotConfiguredProvider()
        return fal
    if provider_id in ("gemini_image", "gemini", "nano_banana"):
        gem = GeminiImageProvider()
        if gem.is_configured():
            return gem
        fal = FalKontextProvider()
        return fal if fal.is_configured() else NotConfiguredProvider()
    if provider_id in ("gpt_image", "gpt-image", "openai", "azure_openai"):
        gpt = GptImageProvider()
        if gpt.is_configured():
            return gpt
        fal = FalKontextProvider()
        return fal if fal.is_configured() else NotConfiguredProvider()
    # Unknown provider ids — keep local stub so product never hard-blocks in misconfig.
    return LocalStubProvider()
