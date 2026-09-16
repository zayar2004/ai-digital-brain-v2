"""
Specialized Excel → Error Knowledge importer.

Recognizes the "Error Troubleshooting" sheet structure:
    No. | Error Message (English) | မြန်မာဘာသာပြန် |
    ဖြစ်နိုင်သောအကြောင်း/စစ်ဆေးရန် | ဖြေရှင်းနည်းအဆင့်များ | မှတ်ချက်
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook


@dataclass
class ErrorRow:
    row_number: int
    no: str = ""
    error_name_en: str = ""
    error_name_my: str = ""
    cause: str = ""
    solution: str = ""
    notes: str = ""
    error_code: str = ""
    title: str = ""
    content: str = ""


@dataclass
class ErrorSheet:
    name: str
    headers: list[str] = field(default_factory=list)
    rows: list[ErrorRow] = field(default_factory=list)


@dataclass
class ErrorIngestResult:
    source_type: str = "error_excel"
    original_filename: str = ""
    machine_name: str = ""
    sheets: list[ErrorSheet] = field(default_factory=list)
    candidates: list[ErrorRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------
# Header normalization — very permissive
# ----------------------------------------------------------------
def _norm_header(v) -> str:
    """Return a canonical key for a header cell."""
    if v is None:
        return ""
    s = str(v).strip().lower()
    # Collapse whitespace and remove punctuation noise
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" :;.,")

    # Direct dict match first
    if s in _DICT:
        return _DICT[s]

    # Fuzzy substring match
    for key, canon in _FUZZY:
        if key in s:
            return canon

    return s


# Exact aliases
_DICT = {
    "no": "no", "no.": "no", "number": "no", "နံပါတ်": "no",

    "error message": "error_name_en",
    "error message (english)": "error_name_en",
    "error message english": "error_name_en",
    "error name": "error_name_en",
    "error": "error_name_en",
    "english": "error_name_en",

    "မြန်မာဘာသာပြန်": "error_name_my",
    "myanmar": "error_name_my",
    "myanmar translation": "error_name_my",
    "မြန်မာ": "error_name_my",

    "cause": "cause",
    "possible cause": "cause",
    "check": "cause",

    "solution": "solution",
    "fix": "solution",
    "troubleshooting": "solution",

    "note": "notes",
    "notes": "notes",
    "remark": "notes",
    "remarks": "notes",
}

# Fuzzy substring aliases (checked in order)
_FUZZY = [
    # order matters — more specific first
    ("error message", "error_name_en"),
    ("error name", "error_name_en"),
    ("english", "error_name_en"),
    ("မြန်မာဘာသာပြန်", "error_name_my"),
    ("myanmar translation", "error_name_my"),
    ("myanmar", "error_name_my"),
    ("ဖြစ်နိုင်သောအကြောင်း", "cause"),
    ("possible cause", "cause"),
    ("cause", "cause"),
    ("check", "cause"),
    ("ဖြေရှင်းနည်း", "solution"),
    ("solution", "solution"),
    ("fix", "solution"),
    ("troubleshoot", "solution"),
    ("မှတ်ချက်", "notes"),
    ("remark", "notes"),
    ("note", "notes"),
    ("no.", "no"),
    ("no", "no"),
]


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _derive_error_code(error_name_en: str, no: str = "") -> str:
    """MSDA-1 style code from initials of error words."""
    if not error_name_en:
        return no or ""
    words = re.findall(r"[A-Za-z]{2,}", error_name_en)
    if not words:
        return no or ""
    initials = "".join(w[0].upper() for w in words[:5])
    return f"{initials}-{no}" if no else initials


def _make_title(row: ErrorRow) -> str:
    en = row.error_name_en or row.error_name_my or "Error"
    en_short = en[:80].rstrip()
    return f"#{row.no} {en_short}" if row.no else en_short


def _make_content(row: ErrorRow) -> str:
    """
    Content = Solution only (as requested by Admin).
    If solution is missing, fall back to cause.
    """
    if row.solution:
        return row.solution.strip()
    if row.cause:
        return row.cause.strip()
    return row.error_name_en or row.error_name_my or ""


def _looks_like_error_sheet(headers: list[str]) -> bool:
    hset = set(headers)
    score = 0
    for k in ("error_name_en", "error_name_my", "cause", "solution", "notes"):
        if k in hset:
            score += 1
    return score >= 2


# ----------------------------------------------------------------
# Main reader
# ----------------------------------------------------------------
import os

_MACHINE_STOPWORDS = {
    "error", "errors", "troubleshooting", "manual", "guide",
    "sheet", "data", "file", "document", "fix", "fixes",
    "updated", "final", "fixed", "rev", "revision", "version",
    "test", "copy", "backup", "old", "new",
    "mm", "en", "eng", "mya", "myanmar",
    "no", "note", "notes", "list", "table",
}


def derive_machine_name(path) -> str | None:
    """Derive a machine name from the filename (fallback if Admin didn't type one)."""
    import re as _re
    from pathlib import Path as _P
    p = _P(path)
    base = p.stem  # filename without extension
    # Replace separators with spaces
    s = _re.sub(r"[_\-.]+", " ", base).strip()
    # Remove trailing number "(19)" or " 1"
    s = _re.sub(r"\s*\(\d+\)\s*$", "", s)
    words = s.split()
    kept: list[str] = []
    for w in words:
        wl = w.lower()
        if wl in _MACHINE_STOPWORDS:
            break
        if _re.fullmatch(r"\d+", w):
            break
        kept.append(w)
        if len(kept) >= 4:
            break
    if not kept:
        return None
    name = " ".join(kept).strip()
    # Title-case except all-caps words
    name = " ".join(w if w.isupper() else w.capitalize() for w in name.split())
    return name if len(name) >= 3 else None


def read_error_excel(path: str | Path) -> ErrorIngestResult:
    result = ErrorIngestResult(original_filename=Path(path).name)

    wb = load_workbook(filename=str(path), data_only=True, read_only=True)

    for ws in wb.worksheets:
        if ws.max_row < 2:
            continue

        raw_headers = [
            _cell(ws.cell(row=1, column=c).value)
            for c in range(1, ws.max_column + 1)
        ]
        norm_headers = [_norm_header(h) for h in raw_headers]

        if not _looks_like_error_sheet(norm_headers):
            continue

        sheet = ErrorSheet(name=ws.title, headers=raw_headers)

        for r in range(2, ws.max_row + 1):
            row = ErrorRow(row_number=r)
            for c in range(1, ws.max_column + 1):
                key = norm_headers[c - 1]
                val = _cell(ws.cell(row=r, column=c).value)
                if key == "no": row.no = val
                elif key == "error_name_en": row.error_name_en = val
                elif key == "error_name_my": row.error_name_my = val
                elif key == "cause": row.cause = val
                elif key == "solution": row.solution = val
                elif key == "notes": row.notes = val

            if not (row.error_name_en or row.error_name_my or row.solution):
                continue

            row.error_code = _derive_error_code(row.error_name_en, row.no)
            row.title = _make_title(row)
            row.content = _make_content(row)
            sheet.rows.append(row)

        if sheet.rows:
            result.sheets.append(sheet)

    wb.close()

    for sheet in result.sheets:
        result.candidates.extend(sheet.rows)

    # Auto-detect machine name from the filename
    try:
        result.machine_name = derive_machine_name(path) or ""
    except Exception:
        result.machine_name = ""

    if not result.candidates:
        result.warnings.append(
            "Error troubleshooting sheet မတွေ့ပါ။ "
            "Header တွေမှာ Error Message, ဖြေရှင်းနည်း စတာတွေ ပါရမယ်။"
        )
    return result
