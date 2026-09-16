"""
Unified document ingestion pipeline.

Flow:
    UPLOAD (PDF/DOCX/Excel/TXT)
      ↓
    DETECT TYPE
      ↓
    EXTRACT TEXT
      ↓
    SPLIT INTO CANDIDATES
      ↓
    RULE-BASED EXTRACTION (machine, unit, error)
      ↓
    PREVIEW  →  Admin approve

Never auto-creates APPROVED knowledge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.docx_reader import read_docx
from app.ingestion.excel_reader import read_excel
from app.ingestion import error_excel_ingestor as EEI
from app.ingestion.pdf_reader import read_pdf
from app.ingestion.quick_teach import extract as quick_extract


@dataclass
class IngestedCandidate:
    title: str
    content: str
    source_type: str        # pdf | docx | excel | text | excel_error
    source_file: str
    source_page: str | None = None
    source_sheet: str | None = None
    source_row: int | None = None

    machine_name: str | None = None
    unit: str | None = None
    error_code: str | None = None
    confidence: float = 0.5

    # Error-specific extras (populated by error_excel_ingestor path)
    no: str = ""
    error_name_en: str = ""
    error_name_my: str = ""
    cause: str = ""
    solution: str = ""
    notes: str = ""
    machine_hint: str = ""


@dataclass
class IngestedDocument:
    source_type: str
    original_filename: str
    pages_or_sheets: int = 0
    candidates: list[IngestedCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------
# Text splitter
# ----------------------------------------------------------------
_MIN_CHUNK = 15
_MAX_CHUNK = 2000
_HEADING_RE = re.compile(r"^\s*(?:#{1,3}\s+|\d+\.\s+|[-•]\s+)?(.{3,120})$")
_ERROR_LINE_RE = re.compile(r"(?:error|err|er)\s*[:\-]?\s*(\d{1,4})", re.IGNORECASE)


def _split_candidates(text: str, source_type: str, source_file: str,
                      *, page: str | None = None, sheet: str | None = None) -> list[IngestedCandidate]:
    """Split a big text into candidate knowledge chunks."""
    out: list[IngestedCandidate] = []

    # Prefer paragraph splitting on blank lines
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if not blocks:
        blocks = [text.strip()] if text.strip() else []

    for block in blocks:
        # If a block is too big, split on lines
        if len(block) > _MAX_CHUNK:
            sub = [ln.strip() for ln in block.splitlines() if ln.strip()]
            chunks = []
            buf = ""
            for ln in sub:
                if len(buf) + len(ln) + 1 > _MAX_CHUNK:
                    if buf:
                        chunks.append(buf)
                    buf = ln
                else:
                    buf = (buf + "\n" + ln).strip()
            if buf:
                chunks.append(buf)
            parts = chunks
        else:
            parts = [block]

        for part in parts:
            if len(part) < _MIN_CHUNK:
                continue
            cand = IngestedCandidate(
                title=_auto_title(part),
                content=part,
                source_type=source_type,
                source_file=source_file,
                source_page=page,
                source_sheet=sheet,
            )
            # Rule-based field extraction
            ext = quick_extract(part)
            cand.machine_name = ext.machine_name
            cand.unit = ext.unit
            cand.error_code = ext.error_code
            if ext.confidence:
                cand.confidence = round(sum(ext.confidence.values()) / len(ext.confidence), 2)
            out.append(cand)
    return out


def _auto_title(block: str) -> str:
    first = block.splitlines()[0].strip()
    if len(first) > 100:
        first = first[:100].rstrip() + "…"
    if not first:
        first = block[:60].rstrip() + "…"
    return first


# ----------------------------------------------------------------
# Main entry
# ----------------------------------------------------------------
def ingest_document(path: str, original_filename: str) -> IngestedDocument:
    """Detect type from filename, extract, and return candidates."""
    suffix = Path(original_filename).suffix.lower()

    if suffix in (".pdf",):
        return _ingest_pdf(path, original_filename)
    if suffix in (".docx", ".doc"):
        return _ingest_docx(path, original_filename)
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return _ingest_excel(path, original_filename)
    if suffix in (".txt", ".md"):
        return _ingest_text(path, original_filename)

    raise ValueError(f"Unsupported file type: {suffix}")


def _ingest_pdf(path: str, original_filename: str) -> IngestedDocument:
    doc = read_pdf(path)
    out = IngestedDocument(
        source_type="pdf",
        original_filename=original_filename,
        pages_or_sheets=doc.page_count,
    )
    for p in doc.pages:
        cands = _split_candidates(p.text, "pdf", original_filename, page=str(p.page_number))
        out.candidates.extend(cands)
    if not out.candidates:
        out.warnings.append("PDF ထဲမှာ စာသား မတွေ့ပါ။ (Scan ဖြစ်နိုင်တယ် — OCR လိုတယ်)")
    return out


def _ingest_docx(path: str, original_filename: str) -> IngestedDocument:
    doc = read_docx(path)
    out = IngestedDocument(
        source_type="docx",
        original_filename=original_filename,
        pages_or_sheets=len(doc.blocks),
    )
    for b in doc.blocks:
        if b.kind == "paragraph":
            cands = _split_candidates(b.text, "docx", original_filename)
        else:
            cands = _split_candidates(b.text, "docx", original_filename, sheet="table")
        out.candidates.extend(cands)
    if not out.candidates:
        out.warnings.append("DOCX ထဲမှာ စာသား မတွေ့ပါ။")
    return out


def _ingest_excel(path: str, original_filename: str) -> IngestedDocument:
    """
    Smart Excel ingest:
      1. Try Error Troubleshooting structure (error_excel_ingestor)
      2. If found → produce rich candidates (Machine Name auto, Error Code auto, Solution as Content)
      3. Otherwise → fall back to generic row-based extraction
    """
    # ---- Attempt specialized error-ingest first ----
    try:
        err = EEI.read_error_excel(path)
    except Exception:
        err = None

    if err and err.candidates:
        out = IngestedDocument(
            source_type="excel_error",
            original_filename=original_filename,
            pages_or_sheets=len(err.sheets),
        )
        # Use filename-derived machine name (auto)
        machine_hint = err.machine_name or ""

        for ec in err.candidates:
            cand = IngestedCandidate(
                title=ec.title or ec.error_name_en or "Error",
                content=ec.content or ec.solution or "",
                source_type="excel",
                source_file=original_filename,
                source_sheet="Troubleshooting",
                source_row=ec.row_number,
                machine_name=machine_hint,
                unit=None,
                error_code=ec.error_code,
                confidence=0.85,
            )
            # Attach extra fields as attributes the template can read
            cand.no = ec.no
            cand.error_name_en = ec.error_name_en
            cand.error_name_my = ec.error_name_my
            cand.cause = ec.cause
            cand.solution = ec.solution
            cand.notes = ec.notes
            cand.machine_hint = machine_hint
            out.candidates.append(cand)

        if machine_hint:
            out.warnings.append(
                f"🤖 Machine Name auto-detect: {machine_hint}"
            )
        return out

    # ---- Generic fallback ----
    sheets = read_excel(path)
    out = IngestedDocument(
        source_type="excel",
        original_filename=original_filename,
        pages_or_sheets=len(sheets),
    )

    for s in sheets:
        for row in s.rows:
            if s.is_generic:
                text = row.generic_text
            else:
                text = _row_to_text(row.values)

            text = (text or "").strip()
            if len(text) < _MIN_CHUNK:
                continue

            cands = _split_candidates(
                text, "excel", original_filename, sheet=s.name,
            )
            for c in cands:
                c.source_row = row.row_number
            out.candidates.extend(cands)

    if not out.candidates:
        out.warnings.append("Excel ထဲမှာ စာသား မတွေ့ပါ။")
    return out


def _ingest_text(path: str, original_filename: str) -> IngestedDocument:
    out = IngestedDocument(
        source_type="text",
        original_filename=original_filename,
        pages_or_sheets=1,
    )
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError as e:
        raise RuntimeError(f"Text read failed: {e}") from e

    cands = _split_candidates(raw, "text", original_filename)
    out.candidates.extend(cands)
    return out


def _row_to_text(row: dict[str, str]) -> str:
    """Turn a dict row into a single-line string."""
    parts: list[str] = []
    for k, v in row.items():
        if v:
            parts.append(f"{k}: {v}")
    return " | ".join(parts)
