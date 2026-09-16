"""
Machine service.

All machine operations go through here.
Enforces shop scope and prevents duplicates.
"""

from __future__ import annotations

from sqlalchemy import or_

from app.extensions import db
from app.models import Machine, MachineAlias


def list_machines(shop_id: int | None = None, only_active: bool = True) -> list[Machine]:
    """List machines, optionally scoped to a shop."""
    q = Machine.query.filter(Machine.is_deleted.is_(False))
    if only_active:
        q = q.filter(Machine.status == "ACTIVE")
    if shop_id:
        q = q.filter(Machine.shop_id == shop_id)
    return q.order_by(Machine.name.asc()).all()


def get_machine(machine_id: int) -> Machine | None:
    if not machine_id:
        return None
    return db.session.get(Machine, machine_id)


def find_machine_in_shop(shop_id: int, name: str) -> Machine | None:
    """Find by exact name within a shop (case-insensitive)."""
    if not name:
        return None
    return (
        Machine.query.filter(
            Machine.shop_id == shop_id,
            Machine.is_deleted.is_(False),
            db.func.lower(Machine.name) == name.strip().lower(),
        )
        .first()
    )


def create_machine(
    *,
    shop_id: int,
    name: str,
    model: str | None = None,
    unit: str | None = None,
    description: str | None = None,
    aliases: list[str] | None = None,
) -> Machine:
    """Create a machine. Raises ValueError on duplicate / invalid."""
    if not shop_id:
        raise ValueError("shop_id is required.")
    name = (name or "").strip()
    if not name:
        raise ValueError("Machine name is required.")

    existing = find_machine_in_shop(shop_id, name)
    if existing:
        raise ValueError(f"Machine '{name}' already exists in this shop.")

    m = Machine(
        shop_id=shop_id,
        name=name,
        model=(model or "").strip() or None,
        unit=(unit or "").strip() or None,
        description=(description or "").strip() or None,
        status="ACTIVE",
    )
    db.session.add(m)
    db.session.flush()

    for a in (aliases or []):
        _safe_add_alias(m, a)

    db.session.commit()
    return m


def update_machine(
    machine_id: int,
    *,
    name: str | None = None,
    model: str | None = None,
    unit: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Machine:
    m = get_machine(machine_id)
    if not m:
        raise ValueError("Machine not found.")

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("Machine name cannot be empty.")
        if new_name.lower() != m.name.lower():
            dup = find_machine_in_shop(m.shop_id, new_name)
            if dup and dup.id != m.id:
                raise ValueError(f"Another machine named '{new_name}' exists in this shop.")
        m.name = new_name

    if model is not None:
        m.model = model.strip() or None
    if unit is not None:
        m.unit = unit.strip() or None
    if description is not None:
        m.description = description.strip() or None
    if status is not None and status in ("ACTIVE", "MAINTENANCE", "RETIRED"):
        m.status = status

    db.session.commit()
    return m


def archive_machine(machine_id: int) -> None:
    """Soft-delete a machine."""
    m = get_machine(machine_id)
    if not m:
        raise ValueError("Machine not found.")
    m.soft_delete()
    db.session.commit()


# ------------------------------------------------------------------
# Aliases
# ------------------------------------------------------------------
def _safe_add_alias(machine: Machine, alias: str) -> MachineAlias | None:
    alias = (alias or "").strip()
    if not alias:
        return None
    # skip duplicate on same machine (case-insensitive)
    existing = next(
        (a for a in machine.aliases if a.alias.lower() == alias.lower()),
        None,
    )
    if existing:
        return existing
    a = MachineAlias(machine_id=machine.id, alias=alias, alias_type="KEYWORD")
    db.session.add(a)
    return a


def add_alias(machine_id: int, alias: str, alias_type: str = "KEYWORD") -> MachineAlias:
    m = get_machine(machine_id)
    if not m:
        raise ValueError("Machine not found.")
    alias = (alias or "").strip()
    if not alias:
        raise ValueError("Alias cannot be empty.")

    existing = next(
        (a for a in m.aliases if a.alias.lower() == alias.lower()),
        None,
    )
    if existing:
        raise ValueError(f"Alias '{alias}' already exists for this machine.")

    a = MachineAlias(machine_id=m.id, alias=alias, alias_type=alias_type or "KEYWORD")
    db.session.add(a)
    db.session.commit()
    return a


def remove_alias(alias_id: int) -> None:
    a = db.session.get(MachineAlias, alias_id)
    if not a:
        raise ValueError("Alias not found.")
    db.session.delete(a)
    db.session.commit()


# ------------------------------------------------------------------
# Search (deterministic)
# ------------------------------------------------------------------
def search_machines_in_shop(
    shop_id: int, query: str, limit: int = 30
) -> list[Machine]:
    """
    Deterministic search by name/model/unit/alias within a shop.
    Strict shop scope. No fallback to other shops.
    """
    q = (query or "").strip()
    if not q:
        return list_machines(shop_id=shop_id)

    like = f"%{q.lower()}%"

    # Machine name / model / unit
    name_hits = (
        Machine.query.filter(
            Machine.shop_id == shop_id,
            Machine.is_deleted.is_(False),
            or_(
                db.func.lower(Machine.name).like(like),
                db.func.lower(db.func.coalesce(Machine.model, "")).like(like),
                db.func.lower(db.func.coalesce(Machine.unit, "")).like(like),
            ),
        )
        .limit(limit)
        .all()
    )

    # Alias hits
    alias_hits = (
        db.session.query(Machine)
        .join(MachineAlias, MachineAlias.machine_id == Machine.id)
        .filter(
            Machine.shop_id == shop_id,
            Machine.is_deleted.is_(False),
            db.func.lower(MachineAlias.alias).like(like),
        )
        .limit(limit)
        .all()
    )

    # Deduplicate, preserve order
    seen: set[int] = set()
    out: list[Machine] = []
    for m in name_hits + alias_hits:
        if m.id in seen:
            continue
        seen.add(m.id)
        out.append(m)
    return out
