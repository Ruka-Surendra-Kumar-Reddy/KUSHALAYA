"""Azure OpenAI chat completions for Workforce Copilot."""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Used to list deployments; chat may use a different preview version from settings.
DEPLOYMENTS_API_VERSION = "2024-06-01"


def is_configured() -> bool:
    return bool(
        settings.AZURE_OPENAI_ENDPOINT.strip()
        and settings.AZURE_OPENAI_API_KEY.strip()
        and settings.AZURE_OPENAI_DEPLOYMENT.strip()
    )


def _base_endpoint() -> str:
    return settings.AZURE_OPENAI_ENDPOINT.strip().rstrip("/")


def _api_headers() -> dict[str, str]:
    return {
        "api-key": settings.AZURE_OPENAI_API_KEY.strip(),
        "Content-Type": "application/json",
    }


def list_deployments() -> tuple[list[str], str | None]:
    """Return deployment ids from Azure, or ([], error_message)."""
    if not settings.AZURE_OPENAI_ENDPOINT.strip() or not settings.AZURE_OPENAI_API_KEY.strip():
        return [], "Endpoint and API key are required"

    url = (
        f"{_base_endpoint()}/openai/deployments"
        f"?api-version={DEPLOYMENTS_API_VERSION}"
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=_api_headers())
            if response.status_code >= 400:
                return [], f"HTTP {response.status_code}: {response.text[:300]}"
            body = response.json()
    except Exception as exc:
        return [], str(exc)

    names: list[str] = []
    for item in body.get("data") or []:
        dep_id = item.get("id") or item.get("name")
        if dep_id:
            names.append(str(dep_id))
    return names, None


def chat_completion(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    if not is_configured():
        raise RuntimeError("Azure OpenAI is not configured")

    deployment = settings.AZURE_OPENAI_DEPLOYMENT.strip()
    api_version = settings.AZURE_OPENAI_API_VERSION
    url = (
        f"{_base_endpoint()}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
    )

    body = {
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.AZURE_OPENAI_TEMPERATURE,
        "max_tokens": max_tokens if max_tokens is not None else settings.AZURE_OPENAI_MAX_TOKENS,
    }

    with httpx.Client(timeout=90.0) as client:
        response = client.post(url, headers=_api_headers(), json=body)
        if response.status_code >= 400:
            logger.warning(
                "Azure OpenAI error %s deployment=%s url=%s body=%s",
                response.status_code,
                deployment,
                url.split("?")[0],
                response.text[:500],
            )
            if response.status_code == 404:
                known, list_err = list_deployments()
                hint = (
                    f"Deployment '{deployment}' was not found on this Azure OpenAI resource. "
                    "In Azure Portal → your OpenAI resource → Model deployments, "
                    "copy the exact Deployment name into AZURE_OPENAI_DEPLOYMENT "
                    "(it is often not the same as the model name, e.g. gpt-4o)."
                )
                if known:
                    hint += f" Deployments found on this endpoint: {', '.join(known)}."
                elif list_err:
                    hint += f" Could not list deployments: {list_err}"
                raise RuntimeError(hint) from None
            response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Azure OpenAI returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("Azure OpenAI returned empty content")
    return content.strip()
