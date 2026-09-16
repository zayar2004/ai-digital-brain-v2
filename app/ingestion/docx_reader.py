"""
DOCX text extraction.

Uses python-docx. Extracts paragraphs and tables.
Preserves section/paragraph ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import docx


@dataclass
class DocxBlock:
    index: int
    kind: str  # "paragraph" | "table"
    text: str


@dataclass
class DocxDocument:
    blocks: list[DocxBlock] = field(default_factory=list)

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text)

    def paragraphs_only(self) -> list[str]:
        return [b.text for b in self.blocks if b.kind == "paragraph" and b.text]


def read_docx(path: str | Path) -> DocxDocument:
    doc = DocxDocument()
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise RuntimeError(f"DOCX read failed: {e}") from e

    idx = 0
    for p in d.paragraphs:
        txt = (p.text or "").strip()
        if not txt:
            continue
        idx += 1
        doc.blocks.append(DocxBlock(index=idx, kind="paragraph", text=txt))

    for table in d.tables:
        idx += 1
        rows_txt = []
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            rows_txt.append(" | ".join(cells))
        table_txt = "\n".join(rows_txt).strip()
        if table_txt:
            doc.blocks.append(DocxBlock(index=idx, kind="table", text=table_txt))

    return doc
