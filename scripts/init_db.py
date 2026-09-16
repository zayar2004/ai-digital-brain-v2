"""
Initialize the database schema and seed the 13 shops (A1-A13).

Usage:
    python -m scripts.init_db
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python -m scripts.init_db` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Shop  # noqa: E402


def seed_shops() -> tuple[int, int]:
    """Create the A1-A13 shops if missing. Return (created, existing)."""
    created = 0
    existing = 0
    for code in Shop.all_codes():
        shop = Shop.query.filter_by(code=code).first()
        if shop is None:
            db.session.add(Shop(code=code, name=code, is_active=True))
            created += 1
        else:
            existing += 1
    db.session.commit()
    return created, existing


def main() -> int:
    app = create_app()
    with app.app_context():
        print("→ Creating database schema...")
        db.create_all()
        print("  ✓ Schema created.")

        print("→ Seeding shops A1-A13...")
        created, existing = seed_shops()
        print(f"  ✓ Created: {created}, Already existed: {existing}")

        print("→ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
