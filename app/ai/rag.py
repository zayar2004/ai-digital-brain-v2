"""
RAG pipeline.

    USER QUESTION
      → INTENT / ENTITY (simple rules)
      → SEARCH (unified + deterministic)
      → GROUND CONTEXT
      → AI ANSWER
      → GROUNDING CHECK
      → RETURN
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai import grounding, prompts
from app.ai.provider import AIResponse, chat, is_configured
from app.models import ErrorCase, ErrorKnowledge, Knowledge, MachineCode
from app.search import unified_search as US


@dataclass
class RAGResult:
    ok: bool
    answer: str = ""
    error: str | None = None
    provider: str = ""
    model: str = ""
    hits: list[dict] = field(default_factory=list)
    grounding_ok: bool = True
    grounding_problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "answer": self.answer,
            "error": self.error,
            "provider": self.provider,
            "model": self.model,
            "grounding_ok": self.grounding_ok,
            "grounding_problems": self.grounding_problems,
            "hits": self.hits,
        }


def answer_question(
    *,
    user_question: str,
    shop_code: str | None,
    shop_id: int | None,
    only_approved: bool = True,
) -> RAGResult:
    """
    Main RAG entry point.

    1. Search first (deterministic).
    2. Build context from search hits.
    3. Ask AI (if configured).
    4. Verify grounding.
    """
    q = (user_question or "").strip()
    if not q:
        return RAGResult(ok=False, error="empty question")

    # 1. Retrieve
    search = US.search(
        query=q,
        shop_id=shop_id,
        shop_code=shop_code,
        limit_per_kind=5,
        only_approved=only_approved,
    )

    # 2. Build context blocks
    context_blocks: list[str] = []
    for h in search.hits:
        block = _hit_to_context(h)
        if block:
            context_blocks.append(block)

    # 2.5 If NO context at all → return deterministic "not found" message
    # (no need to call AI — saves tokens + guarantees consistent phrasing)
    if not context_blocks:
        return RAGResult(
            ok=True,
            answer="ဒီအချက်အလက်ကို Approved Knowledge ထဲမှာ မတွေ့သေးပါ။",
            provider="none",
            model="none",
            hits=[h.to_dict() for h in search.hits],
            grounding_ok=True,
            grounding_problems=[],
        )

    # 3. Ask AI (context exists)
    if not is_configured():
        return RAGResult(
            ok=False,
            error="AI is not configured.",
            hits=[h.to_dict() for h in search.hits],
        )

    messages = prompts.build_rag_messages(
        user_question=q,
        shop_code=shop_code,
        context_blocks=context_blocks,
    )
    resp: AIResponse = chat(messages, temperature=0.2, max_tokens=400)
    if not resp.ok:
        return RAGResult(
            ok=False, error=resp.error or "AI request failed",
            provider=resp.provider, model=resp.model,
            hits=[h.to_dict() for h in search.hits],
        )

    # 4. If AI returned empty → deterministic fallback from top hit
    ai_text = (resp.text or "").strip()
    if not ai_text:
        ai_text = _fallback_from_hits(search.hits, context_blocks)
        if not ai_text:
            ai_text = "ဒီအချက်အလက်ကို Approved Knowledge ထဲမှာ မတွေ့သေးပါ။"

    # 5. Grounding check
    ctx_text = "\n\n".join(context_blocks)
    report = grounding.check(ai_text, ctx_text)

    return RAGResult(
        ok=True,
        answer=ai_text,
        provider=resp.provider,
        model=resp.model,
        hits=[h.to_dict() for h in search.hits],
        grounding_ok=report.ok,
        grounding_problems=report.problems,
    )


def _fallback_from_hits(hits, context_blocks) -> str:
    """Build a deterministic answer from the retrieved context."""
    if not hits:
        return ""

    lines: list[str] = []
    # Prefer error knowledge / error case snippets
    for h in hits[:3]:
        kind = h.kind if hasattr(h, "kind") else h.get("kind")
        title = h.title if hasattr(h, "title") else h.get("title", "")
        if kind in ("error", "case"):
            lines.append(f"📌 {title}")
    if not lines and hits:
        lines.append(f"📌 {hits[0].title if hasattr(hits[0], 'title') else hits[0].get('title', '')}")

    # Append context text (trimmed)
    body = "\n\n".join(c for c in context_blocks if c).strip()
    if body:
        lines.append("")
        lines.append(body[:1200])

    return "\n".join(lines).strip()


def _hit_to_context(hit) -> str:
    """Convert a search hit into a compact context block for the AI."""
    # Load the actual record (small DB lookups — bounded by limit_per_kind)
    try:
        if hit.kind == "knowledge":
            k = Knowledge.query.get(hit.id)
            if k:
                return (
                    f"[Knowledge #{k.id}] shop={k.shop.code if k.shop else '?'} "
                    f"status={k.status}\n"
                    f"title: {k.title}\n"
                    f"content: {(k.myanmar_content or k.original_content or '')[:800]}"
                )
        if hit.kind == "error":
            e = ErrorKnowledge.query.get(hit.id)
            if e:
                return (
                    f"[ErrorKnowledge #{e.id}] shop={e.shop.code if e.shop else '?'} "
                    f"code={e.error_code} machine={e.machine_name}\n"
                    f"symptoms: {e.symptoms or '—'}\n"
                    f"cause: {e.cause or '—'}\n"
                    f"solution: {e.solution or '—'}"
                )
        if hit.kind == "case":
            c = ErrorCase.query.get(hit.id)
            if c:
                return (
                    f"[ErrorCase #{c.id}] shop={c.shop.code if c.shop else '?'} "
                    f"code={c.error_code} machine={c.machine_name} unit={c.unit}\n"
                    f"problem: {c.problem or '—'}\n"
                    f"finding: {c.finding or '—'}\n"
                    f"action: {c.action_taken or '—'}\n"
                    f"result: {c.result or '—'}"
                )
        if hit.kind == "code":
            mc = MachineCode.query.get(hit.id)
            if mc:
                return (
                    f"[MachineCode #{mc.id}] shop={mc.shop.code if mc.shop else '?'} "
                    f"machine={mc.machine_name} unit={mc.unit} code={mc.code}"
                )
    except Exception:
        pass
    return ""
