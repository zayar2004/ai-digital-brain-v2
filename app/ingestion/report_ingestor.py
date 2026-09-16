"""
Parse a pasted work report into structured metrics.

Example:
    7/9/2026 Update
    Machine 144
    Daily Key 236
    Spare Key 236
    Chair Shot 103
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ParsedReport:
    report_date: date | None = None
    title: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    notes: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)


_DATE_RE_1 = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_DATE_RE_2 = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")

# "Key: Value" or "Key Value"
_METRIC_LINE_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z\u1000-\u109F][\w\s\u1000-\u109F\-/]{1,60}?)\s*[:\-]?\s*(?P<val>-?\d+(?:\.\d+)?)\s*$"
)


def parse(text: str) -> ParsedReport:
    out = ParsedReport()
    if not text:
        return out

    lines = [ln.rstrip() for ln in text.splitlines()]
    leftover_notes: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        # Date?
        m = _DATE_RE_1.search(s)
        if m and out.report_date is None:
            try:
                d = int(m.group(1)); mo = int(m.group(2)); y = int(m.group(3))
                out.report_date = date(y, mo, d)
                out.confidence["report_date"] = 0.9
                continue
            except ValueError:
                pass
        else:
            m = _DATE_RE_2.search(s)
            if m and out.report_date is None:
                try:
                    y = int(m.group(1)); mo = int(m.group(2)); d = int(m.group(3))
                    out.report_date = date(y, mo, d)
                    out.confidence["report_date"] = 0.9
                    continue
                except ValueError:
                    pass

        # Title?
        if out.title is None and ("update" in s.lower() or "report" in s.lower()):
            out.title = s
            out.confidence["title"] = 0.7
            continue

        # Metric?
        m = _METRIC_LINE_RE.match(s)
        if m:
            try:
                key = m.group("key").strip().replace("  ", " ")
                val = float(m.group("val"))
                out.metrics[key] = val
                out.confidence["metrics"] = 0.8
                continue
            except Exception:
                pass

        leftover_notes.append(s)

    if leftover_notes:
        out.notes = "\n".join(leftover_notes)

    return out
