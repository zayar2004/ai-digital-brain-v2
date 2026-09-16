"""
High-level AI service used by routes and (later) Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai import prompts
from app.ai.provider import (
    AIResponse,
    chat,
    chat_json,
    is_configured,
    provider_name,
)
from app.ingestion import quick_teach


@dataclass
class ExtractionOutcome:
    ok: bool
    fields: dict
    source: str  # "ai" | "rules" | "none"
    error: str | None = None
    ai_response: AIResponse | None = None


def quick_teach_extract(raw_text: str, *, machine_hint: str | None = None) -> ExtractionOutcome:
    """
    Extract structured fields from a raw text.

    Priority:
      1) If AI is configured → try AI (JSON)
      2) Fallback to rule-based extractor
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return ExtractionOutcome(ok=False, fields={}, source="none", error="empty text")

    if is_configured():
        parsed, resp = chat_json(
            prompts.build_quick_teach_messages(raw_text),
            temperature=0.1, max_tokens=400,
        )
        if parsed and isinstance(parsed, dict):
            # Fill gaps with rule-based extractor (never trust AI alone)
            rules = quick_teach.extract(raw_text, known_machine_hint=machine_hint)
            merged = _merge_ai_rules(parsed, rules)
            return ExtractionOutcome(ok=True, fields=merged, source="ai", ai_response=resp)

    # Fallback
    rules = quick_teach.extract(raw_text, known_machine_hint=machine_hint)
    return ExtractionOutcome(
        ok=True,
        fields={
            "machine_name": rules.machine_name,
            "model": rules.model,
            "unit": rules.unit,
            "error_code": rules.error_code,
            "problem": rules.problem,
            "finding": rules.finding,
            "cause": rules.cause,
            "action_taken": rules.action_taken,
            "result": rules.result,
            "confidence": rules.confidence,
        },
        source="rules",
    )


def _merge_ai_rules(ai: dict, rules) -> dict:
    """AI values are used only when present; otherwise rule-based."""
    def pick(key: str, fallback):
        v = ai.get(key)
        if v is None or (isinstance(v, str) and not v.strip()):
            return fallback
        return v

    conf = ai.get("confidence") or {}
    if not isinstance(conf, dict):
        conf = {}

    return {
        "machine_name": pick("machine_name", rules.machine_name),
        "model": pick("model", rules.model),
        "unit": pick("unit", rules.unit),
        "error_code": pick("error_code", rules.error_code),
        "problem": pick("problem", rules.problem),
        "finding": pick("finding", rules.finding),
        "cause": pick("cause", rules.cause),
        "action_taken": pick("action_taken", rules.action_taken),
        "result": pick("result", rules.result),
        "confidence": {**rules.confidence, **conf},
    }


def status() -> dict:
    return {
        "configured": is_configured(),
        "provider": provider_name(),
    }
