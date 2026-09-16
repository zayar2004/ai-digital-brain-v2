"""
Quick Teach: raw text → structured knowledge.

Rule-based extraction that handles common Myanmar workplace phrases.
AI is optional (used via app.ai.service when available).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    machine_name: str | None = None
    model: str | None = None
    unit: str | None = None
    error_code: str | None = None
    problem: str | None = None
    finding: str | None = None
    cause: str | None = None
    action_taken: str | None = None
    result: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "machine_name": self.machine_name,
            "model": self.model,
            "unit": self.unit,
            "error_code": self.error_code,
            "problem": self.problem,
            "finding": self.finding,
            "cause": self.cause,
            "action_taken": self.action_taken,
            "result": self.result,
            "confidence": self.confidence,
        }


# ----------------------------------------------------------------
# Patterns
# ----------------------------------------------------------------
_UNIT_RE = re.compile(r"\b[Pp]\s?(\d{1,3})\b")
_ERROR_RE = re.compile(
    r"(?<![A-Za-z])(?:error|err|er)\s*[:\-_]?\s*([A-Z]?\d{1,4})",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"\b([A-Z])\s*[_\-\s]?(\d{1,4})\b")

# Myanmar + English keywords for clause classification
PROBLEM_KEYS = [
    "ပေါ်နေ", "ပေါ်လာ", "ဖြစ်နေ", "မတက်", "မလုပ်", "ပျက်", "error", "problem",
]
FINDING_KEYS = [
    "စစ်ကြည့်", "တွေ့ရှိ", "တွေ့ရ", "တွေ့",
    "ရှိသည်", "ရှိနေ", "ညှပ်", "ပိတ်နေ", "ကုန်နေ", "ချို့ယွင်း",
    "finding", "found",
]
ACTION_KEYS = [
    "ထုတ်ပေး", "ပြုပြင်", "ပြန်", "ဖြည့်", "လဲ", "ပြောင်း",
    "လုပ်လိုက်", "ပြင်လိုက်", "လုပ်ဆောင်", "ထုတ်", "ပေး",
    "action", "fixed", "replaced",
]
RESULT_KEYS = [
    "အဆင်ပြေ", "ပြီးသွား", "ပြီးပါပြီ", "ပြေသွား", "အလုပ်လုပ်",
    "ပုံမှန်", "ok", "အိုကေ", "result",
]
CAUSE_KEYS = [
    "ကြောင့်", "အကြောင်း", "cause",
]


def _split_sentences(text: str) -> list[str]:
    """Split into clauses — Myanmar + English punctuation + connectors."""
    if not text:
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"[။\.!\?]+", t)
    clauses: list[str] = []
    # Also split on Myanmar connectors "၍" and "ရာ"
    for part in parts:
        part = part.strip()
        if not part:
            continue
        sub = re.split(
            r"\s*၍\s*"              # and
            r"|\s+ရာ\s+"            # when
            r"|\s+တော့\s+"          # then
            r"|\s+သော်\s+"          # if
            r"|တာ\s+(?=[\u1000-\u109F])"   # "တာ" + space + Myanmar char
            r"|\s+အခါ\s+"           # time
            r"|ပြီး(?=[\u1000-\u109F])"     # "ပြီး" + Myanmar char
            r"|သွားပြီ"               # "finished"
            ,
            part,
        )
        for s in sub:
            s = s.strip().rstrip(",;:")
            if len(s) >= 2:
                clauses.append(s)
    return clauses


def _normalize_error_code(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().upper()
    m = re.match(r"^([A-Z])[_\-\s]?(\d{1,4})$", s)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    if s.isdigit():
        return s
    return s


def _contains_any(text: str, keys: list[str]) -> str | None:
    """Return the first matching key, or None."""
    t = text.lower()
    for k in keys:
        if k.lower() in t:
            return k
    return None


def extract(text: str, *, known_machine_hint: str | None = None) -> ExtractionResult:
    result = ExtractionResult()
    if not text:
        return result

    t = text.strip()

    # Unit
    m = _UNIT_RE.search(t)
    if m:
        result.unit = f"P{m.group(1)}"
        result.confidence["unit"] = 0.9

    # Error code
    m = _ERROR_RE.search(t)
    if m:
        result.error_code = _normalize_error_code(m.group(1))
        result.confidence["error_code"] = 0.95
    else:
        m = _CODE_RE.search(t)
        if m:
            cand = f"{m.group(1)}_{m.group(2)}"
            if not (result.unit and cand == result.unit):
                if m.group(1).upper() != "P":
                    result.error_code = cand
                    result.confidence["error_code"] = 0.75

    # Machine name
    if known_machine_hint:
        result.machine_name = known_machine_hint
        result.confidence["machine_name"] = 0.95
    else:
        for pat in [
            r"^(.+?)\s+[A-Z]\s*[_\-\s]\d{1,4}\b",
            r"^(.+?)\s+[Pp]\s?\d{1,3}\b",
            r"^(.+?)\s+[Ee]rr?(?:or)?\s*[:\-_]?\s*\d+",
            r"^(.+?)\s+ပေါ်နေ",
        ]:
            m = re.match(pat, t)
            if m:
                cand = m.group(1).strip().rstrip(",;:-")
                if 1 < len(cand) < 80:
                    result.machine_name = cand
                    result.confidence["machine_name"] = 0.8
                    break

    # Clause classification
    clauses = _split_sentences(t)
    if not clauses:
        return result

    # Problem = first clause
    result.problem = clauses[0]
    result.confidence["problem"] = 0.7

    # Finding = first non-problem clause with FINDING_KEYS
    for c in clauses[1:]:
        if _contains_any(c, FINDING_KEYS):
            result.finding = c
            result.confidence["finding"] = 0.8
            break

    # Action
    for c in clauses[1:]:
        if c == result.finding:
            continue
        if _contains_any(c, ACTION_KEYS):
            result.action_taken = c
            result.confidence["action_taken"] = 0.8
            break

    # Result
    for c in clauses[1:]:
        if c in (result.finding, result.action_taken):
            continue
        if _contains_any(c, RESULT_KEYS):
            result.result = c
            result.confidence["result"] = 0.85
            break

    # Cause
    for c in clauses[1:]:
        if c in (result.finding, result.action_taken, result.result):
            continue
        if _contains_any(c, CAUSE_KEYS):
            result.cause = c
            result.confidence["cause"] = 0.7
            break

    return result


# ================================================================
# Override: extract() — post-process to extract Result from Action
# ================================================================
_original_extract = extract


def extract(text: str, *, known_machine_hint: str | None = None) -> ExtractionResult:
    """Wrap original extract to additionally split Result out of Action."""
    r = _original_extract(text, known_machine_hint=known_machine_hint)

    # If Action contains Result keywords, split it
    if r.action_taken and not r.result:
        for rk in RESULT_KEYS:
            if rk.lower() in r.action_taken.lower():
                # Split at Result keyword
                idx = r.action_taken.lower().find(rk.lower())
                if idx > 0:
                    action_part = r.action_taken[:idx].strip()
                    result_part = r.action_taken[idx:].strip()
                    if action_part:
                        r.action_taken = action_part
                    if result_part:
                        r.result = result_part
                    break

    return r
