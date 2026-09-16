"""
Natural language → Task fields.

Supports Myanmar phrases like:
    "A3 Crocodile Tycoon ကို တနင်္လာနေ့တိုင်း မနက် 9 နာရီ စစ်မယ်"

Rule-based. Optionally enhanced by AI (PART 16 service).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

WEEKDAYS_MY = {
    "တနင်္လာ": 0, "တနင်္လာနေ့": 0, "monday": 0,
    "အင်္ဂါ": 1, "အင်္ဂါနေ့": 1, "tuesday": 1,
    "ဗုဒ္ဓဟူး": 2, "ဗုဒ္ဓဟူးနေ့": 2, "wednesday": 2,
    "ကြာသပတေး": 3, "ကြာသပတေးနေ့": 3, "thursday": 3,
    "သောကြာ": 4, "သောကြာနေ့": 4, "friday": 4,
    "စနေ": 5, "စနေနေ့": 5, "saturday": 5,
    "တနင်္ဂနွေ": 6, "တနင်္ဂနွေနေ့": 6, "sunday": 6,
}

FREQ_PATTERNS = [
    ("DAILY",   ["နေ့စဉ်", "နေ့တိုင်း", "every day", "daily"]),
    ("WEEKLY",  ["အပတ်စဉ်", "အပတ်တိုင်း", "weekly", "every week"]),
    ("MONTHLY", ["လစဉ်", "လတိုင်း", "monthly", "every month"]),
    ("YEARLY",  ["နှစ်စဉ်", "နှစ်တိုင်း", "yearly", "every year"]),
]


@dataclass
class ParsedTask:
    title: str = ""
    frequency: str = "DAILY"
    weekday: int | None = None
    day_of_month: int | None = None
    month: int | None = None
    specific_date: str | None = None
    task_time: str | None = None
    priority: str = "NORMAL"
    machine_hint: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)


def parse(text: str) -> ParsedTask:
    t = (text or "").strip()
    out = ParsedTask(title=t[:200])

    if not t:
        return out

    # Frequency
    for freq, patterns in FREQ_PATTERNS:
        for p in patterns:
            if p in t:
                out.frequency = freq
                out.confidence["frequency"] = 0.9
                break
        if out.frequency == freq and "frequency" in out.confidence:
            break

    # Weekday
    for name, wd in WEEKDAYS_MY.items():
        if name in t:
            out.weekday = wd
            out.frequency = "WEEKLY"
            out.confidence["weekday"] = 0.9
            break

    # Day-of-month: "15 ရက်"
    m = re.search(r"(\d{1,2})\s*ရက်", t)
    if m:
        try:
            d = int(m.group(1))
            if 1 <= d <= 31:
                out.day_of_month = d
                if out.frequency == "DAILY":
                    out.frequency = "MONTHLY"
                out.confidence["day_of_month"] = 0.8
        except ValueError:
            pass

    # Specific date: "2026-09-15" or "15/9/2026"
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        out.specific_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        out.frequency = "ONE_TIME"
        out.confidence["specific_date"] = 0.9
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if m:
            out.specific_date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
            out.frequency = "ONE_TIME"
            out.confidence["specific_date"] = 0.85

    # Time: "9 နာရီ", "09:00", "9:30", "မနက် 9 နာရီ"
    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60:
            out.task_time = f"{hh:02d}:{mm:02d}"
            out.confidence["task_time"] = 0.95
    else:
        m = re.search(r"(\d{1,2})\s*နာရီ(?:\s*(\d{1,2})\s*မိနစ်)?", t)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2)) if m.group(2) else 0
            # Handle မနက် / ညနေ
            if "ညနေ" in t and hh < 12:
                hh += 12
            if "ည" in t and hh < 12:
                hh += 12
            if 0 <= hh < 24 and 0 <= mm < 60:
                out.task_time = f"{hh:02d}:{mm:02d}"
                out.confidence["task_time"] = 0.85

    # Priority
    if any(k in t for k in ["အရေးကြီး", "urgent", "အမြန်"]):
        out.priority = "HIGH"
        out.confidence["priority"] = 0.7

    # Machine hint: text before "ကို"
    m = re.search(r"([A-Za-z][\w\s\-]{1,40}?)\s*(?:ကို|machine|စက်)", t)
    if m:
        out.machine_hint = m.group(1).strip()
        out.confidence["machine_hint"] = 0.6

    return out


def weekday_name(wd: int | None) -> str:
    names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    if wd is None or not (0 <= wd < 7):
        return "?"
    return names[wd]
