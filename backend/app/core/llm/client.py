"""Gemini LLM client: thin, injectable wrapper around the Gemini REST API.

This module — together with its callers in api/recommendations.py — is the
ONLY place in the entire codebase that touches an LLM. Every earlier stage
(ingestion … insight generation) is deterministic code; the ledger in
api/telemetry.py documents that split.

Design for testability: `call_llm(prompt, client=None)` accepts an injected
`client` object exposing `generate_content(prompt: str) -> response` with
`response.text` and `response.usage_metadata` attributes (the google-genai
SDK's shape). Tests pass a stub; production builds a real transport over
httpx against the Gemini REST endpoint, so no extra SDK is required.

Cost is estimated from settings' published per-Mtok rates:
    cost_usd = prompt_tokens/1e6 * INPUT_RATE + completion_tokens/1e6 * OUTPUT_RATE
"""

import time

import httpx

from app.config import settings


class GeminiRestClient:
    """Minimal Gemini REST transport (v1beta generateContent) via httpx.

    Matches the injectable-client shape used by call_llm:
        generate_content(prompt) -> SimpleNamespace(text, usage_metadata)
    """

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 60.0):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout

    def generate_content(self, prompt: str):
        """Call Gemini; return an SDK-shaped response (text + usage metadata)."""
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set — the LLM recommendation layer "
                "requires a Gemini API key in backend/.env."
            )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        response = httpx.post(
            url,
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()

        parts = (body.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = body.get("usageMetadata") or {}
        return _RestResponse(
            text=text,
            usage_metadata=_RestUsage(
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
            ),
        )


class _RestResponse:
    def __init__(self, text: str, usage_metadata):
        self.text = text
        self.usage_metadata = usage_metadata


class _RestUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = completion_tokens


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Deterministic cost estimate from the configured published rates."""
    return round(
        prompt_tokens / 1_000_000 * settings.GEMINI_INPUT_USD_PER_MTOK
        + completion_tokens / 1_000_000 * settings.GEMINI_OUTPUT_USD_PER_MTOK,
        6,
    )


def call_llm(prompt: str, client=None) -> dict:
    """Call the Gemini model with a prompt; return text + usage + cost.

    Args:
        prompt: the fully-built prompt string (from prompt_templates —
            structured package fields only, never raw data).
        client: optional injected transport (must expose
            generate_content(prompt) -> obj with .text and .usage_metadata.
            Defaults to a real GeminiRestClient.

    Returns {
        "text": str,
        "prompt_tokens": int,
        "completion_tokens": int,
        "latency_ms": int,
        "cost_usd": float,
        "model": str,
    }
    """
    transport = client or GeminiRestClient()
    started = time.perf_counter()
    response = transport.generate_content(prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    text = str(getattr(response, "text", "") or "")

    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    return {
        "text": text.strip(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "cost_usd": estimate_cost_usd(prompt_tokens, completion_tokens),
        "model": getattr(transport, "model", settings.GEMINI_MODEL),
    }
