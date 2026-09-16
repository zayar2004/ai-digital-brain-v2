"""
Machine Code search service.

Deterministic search with strict shop isolation.
No AI required — works even when AI is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.extensions import db
from app.models import MachineCode, MachineCodeSource


# ----------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------
def normalize_query(q: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    if not q:
        return ""
    s = str(q).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_code(code: str) -> str:
    """Uppercase, strip, collapse whitespace."""
    if not code:
        return ""
    return re.sub(r"\s+", " ", str(code).strip().upper())


def tokenize(q: str) -> list[str]:
    """Split a query into tokens, preserving short words."""
    q = normalize_query(q)
    if not q:
        return []
    return [t for t in re.split(r"[\s_\-/]+", q) if t]


# ----------------------------------------------------------------
# Search result
# ----------------------------------------------------------------
@dataclass
class CodeMatch:
    id: int
    shop_code: str
    machine_name: str | None
    model: str | None
    unit: str | None
    code: str
    status: str
    score: float = 0.0
    match_type: str = "partial"  # exact | prefix | partial | alias | fuzzy

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shop": self.shop_code,
            "machine": self.machine_name,
            "model": self.model,
            "unit": self.unit,
            "code": self.code,
            "status": self.status,
            "match_type": self.match_type,
            "score": round(self.score, 3),
        }


@dataclass
class SearchOutcome:
    query: str
    shop_code: str | None
    matches: list[CodeMatch] = field(default_factory=list)
    total: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "shop": self.shop_code,
            "total": self.total,
            "matches": [m.to_dict() for m in self.matches],
        }


# ----------------------------------------------------------------
# Core search
# ----------------------------------------------------------------
def search_machine_codes(
    *,
    shop_id: int,
    shop_code: str,
    query: str,
    only_approved: bool = False,
    limit: int = 100,
) -> SearchOutcome:
    """
    Search machine codes within a single shop.

    Strict shop isolation is enforced at the query level.
    """
    outcome = SearchOutcome(query=query, shop_code=shop_code)

    base = MachineCode.query.filter(MachineCode.shop_id == shop_id)
    if only_approved:
        base = base.filter(MachineCode.status == "APPROVED")

    q_norm = normalize_query(query)
    if not q_norm:
        # No query: return all (up to limit), ordered by code
        rows = base.order_by(MachineCode.code.asc()).limit(limit).all()
        outcome.matches = [
            CodeMatch(
                id=r.id,
                shop_code=shop_code,
                machine_name=r.machine_name,
                model=r.model,
                unit=r.unit,
                code=r.code,
                status=r.status,
                score=0.5,
                match_type="list",
            )
            for r in rows
        ]
        outcome.total = base.count()
        return outcome

    tokens = tokenize(q_norm)

    # Fetch a candidate set (bounded) from this shop only
    candidates = base.limit(1000).all()

    scored: list[CodeMatch] = []
    for r in candidates:
        score, mtype = _score_row(r, q_norm, tokens)
        if score <= 0:
            continue
        scored.append(
            CodeMatch(
                id=r.id,
                shop_code=shop_code,
                machine_name=r.machine_name,
                model=r.model,
                unit=r.unit,
                code=r.code,
                status=r.status,
                score=score,
                match_type=mtype,
            )
        )

    scored.sort(key=lambda m: (-m.score, m.code))
    outcome.matches = scored[:limit]
    outcome.total = len(scored)
    return outcome


def _score_row(row: MachineCode, q_norm: str, tokens: list[str]) -> tuple[float, str]:
    """Return (score, match_type). Score 0 means no match."""
    code_n = normalize_query(row.code or "")
    machine_n = normalize_query(row.machine_name or "")
    model_n = normalize_query(row.model or "")
    unit_n = normalize_query(row.unit or "")

    # Exact code match
    if q_norm == code_n:
        return (1.0, "exact")

    # Exact machine + unit match
    if q_norm == machine_n:
        return (0.95, "exact")

    # Prefix match on code
    if code_n.startswith(q_norm):
        return (0.9, "prefix")

    # Prefix match on machine
    if machine_n.startswith(q_norm):
        return (0.85, "prefix")

    # All tokens present?
    fields = [code_n, machine_n, model_n, unit_n]
    if all(any(t in f for f in fields) for t in tokens):
        # Boost if match includes machine+unit
        has_machine = any(t in machine_n for t in tokens)
        has_unit = any(t in unit_n for t in tokens)
        has_code = any(t in code_n for t in tokens)
        if has_machine and has_unit:
            return (0.8, "partial")
        if has_code:
            return (0.75, "partial")
        if has_machine:
            return (0.7, "partial")
        return (0.6, "partial")

    # Any token match (weak)
    hit_count = sum(1 for t in tokens if any(t in f for f in fields))
    if hit_count > 0 and len(tokens) > 0:
        return (0.3 * (hit_count / len(tokens)), "fuzzy")

    return (0.0, "none")


# ----------------------------------------------------------------
# Approval
# ----------------------------------------------------------------
def approve_code(code_id: int) -> bool:
    row = db.session.get(MachineCode, code_id)
    if not row:
        return False
    row.status = "APPROVED"
    db.session.commit()
    return True


def approve_source_codes(source_id: int) -> int:
    rows = MachineCode.query.filter_by(source_id=source_id, status="PENDING").all()
    for r in rows:
        r.status = "APPROVED"
    db.session.commit()
    return len(rows)


def archive_code(code_id: int) -> bool:
    row = db.session.get(MachineCode, code_id)
    if not row:
        return False
    row.status = "ARCHIVED"
    db.session.commit()
    return True
