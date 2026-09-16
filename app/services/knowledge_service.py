"""
Knowledge service.

Central entry point for Knowledge CRUD + approval + versioning + conflicts.
"""

from __future__ import annotations

from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Knowledge,
    KnowledgeConflict,
    KnowledgeConflictStatus,
    KnowledgeStatus,
    KnowledgeVersion,
)


def create_knowledge(
    *,
    shop_id: int,
    title: str,
    category: str | None = None,
    machine_id: int | None = None,
    model: str | None = None,
    unit: str | None = None,
    error_code: str | None = None,
    original_content: str | None = None,
    myanmar_content: str | None = None,
    english_content: str | None = None,
    original_language: str = "my",
    confidence: float | None = 1.0,
    source_type: str | None = "manual",
    source_file: str | None = None,
    source_sheet: str | None = None,
    source_row: int | None = None,
    source_reference: str | None = None,
    status: str = KnowledgeStatus.DRAFT,
    effective_from=None,
    effective_until=None,
) -> Knowledge:
    title = (title or "").strip()
    if not title:
        raise ValueError("Knowledge title is required.")
    if not shop_id:
        raise ValueError("shop_id is required.")

    k = Knowledge(
        shop_id=shop_id,
        title=title,
        category=category,
        machine_id=machine_id,
        model=model,
        unit=unit,
        error_code=error_code,
        original_content=original_content,
        myanmar_content=myanmar_content,
        english_content=english_content,
        original_language=original_language,
        confidence=confidence,
        source_type=source_type,
        source_file=source_file,
        source_sheet=source_sheet,
        source_row=source_row,
        source_reference=source_reference,
        status=status,
        version=1,
        created_by_id=_current_user_id(),
        effective_from=effective_from,
        effective_until=effective_until,
    )
    db.session.add(k)
    db.session.flush()

    _snapshot_version(k, reason="initial")

    # Auto-detect conflicts with approved knowledge (same shop + unit + error_code)
    _detect_conflicts(k)

    db.session.commit()
    return k


def update_knowledge(
    knowledge_id: int,
    *,
    title: str | None = None,
    myanmar_content: str | None = None,
    english_content: str | None = None,
    original_content: str | None = None,
    category: str | None = None,
    machine_id: int | None = None,
    model: str | None = None,
    unit: str | None = None,
    error_code: str | None = None,
    confidence: float | None = None,
    effective_from=None,
    effective_until=None,
    change_reason: str = "edit",
) -> Knowledge:
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        raise ValueError("Knowledge not found.")

    changed = False
    for field, value in [
        ("title", title),
        ("myanmar_content", myanmar_content),
        ("english_content", english_content),
        ("original_content", original_content),
        ("category", category),
        ("machine_id", machine_id),
        ("model", model),
        ("unit", unit),
        ("error_code", error_code),
        ("confidence", confidence),
        ("effective_from", effective_from),
        ("effective_until", effective_until),
    ]:
        if value is not None and getattr(k, field) != value:
            setattr(k, field, value)
            changed = True

    if not changed:
        return k

    k.version = (k.version or 1) + 1
    db.session.flush()
    _snapshot_version(k, reason=change_reason, changed_by_id=_current_user_id())
    db.session.commit()
    return k


def approve_knowledge(knowledge_id: int) -> Knowledge:
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        raise ValueError("Knowledge not found.")
    from app.models.base import utcnow
    k.status = KnowledgeStatus.APPROVED
    k.approved_by_id = _current_user_id()
    k.approved_at = utcnow()
    db.session.commit()
    # On approval, re-check for conflicts against other approved items
    _detect_conflicts(k)
    db.session.commit()
    return k


def archive_knowledge(knowledge_id: int) -> Knowledge:
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        raise ValueError("Knowledge not found.")
    k.status = KnowledgeStatus.ARCHIVED
    db.session.commit()
    return k


def list_knowledge(
    *,
    shop_id: int | None = None,
    status: str | None = None,
    machine_id: int | None = None,
    q: str | None = None,
    global_shared: bool = True,
):
    """
    List knowledge.

    ★ global_shared=True (default): ignore shop filter — all shops see everything.
    ★ global_shared=False: enforce shop_id filter (admin chose a specific shop).
    """
    query = Knowledge.query.filter(Knowledge.is_deleted.is_(False))
    if not global_shared and shop_id:
        query = query.filter(Knowledge.shop_id == shop_id)
    if status:
        query = query.filter(Knowledge.status == status)
    if machine_id:
        query = query.filter(Knowledge.machine_id == machine_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(
            db.func.lower(Knowledge.title).like(like),
            db.func.lower(db.func.coalesce(Knowledge.myanmar_content, "")).like(like),
            db.func.lower(db.func.coalesce(Knowledge.english_content, "")).like(like),
        ))
    return query.order_by(Knowledge.id.desc())


def restore_version(knowledge_id: int, version_number: int) -> Knowledge:
    """Restore a previous version's snapshot into the current Knowledge."""
    from app.models import KnowledgeVersion
    k = db.session.get(Knowledge, knowledge_id)
    if not k:
        raise ValueError("Knowledge not found.")
    v = KnowledgeVersion.query.filter_by(
        knowledge_id=knowledge_id, version=version_number
    ).first()
    if not v:
        raise ValueError(f"Version {version_number} not found.")

    k.title = v.title
    k.original_content = v.original_content
    k.myanmar_content = v.myanmar_content
    k.english_content = v.english_content
    k.status = v.status
    k.confidence = v.confidence
    k.version = (k.version or 1) + 1
    db.session.flush()
    _snapshot_version(k, reason=f"restore v{version_number}",
                      changed_by_id=_current_user_id())
    db.session.commit()
    return k


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _snapshot_version(k: Knowledge, *, reason: str,
                      changed_by_id: int | None = None) -> None:
    v = KnowledgeVersion(
        knowledge_id=k.id,
        version=k.version or 1,
        title=k.title,
        original_content=k.original_content,
        myanmar_content=k.myanmar_content,
        english_content=k.english_content,
        status=k.status,
        confidence=k.confidence,
        changed_by_id=changed_by_id,
        change_reason=reason,
    )
    db.session.add(v)


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def _detect_conflicts(k: Knowledge) -> list[KnowledgeConflict]:
    """
    Detect potential conflicts with other knowledge in same shop
    matching (unit, error_code) and different content.
    """
    if not k.unit or not k.error_code:
        return []

    candidates = Knowledge.query.filter(
        Knowledge.shop_id == k.shop_id,
        Knowledge.id != k.id,
        Knowledge.is_deleted.is_(False),
        Knowledge.status == KnowledgeStatus.APPROVED,
        Knowledge.unit == k.unit,
        Knowledge.error_code == k.error_code,
    ).all()

    created: list[KnowledgeConflict] = []
    for other in candidates:
        # Skip if same content
        if (other.myanmar_content or "") == (k.myanmar_content or ""):
            continue

        # Existing conflict?
        existing = KnowledgeConflict.query.filter(
            or_(
                db.and_(KnowledgeConflict.knowledge_a_id == k.id,
                        KnowledgeConflict.knowledge_b_id == other.id),
                db.and_(KnowledgeConflict.knowledge_a_id == other.id,
                        KnowledgeConflict.knowledge_b_id == k.id),
            )
        ).first()
        if existing:
            continue

        c = KnowledgeConflict(
            shop_id=k.shop_id,
            knowledge_a_id=k.id,
            knowledge_b_id=other.id,
            description=(
                f"Same unit={k.unit} error_code={k.error_code} but different content."
            ),
            status=KnowledgeConflictStatus.OPEN,
        )
        db.session.add(c)
        created.append(c)
    return created


def list_open_conflicts(shop_id: int | None = None):
    q = KnowledgeConflict.query.filter_by(status=KnowledgeConflictStatus.OPEN)
    if shop_id:
        q = q.filter_by(shop_id=shop_id)
    return q.order_by(KnowledgeConflict.id.desc()).all()


def resolve_conflict(conflict_id: int, note: str = "") -> KnowledgeConflict:
    from app.models.base import utcnow
    c = db.session.get(KnowledgeConflict, conflict_id)
    if not c:
        raise ValueError("Conflict not found.")
    c.status = KnowledgeConflictStatus.RESOLVED
    c.resolved_by_id = _current_user_id()
    c.resolved_at = utcnow()
    c.resolution_note = note
    db.session.commit()
    return c
