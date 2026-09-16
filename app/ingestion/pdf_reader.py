"""
PDF text extraction.

Uses PyPDF2. Never invents text.
Preserves page numbers for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import PyPDF2


@dataclass
class PDFPage:
    page_number: int
    text: str


@dataclass
class PDFDocument:
    pages: list[PDFPage] = field(default_factory=list)
    title: str | None = None
    page_count: int = 0

    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)


def read_pdf(path: str | Path) -> PDFDocument:
    """Extract text from every page. Skips empty pages."""
    doc = PDFDocument()
    try:
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            doc.page_count = len(reader.pages)
            try:
                meta = reader.metadata or {}
                doc.title = (meta.get("/Title") or "").strip() or None
            except Exception:
                doc.title = None

            for i, page in enumerate(reader.pages, start=1):
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                txt = txt.strip()
                if txt:
                    doc.pages.append(PDFPage(page_number=i, text=txt))
    except Exception as e:
        raise RuntimeError(f"PDF read failed: {e}") from e

    return doc
