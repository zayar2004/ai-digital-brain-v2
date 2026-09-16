"""
Unlock a locked admin account.

Usage:
    python -m scripts.unlock_user <username>
    python -m scripts.unlock_user --all
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m scripts.unlock_user <username> | --all")
        return 1
    target = argv[1]

    app = create_app()
    with app.app_context():
        if target == "--all":
            n = User.query.update({
                "failed_login_count": 0,
                "locked_until": None,
            })
            db.session.commit()
            print(f"✓ Unlocked all users ({n} rows)")
            return 0

        u = User.query.filter_by(username=target).first()
        if not u:
            print(f"❌ User not found: {target}")
            return 1
        u.failed_login_count = 0
        u.locked_until = None
        db.session.commit()
        print(f"✓ Unlocked '{target}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
