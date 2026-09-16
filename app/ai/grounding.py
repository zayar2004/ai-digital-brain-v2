"""
Grounding verification.

Checks that an AI answer does not introduce facts that are NOT in the
retrieved context. This protects against hallucination.

This module is deterministic (no AI needed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Patterns we consider "must be supported by context"
_CODE_RE = re.compile(r"\b[A-Z]{1,6}(?:[-_][A-Z0-9]+){1,8}\b")   # e.g. CT-P6-015
_ERROR_RE = re.compile(r"(?:error|err)\s*[:\-]?\s*(\d{1,4})", re.IGNORECASE)
_UNIT_RE = re.compile(r"\b[Pp]\s?(\d{1,3})\b")
_NUM_RE = re.compile(r"\b\d{2,}\b")


@dataclass
class GroundingReport:
    ok: bool
    problems: list[str]

    def to_dict(self) -> dict:
        return {"ok": self.ok, "problems": self.problems}


def check(answer: str, context: str) -> GroundingReport:
    """Return grounding report for the answer given context."""
    problems: list[str] = []
    if not answer:
        return GroundingReport(ok=True, problems=problems)

    a = answer
    c = context or ""

    # --- Machine codes (uppercase with separators) ---
    for code in set(_CODE_RE.findall(a)):
        # Skip common short words
        if len(code) < 4 or code.lower() in {"error", "admin", "www"}:
            continue
        if code not in c:
            problems.append(f"code not in context: {code}")

    # --- Error codes ---
    for e in set(_ERROR_RE.findall(a)):
        # Allow if the same number appears in context
        if e not in c:
            problems.append(f"error code not in context: {e}")

    # --- Units (P<number>) ---
    for u in set(_UNIT_RE.findall(a)):
        if f"P{u}" not in c and f"p{u}" not in c:
            problems.append(f"unit not in context: P{u}")

    # --- Large numbers ---
    for n in set(_NUM_RE.findall(a)):
        if n not in c:
            problems.append(f"number not in context: {n}")

    # Deduplicate while preserving order
    seen = set()
    problems = [p for p in problems if not (p in seen or seen.add(p))]

    return GroundingReport(ok=(len(problems) == 0), problems=problems)
