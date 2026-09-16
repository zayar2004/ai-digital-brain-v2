"""
Knowledge Search — Machine + Error Smart Match (v5 — 4 cases)
🅲 Both mode:
  Case 1: Machine + Error → strict match
  Case 2: Error only → hint (machines)
  Case 3: Machine only → hint (errors)
  Case 4: No match → fallback
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher


def parse_query(q: str) -> tuple[str, str]:
    q = (q or "").strip()
    if not q:
        return "", ""

    error_pats = [
        r'\b(Error\s*\d+)\b',
        r'\b(E\s*\d+)\b',
        r'\b(ERR?\s*\d+)\b',
        r'\b(OFF|ON|Jam|Reset)\b',
    ]
    for pat in error_pats:
        m = re.search(pat, q, re.IGNORECASE)
        if m:
            error = m.group(1).strip()
            machine = (q[:m.start()] + " " + q[m.end():]).strip()
            return machine, error

    parts = q.rsplit(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return q, ""


def similarity(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_overlap(q_tokens: list, t_tokens: list) -> float:
    if not q_tokens or not t_tokens:
        return 0.0
    matches = 0
    for qt in q_tokens:
        for tt in t_tokens:
            if qt == tt or qt in tt or tt in qt:
                matches += 1
                break
    return matches / len(q_tokens)


def match_score(q_machine: str, q_error: str,
                k_title: str, k_error_code: str) -> float:
    q_full = f"{q_machine} {q_error}".strip().lower()
    t_full = (k_title or "").strip().lower()
    t_e = (k_error_code or "").strip().lower()

    q_tokens = q_full.split()
    t_tokens = t_full.split()

    full_overlap = token_overlap(q_tokens, t_tokens)
    if full_overlap >= 0.95:
        return 1.0

    q_m = (q_machine or "").strip().lower()
    m_fuzzy = similarity(q_m, t_full)
    m_token = token_overlap(q_m.split(), t_full.split())
    m_score = max(m_fuzzy, m_token)

    q_e = (q_error or "").strip().lower()
    e_score = 0.0
    if q_e and t_e:
        if q_e == t_e:
            e_score = 1.0
        else:
            e_score = similarity(q_e, t_e)

    if not q_e:
        return m_score

    if not t_e:
        return m_score * 0.75

    total = m_score * 0.4 + e_score * 0.6
    if m_score >= 0.9 and e_score >= 0.9:
        total = min(total + 0.15, 1.0)

    return total


def search_knowledge_smart(query: str, shop_id: int | None = None,
                           threshold: float = 0.75):
    """
    Returns: (status, match_k, score, samples)
    status:
      "match"        → direct answer
      "error_hint"   → Error only — machines list
      "machine_hint" → Machine only — errors list
      "no_match"     → fallback
    """
    from app.models.knowledge import Knowledge

    q_machine, q_error = parse_query(query)

    q = Knowledge.query.filter_by(status="APPROVED", is_deleted=False)
    if shop_id:
        q = q.filter_by(shop_id=shop_id)
    all_k = q.all()

    # ── Case 1: Machine + Error — strict ──
    if q_machine and q_error:
        results = []
        for k in all_k:
            score = match_score(q_machine, q_error, k.title or "", k.error_code or "")
            results.append((score, k))
        results.sort(key=lambda x: -x[0])
        if not results or results[0][0] < threshold:
            return "no_match", None, (results[0][0] if results else 0.0), results[:6]
        # ★ Same score multiple → hint
        top_score = results[0][0]
        top_matches = [k for s, k in results if s == top_score]
        if len(top_matches) == 1:
            return "match", top_matches[0], top_score, []
        else:
            return "machine_hint", None, top_score, top_matches[:6]

    # ── Case 2: Error only — hint ──
    if q_error and not q_machine:
        q_e = q_error.strip().lower()
        matches = []
        for k in all_k:
            ec = (k.error_code or "").strip().lower()
            if not ec:
                continue
            s = similarity(q_e, ec)
            if q_e == ec:
                s = 1.0
            if s >= 0.90:
                matches.append((s, k))
        matches.sort(key=lambda x: -x[0])
        if len(matches) == 1:
            return "match", matches[0][1], matches[0][0], []
        elif matches:
            return "error_hint", None, 0.0, [k for _, k in matches[:6]]
        return "no_match", None, 0.0, []

    # ── Case 3: Machine only — hint ──
    if q_machine and not q_error:
        q_m = q_machine.strip().lower()
        matches = []
        for k in all_k:
            title = (k.title or "").strip().lower()
            s = max(similarity(q_m, title), token_overlap(q_m.split(), title.split()))
            if s >= 0.80:
                matches.append((s, k))
        matches.sort(key=lambda x: -x[0])
        if not matches:
            return "no_match", None, 0.0, []
        # ★ Same score multiple → hint
        top_score = matches[0][0]
        top_matches = [k for s, k in matches if s == top_score]
        if len(top_matches) == 1:
            return "match", top_matches[0], top_score, []
        else:
            return "machine_hint", None, top_score, top_matches[:6]

    # ── Case 4: Garbage ──
    return "no_match", None, 0.0, []
