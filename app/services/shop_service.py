"""
Shop service.

Provides the canonical list of shops (A1-A13) and safe lookups.
All shop-scoped records MUST reference a shop via this service.
"""

from __future__ import annotations

from functools import lru_cache

from app.extensions import db
from app.models import Shop


def list_shops(only_active: bool = True) -> list[Shop]:
    """Return all shops, ordered by numeric code (A1, A2, ..., A13)."""
    q = Shop.query
    if only_active:
        q = q.filter_by(is_active=True)

    shops = q.all()
    return sorted(shops, key=_sort_key)


def _sort_key(shop: Shop) -> tuple[int, str]:
    """Sort A1 < A2 < ... < A10 < ... < A13 numerically."""
    code = shop.code or ""
    if code.startswith("A") and code[1:].isdigit():
        return (int(code[1:]), code)
    return (9999, code)


def get_shop_by_code(code: str) -> Shop | None:
    """Return a shop by its code ('A3'), or None."""
    if not code:
        return None
    return Shop.query.filter_by(code=str(code).strip().upper()).first()


def get_shop_by_id(shop_id: int) -> Shop | None:
    if not shop_id:
        return None
    try:
        return db.session.get(Shop, int(shop_id))
    except (TypeError, ValueError):
        return None


def shop_codes() -> list[str]:
    """Return the list of active shop codes in numeric order."""
    return [s.code for s in list_shops(only_active=True)]


def ensure_shops_seeded() -> int:
    """
    Ensure A1-A13 exist. Returns number of shops created.
    Safe to call on startup.
    """
    created = 0
    for code in Shop.all_codes():
        if not Shop.query.filter_by(code=code).first():
            db.session.add(Shop(code=code, name=code, is_active=True))
            created += 1
    if created:
        db.session.commit()
    return created


# ================================================================
# Shop Stats (for /shops UI)
# ================================================================
def shop_stats(shop_id: int) -> dict:
    """Return counts of records belonging to one shop."""
    from app.models import (
        ErrorCase, ErrorKnowledge, Knowledge, Machine,
        MachineCode, MediaFile, Task, TelegramUserShop,
    )

    return {
        "machines": Machine.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "codes": MachineCode.query.filter_by(shop_id=shop_id).count(),
        "knowledge": Knowledge.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "errors": ErrorKnowledge.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "cases": ErrorCase.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "files": MediaFile.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "tasks_total": Task.query.filter_by(
            shop_id=shop_id, is_deleted=False
        ).count(),
        "tasks_pending": Task.query.filter(
            Task.shop_id == shop_id,
            Task.is_deleted.is_(False),
            Task.status.in_(("PENDING", "IN_PROGRESS")),
        ).count(),
        "telegram_users": TelegramUserShop.query.filter_by(
            shop_id=shop_id, is_active=True
        ).count(),
    }


def shop_stats_bulk() -> dict[int, dict]:
    """
    Return {shop_id: stats} for ALL shops in ~9 queries.
    Use on /shops list (13 shops → 13 queries vs 117).
    """
    from sqlalchemy import func
    from app.models import (
        ErrorCase, ErrorKnowledge, Knowledge, Machine,
        MachineCode, MediaFile, Task, TelegramUserShop,
    )

    def counts(model, **filters):
        q = db.session.query(model.shop_id, func.count(model.id))
        for k, v in filters.items():
            q = q.filter(getattr(model, k) == v)
        return dict(q.group_by(model.shop_id).all())

    machines = counts(Machine, is_deleted=False)
    codes = counts(MachineCode)
    knowledge = counts(Knowledge, is_deleted=False)
    errors = counts(ErrorKnowledge, is_deleted=False)
    cases = counts(ErrorCase, is_deleted=False)
    files = counts(MediaFile, is_deleted=False)
    tasks_all = counts(Task, is_deleted=False)
    tasks_pending = dict(
        db.session.query(Task.shop_id, func.count(Task.id))
        .filter(
            Task.is_deleted.is_(False),
            Task.status.in_(("PENDING", "IN_PROGRESS")),
        )
        .group_by(Task.shop_id)
        .all()
    )
    tg_users = counts(TelegramUserShop, is_active=True)

    all_ids = set()
    for d in (machines, codes, knowledge, errors, cases,
              files, tasks_all, tasks_pending, tg_users):
        all_ids |= set(d.keys())

    out: dict[int, dict] = {}
    for sid in all_ids:
        out[sid] = {
            "machines": machines.get(sid, 0),
            "codes": codes.get(sid, 0),
            "knowledge": knowledge.get(sid, 0),
            "errors": errors.get(sid, 0),
            "cases": cases.get(sid, 0),
            "files": files.get(sid, 0),
            "tasks_total": tasks_all.get(sid, 0),
            "tasks_pending": tasks_pending.get(sid, 0),
            "telegram_users": tg_users.get(sid, 0),
        }
    return out

def create_shop(code: str, name: str | None = None,
                description: str | None = None,
                is_active: bool = True) -> Shop:
    """Create a new shop with strict code sanitization.

    Code rules:
      - Auto uppercase
      - Only A-Z, 0-9 kept (all other chars removed)
      - Must start with a letter
      - Max 16 chars
    """
    from app.extensions import db
    import re as _re

    # 1. Strict sanitize — A-Z, 0-9 only
    raw = (code or "").strip().upper()
    code_clean = _re.sub(r"[^A-Z0-9]", "", raw)

    if not code_clean:
        raise ValueError("ဆိုင်ကုဒ် လိုအပ်ပါတယ်။")
    if len(code_clean) > 16:
        raise ValueError("ဆိုင်ကုဒ် 16 characters ထက် မကျော်ရ။")
    if not _re.match(r"^[A-Z]", code_clean):
        raise ValueError("ဆိုင်ကုဒ် — letter (A-Z) နဲ့ စရမယ်။")

    # 2. Existing check
    existing = Shop.query.filter_by(code=code_clean).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.deleted_at = None
            existing.name = (name or code_clean).strip() or code_clean
            existing.description = description
            existing.is_active = is_active
            db.session.commit()
            return existing
        raise ValueError(f"ဆိုင်ကုဒ် '{code_clean}' ရှိပြီးသားပါ။")

    # 3. Create
    shop = Shop(
        code=code_clean,
        name=(name or code_clean).strip() or code_clean,
        description=description,
        is_active=is_active,
    )
    db.session.add(shop)
    db.session.commit()
    return shop


def update_shop(shop_id: int, *, name=None, description=None,
                is_active=None) -> Shop:
    """Update existing shop fields."""
    from app.extensions import db

    shop = db.session.get(Shop, shop_id)
    if not shop:
        raise ValueError("Shop not found")
    if name is not None:
        shop.name = name.strip() or shop.code
    if description is not None:
        shop.description = description
    if is_active is not None:
        shop.is_active = bool(is_active)
    db.session.commit()
    return shop

