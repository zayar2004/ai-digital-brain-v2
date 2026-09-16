"""
Seed demo data for testing.

Usage:
    python -m scripts.seed_demo

Safe: checks existing data before creating.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Machine, MachineAlias, MachineCode, Shop, Task,
)


def seed_machines() -> int:
    count = 0
    demos = [
        # A3
        ("A3", "Crocodile Tycoon", "P6", ["Croc", "CT", "Croc Ty"]),
        ("A3", "Marble World", "M1", ["MW", "Marble"]),
        ("A3", "Dragon Blade", "D1", ["DB", "Dragon"]),
        # A5
        ("A5", "Crocodile Tycoon", "P6", ["Croc", "CT"]),
        ("A5", "Dream Castle", "DC1", ["DC", "Dream"]),
        # A7
        ("A7", "Crocodile Tycoon", "P8", ["Croc", "CT"]),
    ]

    for shop_code, name, model, aliases in demos:
        shop = Shop.query.filter_by(code=shop_code).first()
        if not shop:
            continue
        existing = Machine.query.filter_by(shop_id=shop.id, name=name).first()
        if existing:
            continue
        m = Machine(shop_id=shop.id, name=name, model=model, unit=model, status="ACTIVE")
        db.session.add(m)
        db.session.flush()
        for a in aliases:
            db.session.add(MachineAlias(machine_id=m.id, alias=a, alias_type="SHORT"))
        count += 1
    db.session.commit()
    return count


def seed_machine_codes() -> int:
    count = 0
    demos = [
        ("A3", "Crocodile Tycoon", "P6", "CT-P6-015"),
        ("A3", "Crocodile Tycoon", "P7", "CT-P7-016"),
        ("A3", "Crocodile Tycoon", "P8", "CT-P8-017"),
        ("A3", "Marble World", "P1", "MW-P1-100"),
        ("A3", "Dragon Blade", "P1", "DB-P1-200"),
        ("A5", "Crocodile Tycoon", "P6", "CT-P6-500"),
        ("A7", "Crocodile Tycoon", "P8", "CT-P8-700"),
    ]

    for shop_code, machine_name, unit, code in demos:
        shop = Shop.query.filter_by(code=shop_code).first()
        if not shop:
            continue
        existing = MachineCode.query.filter_by(shop_id=shop.id, code=code).first()
        if existing:
            continue
        m = Machine.query.filter_by(shop_id=shop.id, name=machine_name).first()
        db.session.add(MachineCode(
            shop_id=shop.id,
            machine_id=m.id if m else None,
            machine_name=machine_name,
            unit=unit,
            code=code,
            status="APPROVED",
        ))
        count += 1
    db.session.commit()
    return count


def seed_tasks() -> int:
    count = 0
    demos = [
        ("A3", "Daily machine check", "DAILY", None, "09:00"),
        ("A3", "Monday inspection", "WEEKLY", 0, "10:00"),
        ("A3", "Monthly report", "MONTHLY", None, "14:00"),
    ]
    for shop_code, title, freq, weekday, time in demos:
        shop = Shop.query.filter_by(code=shop_code).first()
        if not shop:
            continue
        existing = Task.query.filter_by(shop_id=shop.id, title=title).first()
        if existing:
            continue
        t = Task(
            shop_id=shop.id, title=title, frequency=freq,
            weekday=weekday, task_time=time, status="PENDING",
        )
        if freq == "MONTHLY":
            t.day_of_month = 15
        db.session.add(t)
        count += 1
    db.session.commit()
    return count


def main() -> int:
    app = create_app()
    with app.app_context():
        print("→ Seeding demo data...")
        n = seed_machines()
        print(f"  ✓ Machines: {n} created")
        n = seed_machine_codes()
        print(f"  ✓ Machine codes: {n} created")
        n = seed_tasks()
        print(f"  ✓ Tasks: {n} created")
        print("✓ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
