"""
Provider-independent AI service.

Supported providers (OpenAI-compatible / Gemini):
    openrouter — OpenRouter.ai
    openai     — OpenAI
    deepseek   — DeepSeek direct
    gemini     — Google Gemini
    none       — disabled (returns deterministic fallback)

Never hardcode a provider.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Config

log = logging.getLogger(__name__)


@dataclass
class AIResponse:
    ok: bool
    text: str = ""
    error: str | None = None
    provider: str = ""
    model: str = ""
    raw: dict | None = None
    usage: dict | None = None


def is_configured() -> bool:
    """Return True if a usable AI provider is configured."""
    if not Config.AI_ENABLED:
        return False
    if Config.AI_PROVIDER.lower() in ("", "none"):
        return False
    return bool(Config.AI_API_KEY and Config.AI_BASE_URL and Config.AI_MODEL)


def provider_name() -> str:
    return (Config.AI_PROVIDER or "none").lower()


# ----------------------------------------------------------------
# OpenAI-compatible chat
# ----------------------------------------------------------------
def _post_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    json_mode: bool = False,
    extra_headers: dict | None = None,
) -> AIResponse:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    try:
        r = httpx.post(url, headers=headers, json=body,
                       timeout=Config.AI_TIMEOUT)
        if r.status_code != 200:
            return AIResponse(
                ok=False,
                error=f"HTTP {r.status_code}: {r.text[:300]}",
                provider=provider_name(), model=model,
            )
        data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return AIResponse(
            ok=True, text=(text or "").strip(),
            provider=provider_name(), model=model,
            raw=data, usage=data.get("usage"),
        )
    except httpx.TimeoutException:
        return AIResponse(ok=False, error="Timeout", provider=provider_name(), model=model)
    except Exception as e:
        return AIResponse(ok=False, error=str(e), provider=provider_name(), model=model)


# ----------------------------------------------------------------
# Gemini
# ----------------------------------------------------------------
def _post_gemini(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    json_mode: bool = False,
) -> AIResponse:
    # Merge system into first user message (Gemini has separate systemInstruction but keep simple)
    system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
    user_parts = [m["content"] for m in messages if m.get("role") != "system"]
    user_text = "\n\n".join(user_parts)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    try:
        r = httpx.post(url, json=body, timeout=Config.AI_TIMEOUT)
        if r.status_code != 200:
            return AIResponse(ok=False, error=f"HTTP {r.status_code}: {r.text[:300]}",
                              provider="gemini", model=model)
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return AIResponse(ok=False, error="No candidates", provider="gemini", model=model)
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return AIResponse(ok=True, text=text.strip(), provider="gemini", model=model, raw=data)
    except httpx.TimeoutException:
        return AIResponse(ok=False, error="Timeout", provider="gemini", model=model)
    except Exception as e:
        return AIResponse(ok=False, error=str(e), provider="gemini", model=model)


# ----------------------------------------------------------------
# Public
# ----------------------------------------------------------------
def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    json_mode: bool = False,
) -> AIResponse:
    """Send a chat request to the configured provider."""
    if not is_configured():
        return AIResponse(ok=False, error="AI is not configured.", provider="none")

    p = provider_name()

    if p == "gemini":
        return _post_gemini(
            api_key=Config.AI_API_KEY,
            model=Config.AI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    # OpenAI-compatible family
    headers: dict | None = None
    if p == "openrouter":
        headers = {
            "HTTP-Referer": "https://github.com/ai-digital-brain",
            "X-Title": "AI Digital Brain",
        }
    return _post_openai_compatible(
        base_url=Config.AI_BASE_URL,
        api_key=Config.AI_API_KEY,
        model=Config.AI_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
        extra_headers=headers,
    )


def chat_json(
    messages: list[dict],
    *,
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> tuple[dict | None, AIResponse]:
    """Ask for JSON and parse safely. Returns (parsed_or_None, response)."""
    resp = chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    if not resp.ok or not resp.text:
        return None, resp
    try:
        return json.loads(resp.text), resp
    except json.JSONDecodeError:
        # Try to salvage JSON between first { and last }
        s = resp.text
        a = s.find("{")
        b = s.rfind("}")
        if a != -1 and b != -1 and b > a:
            try:
                return json.loads(s[a:b + 1]), resp
            except json.JSONDecodeError:
                pass
        return None, resp
