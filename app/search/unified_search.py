"""
Unified search across Knowledge, Machine Codes, Machines, Errors.

Strict shop isolation is enforced at the query level.
Returns a grouped, scored result set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    ErrorCase,
    ErrorKnowledge,
    Knowledge,
    Machine,
    MachineAlias,
    MachineCode,
)


def _norm(s: str | None) -> str:
    if not s:
        return ""
    # Normalize: lowercase, strip, replace _ and - with space, collapse spaces
    s = str(s).strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(q: str) -> list[str]:
    """Split query into meaningful tokens.

    Filters:
      - >= 3 chars: keep any
      - == 2 chars: keep only if alphabetic (e.g. CT, OK)
      - digits: keep only if 2+ digits (e.g. 07, 12)
      - single chars: drop
    """
    q = _norm(q)
    if not q:
        return []
    q = re.sub(r"[#():,\[\]\{\}\"']", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    tokens = [t for t in re.split(r"[\s_\-/]+", q) if t]

    cleaned: list[str] = []
    for t in tokens:
        if len(t) >= 3:
            cleaned.append(t)
        elif len(t) == 2 and t.isalpha():
            cleaned.append(t)
        elif t.isdigit() and len(t) >= 2:
            cleaned.append(t)

    return cleaned if cleaned else tokens

@dataclass
class Hit:
    kind: str           # knowledge | machine | code | error | case
    id: int
    title: str
    subtitle: str = ""
    snippet: str = ""
    url: str = ""
    shop: str = ""
    score: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "snippet": self.snippet,
            "url": self.url,
            "shop": self.shop,
            "score": round(self.score, 3),
            "extra": self.extra,
        }


@dataclass
class SearchResult:
    query: str
    shop_code: str | None
    hits: list[Hit] = field(default_factory=list)
    by_kind: dict[str, list[Hit]] = field(default_factory=dict)
    total: int = 0

    def group(self) -> dict[str, list[Hit]]:
        g: dict[str, list[Hit]] = {}
        for h in self.hits:
            g.setdefault(h.kind, []).append(h)
        self.by_kind = g
        return g

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "shop": self.shop_code,
            "total": self.total,
            "results": [h.to_dict() for h in self.hits],
        }


# ----------------------------------------------------------------
# Scoring helpers
# ----------------------------------------------------------------
def _score_text(query: str, query_tokens: list[str], *fields: str | None) -> float:
    """Return a score 0..1 for a candidate against query."""
    if not query:
        return 0.0
    q = _norm(query)
    joined = " ".join(_norm(f) for f in fields if f)
    if not joined:
        return 0.0

    # Exact whole-string match
    if q == joined:
        return 1.0
    # Prefix
    if joined.startswith(q):
        return 0.9
    # Contains full query
    if q in joined:
        return 0.8
    # Token coverage — require at least 50% match
    if query_tokens:
        hits = sum(1 for t in query_tokens if t in joined)
        if hits == len(query_tokens):
            return 0.7
        # ★ Require at least HALF the tokens to match
        if hits > 0 and (hits / len(query_tokens)) >= 0.5:
            return 0.3 + 0.4 * (hits / len(query_tokens))
        # Single token match with many query tokens → weak
        if len(query_tokens) >= 2 and hits == 1:
            return 0.0     # reject weak matches
    return 0.0


# ----------------------------------------------------------------
# Main search
# ----------------------------------------------------------------
def search(
    *,
    query: str,
    shop_id: int | None,
    shop_code: str | None,
    limit_per_kind: int = 20,
    only_approved: bool = True,
) -> SearchResult:
    """
    Search across all entity kinds.

    If shop_id is None → search across all shops (Admin).
    Strict shop scope is applied when shop_id is given.
    """
    result = SearchResult(query=query, shop_code=shop_code)
    q = (query or "").strip()
    if not q:
        return result

    tokens = _tokens(q)

    # --- Machines ---
    mq = Machine.query.filter(Machine.is_deleted.is_(False))
    if shop_id:
        mq = mq.filter(Machine.shop_id == shop_id)
    machines = mq.limit(200).all()

    for m in machines:
        alias_names = [a.alias for a in m.aliases] if m.aliases else []
        score = _score_text(q, tokens, m.name, m.model, m.unit, *alias_names)
        if score <= 0:
            continue
        result.hits.append(Hit(
            kind="machine",
            id=m.id,
            title=m.name,
            subtitle=f"{m.shop.code} · {m.model or '—'} · {m.unit or '—'}",
            snippet=", ".join(alias_names[:5]),
            url=f"/machines/{m.id}",
            shop=m.shop.code if m.shop else "",
            score=score,
        ))

    # --- Machine Codes ---
    cq = MachineCode.query
    if shop_id:
        cq = cq.filter(MachineCode.shop_id == shop_id)
    if only_approved:
        cq = cq.filter(MachineCode.status == "APPROVED")
    codes = cq.limit(500).all()

    for c in codes:
        score = _score_text(q, tokens, c.code, c.machine_name, c.model, c.unit)
        if score <= 0:
            continue
        result.hits.append(Hit(
            kind="code",
            id=c.id,
            title=c.code,
            subtitle=f"{c.machine_name or '—'} · {c.unit or '—'}",
            snippet="",
            url=f"/machine-codes?q={q}&shop={c.shop.code if c.shop else ''}",
            shop=c.shop.code if c.shop else "",
            score=score,
            extra={"code": c.code, "unit": c.unit},
        ))

    # --- Knowledge (GLOBAL — all shops can see) ---
    kq = Knowledge.query.filter(Knowledge.is_deleted.is_(False))
    # ★ Shop filter intentionally REMOVED — knowledge is shared
    if only_approved:
        kq = kq.filter(Knowledge.status == "APPROVED")
    knowledges = kq.limit(300).all()

    for k in knowledges:
        score = _score_text(
            q, tokens, k.title, k.myanmar_content, k.english_content,
            k.original_content, k.error_code, k.unit, k.model,
        )
        if score <= 0:
            continue
        # Strip title from snippet so it doesn't duplicate
        body = (k.myanmar_content or k.original_content or "").strip()
        if k.title and body.lower().startswith(k.title.lower()):
            body = body[len(k.title):].strip()

        result.hits.append(Hit(
            kind="knowledge",
            id=k.id,
            title=k.title,
            subtitle=f"{k.shop.code} · {k.status}" if k.shop else k.status,
            snippet=_snippet(body),
            url=f"/knowledge/{k.id}",
            shop=k.shop.code if k.shop else "",
            score=score,
        ))

    # --- Error Knowledge (GLOBAL — all shops can see) ---
    eq = ErrorKnowledge.query.filter(ErrorKnowledge.is_deleted.is_(False))
    # ★ Shop filter intentionally REMOVED — errors are shared globally
    if only_approved:
        eq = eq.filter(ErrorKnowledge.status == "APPROVED")
    errors = eq.limit(300).all()

    for e in errors:
        fields = [
            e.error_code, e.error_name, e.machine_name,
            e.symptoms, e.cause, e.solution, e.check_steps,
            e.model, e.unit, e.notes,
        ]
        score = _score_text(q, tokens, *fields)

        q_norm = _norm(q)
        if e.error_code:
            ec_norm = _norm(e.error_code)
            if ec_norm == q_norm:
                score = max(score, 1.0)
            elif q_norm and q_norm in ec_norm:
                score = max(score, 0.9)
        if e.error_name:
            en_norm = _norm(e.error_name)
            if q_norm and q_norm in en_norm:
                score = max(score, 0.85)

        if score <= 0:
            continue
        result.hits.append(Hit(
            kind="error",
            id=e.id,
            title=f"Error {e.error_code or '—'} · {e.error_name or '—'}",
            subtitle=f"{e.shop.code} · {e.machine_name or '—'}",
            snippet=_snippet(e.solution or e.cause or e.symptoms),
            url=f"/errors",
            shop=e.shop.code if e.shop else "",
            score=score,
            extra={"error_code": e.error_code},
        ))

    # --- Error Cases (GLOBAL — all shops can see) ---
    ecq = ErrorCase.query.filter(ErrorCase.is_deleted.is_(False))
    # ★ Shop filter intentionally REMOVED
    if only_approved:
        ecq = ecq.filter(ErrorCase.status == "APPROVED")
    cases = ecq.limit(300).all()

    for c in cases:
        score = _score_text(
            q, tokens, c.error_code, c.machine_name, c.unit,
            c.problem, c.finding, c.action_taken, c.result,
        )
        if score <= 0:
            continue
        result.hits.append(Hit(
            kind="case",
            id=c.id,
            title=f"Case · Error {c.error_code or '—'}",
            subtitle=f"{c.shop.code} · {c.machine_name or '—'} · {c.unit or '—'}",
            snippet=_snippet(c.finding or c.action_taken),
            url=f"/error-cases",
            shop=c.shop.code if c.shop else "",
            score=score,
        ))

    # Sort & limit per kind
    result.hits.sort(key=lambda h: (-h.score, h.kind, h.title.lower()))
    grouped = result.group()
    trimmed: list[Hit] = []
    for kind, hits in grouped.items():
        trimmed.extend(hits[:limit_per_kind])
    trimmed.sort(key=lambda h: (-h.score, h.kind))
    result.hits = trimmed
    result.group()
    result.total = len(result.hits)
    return result


def _snippet(text: str | None, max_len: int = 800) -> str:
    if not text:
        return ""
    # Normalize: collapse multiple spaces/tabs but PRESERVE newlines
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    # Collapse horizontal whitespace only (space, tab)
    s = re.sub(r"[ \t]+", " ", s)
    # Collapse 3+ blank lines → 2 (max one blank line between paragraphs)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "…"
    return s
