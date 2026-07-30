"""Thin client for the HKUST-hosted `qwen-vl` OpenAI-compatible chat/vision
endpoint, used by `backend/dedup.py` to merge furniture detected across
multiple photos of the same job and to infer per-photo room labels
(IMPLEMENTATION_ROADMAP.md multi-image build).

This is the first external network API call anywhere in this codebase --
everything else (Grounding DINO/SAM2/Depth Anything V2) runs local model weights.
Uses `httpx` (already a dependency, via `requirements.txt`) rather than
adding an `openai` SDK dependency for one endpoint.
"""

from __future__ import annotations

import base64
import json
import os

import httpx

DEFAULT_MODEL = "qwen-vl"
DEFAULT_TIMEOUT_S = 60.0


class ReasoningClientError(RuntimeError):
    """Raised when the HKUST endpoint is unreachable, errors, or doesn't
    return the expected JSON payload. Callers must catch this and degrade
    gracefully -- the capture this reasoning pass follows has already been
    persisted and must not be rolled back because of it."""


def _config() -> tuple[str, str, str]:
    base_url = os.environ.get("HKUST_VLM_BASE_URL")
    api_key = os.environ.get("HKUST_VLM_API_KEY")
    model = os.environ.get("HKUST_VLM_MODEL", DEFAULT_MODEL)
    if not base_url or not api_key:
        raise ReasoningClientError(
            "HKUST_VLM_BASE_URL / HKUST_VLM_API_KEY are not configured"
        )
    return base_url, api_key, model


def _image_content_block(png_bytes: bytes) -> dict:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{encoded}"},
    }


def ask_vision_json(
    *,
    system_prompt: str,
    user_text: str,
    images: list[bytes],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict:
    """Sends one chat-completion request: `user_text` plus each of `images`
    (raw PNG bytes) as vision content blocks. Expects and parses a JSON
    object back from the model's message content.

    Raises `ReasoningClientError` on any transport, HTTP, or parse failure.
    """
    base_url, api_key, model = _config()

    content: list[dict] = [{"type": "text", "text": user_text}]
    content.extend(_image_content_block(png) for png in images)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            # This is an Azure API Management gateway in front of an
            # Azure-OpenAI-style backend: plain `Authorization: Bearer` 401s
            # here (APIM wants its own subscription-key header), so the key
            # goes in `api-key` instead.
            headers={"api-key": api_key},
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        message_content = body["choices"][0]["message"]["content"]
        return json.loads(message_content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ReasoningClientError(f"HKUST reasoning request failed: {exc}") from exc
