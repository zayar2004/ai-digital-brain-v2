"""
Error Knowledge + Error Case service.

CRITICAL SEPARATION:
    ErrorKnowledge = official troubleshooting rule
    ErrorCase      = a real-world incident report

A single ErrorCase must NEVER automatically become ErrorKnowledge.
"""

from __future__ import annotations

from flask_login import current_user

from app.extensions import db
from app.models import (
    ErrorCase,
    ErrorKnowledge,
    ErrorKnowledgeStatus,
)


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


# ================================================================
# Error Knowledge
# ================================================================
def create_error_knowledge(
    *,
    shop_id: int,
    error_code: str | None = None,
    error_name: str | None = None,
    machine_id: int | None = None,
    machine_name: str | None = None,
    model: str | None = None,
    unit: str | None = None,
    symptoms: str | None = None,
    cause: str | None = None,
    check_steps: str | None = None,
    solution: str | None = None,
    notes: str | None = None,
    status: str = ErrorKnowledgeStatus.DRAFT,
) -> ErrorKnowledge:
    if not shop_id:
        raise ValueError("shop_id is required.")
    if not error_code and not error_name:
        raise ValueError("Either error_code or error_name is required.")

    ek = ErrorKnowledge(
        shop_id=shop_id,
        error_code=(error_code or "").strip() or None,
        error_name=(error_name or "").strip() or None,
        machine_id=machine_id,
        machine_name=(machine_name or "").strip() or None,
        model=(model or "").strip() or None,
        unit=(unit or "").strip() or None,
        symptoms=symptoms,
        cause=cause,
        check_steps=check_steps,
        solution=solution,
        notes=notes,
        status=status,
        created_by_id=_current_user_id(),
    )
    db.session.add(ek)
    db.session.commit()
    return ek


def update_error_knowledge(
    error_id: int,
    *,
    error_code: str | None = None,
    error_name: str | None = None,
    machine_name: str | None = None,
    model: str | None = None,
    unit: str | None = None,
    symptoms: str | None = None,
    cause: str | None = None,
    check_steps: str | None = None,
    solution: str | None = None,
    notes: str | None = None,
) -> ErrorKnowledge:
    ek = db.session.get(ErrorKnowledge, error_id)
    if not ek:
        raise ValueError("Error knowledge not found.")

    for field, val in [
        ("error_code", error_code), ("error_name", error_name),
        ("machine_name", machine_name), ("model", model), ("unit", unit),
        ("symptoms", symptoms), ("cause", cause),
        ("check_steps", check_steps), ("solution", solution),
        ("notes", notes),
    ]:
        if val is not None:
            setattr(ek, field, (val.strip() if isinstance(val, str) else val) or None)

    ek.version = (ek.version or 1) + 1
    db.session.commit()
    return ek


def approve_error_knowledge(error_id: int) -> ErrorKnowledge:
    ek = db.session.get(ErrorKnowledge, error_id)
    if not ek:
        raise ValueError("Error knowledge not found.")
    from app.models.base import utcnow
    ek.status = ErrorKnowledgeStatus.APPROVED
    ek.approved_by_id = _current_user_id()
    ek.approved_at = utcnow()
    db.session.commit()
    return ek


def archive_error_knowledge(error_id: int) -> ErrorKnowledge:
    ek = db.session.get(ErrorKnowledge, error_id)
    if not ek:
        raise ValueError("Error knowledge not found.")
    ek.status = ErrorKnowledgeStatus.ARCHIVED
    db.session.commit()
    return ek


def list_error_knowledge(
    *, shop_id: int | None = None, status: str | None = None,
    error_code: str | None = None, q: str | None = None,
    global_shared: bool = True,
):
    """
    List error knowledge.

    ★ global_shared=True (default): ignore shop filter — all shops see everything.
    """
    from sqlalchemy import or_
    query = ErrorKnowledge.query.filter(ErrorKnowledge.is_deleted.is_(False))
    # Global by default — no shop filter
    if not global_shared and shop_id:
        query = query.filter(ErrorKnowledge.shop_id == shop_id)
    if status:
        query = query.filter(ErrorKnowledge.status == status)
    if error_code:
        query = query.filter(ErrorKnowledge.error_code == error_code)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(
            db.func.lower(db.func.coalesce(ErrorKnowledge.error_code, "")).like(like),
            db.func.lower(db.func.coalesce(ErrorKnowledge.error_name, "")).like(like),
            db.func.lower(db.func.coalesce(ErrorKnowledge.machine_name, "")).like(like),
        ))
    return query.order_by(ErrorKnowledge.id.desc())


# ================================================================
# Error Cases
# ================================================================
def create_error_case(
    *,
    shop_id: int,
    error_code: str | None = None,
    machine_id: int | None = None,
    machine_name: str | None = None,
    model: str | None = None,
    unit: str | None = None,
    problem: str | None = None,
    finding: str | None = None,
    action_taken: str | None = None,
    result: str | None = None,
    myanmar_content: str | None = None,
    photo_paths: list | None = None,       # ★ NEW
    status: str = "PENDING",
) -> ErrorCase:
    if not shop_id:
        raise ValueError("shop_id is required.")

    ec = ErrorCase(
        shop_id=shop_id,
        error_code=(error_code or "").strip() or None,
        machine_id=machine_id,
        machine_name=(machine_name or "").strip() or None,
        model=(model or "").strip() or None,
        unit=(unit or "").strip() or None,
        problem=problem,
        finding=finding,
        action_taken=action_taken,
        result=result,
        myanmar_content=myanmar_content,
        photo_path=(photo_paths[0] if photo_paths else None),  # first photo (primary)
        photo_paths=__import__("json").dumps(photo_paths) if photo_paths else None,
        status=status,
        created_by_id=_current_user_id(),
    )
    db.session.add(ec)
    db.session.commit()
    return ec


def approve_error_case(case_id: int) -> ErrorCase:
    ec = db.session.get(ErrorCase, case_id)
    if not ec:
        raise ValueError("Error case not found.")
    from app.models.base import utcnow
    ec.status = "APPROVED"
    ec.approved_by_id = _current_user_id()
    ec.approved_at = utcnow()
    db.session.commit()
    return ec


def archive_error_case(case_id: int) -> ErrorCase:
    ec = db.session.get(ErrorCase, case_id)
    if not ec:
        raise ValueError("Error case not found.")
    ec.status = "ARCHIVED"
    db.session.commit()
    return ec


def list_error_cases(
    *, shop_id: int | None = None, status: str | None = None,
    error_code: str | None = None, machine_id: int | None = None,
    global_shared: bool = True,
):
    """List error cases. Global by default."""
    query = ErrorCase.query.filter(ErrorCase.is_deleted.is_(False))
    if not global_shared and shop_id:
        query = query.filter(ErrorCase.shop_id == shop_id)
    if status:
        query = query.filter(ErrorCase.status == status)
    if error_code:
        query = query.filter(ErrorCase.error_code == error_code)
    if machine_id:
        query = query.filter(ErrorCase.machine_id == machine_id)
    return query.order_by(ErrorCase.id.desc())


def delete_error_knowledge(error_id: int) -> bool:
    """Hard delete — single error knowledge."""
    from app.extensions import db
    k = db.session.get(ErrorKnowledge, error_id)
    if not k:
        return False
    db.session.delete(k)
    db.session.commit()
    return True


def bulk_delete_error_knowledge(ids: list) -> int:
    """Hard delete — multiple IDs. Returns count."""
    from app.extensions import db
    if not ids:
        return 0
    clean_ids = []
    for i in ids:
        try:
            clean_ids.append(int(i))
        except (ValueError, TypeError):
            continue
    if not clean_ids:
        return 0
    count = (ErrorKnowledge.query
             .filter(ErrorKnowledge.id.in_(clean_ids))
             .delete(synchronize_session=False))
    db.session.commit()
    return count
