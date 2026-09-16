"""
Reset a user's password.

Usage:
    python -m scripts.reset_password <username> <new_password>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python -m scripts.reset_password <username> <new_password>")
        return 1
    username, new_password = argv[1], argv[2]
    if len(new_password) < 8:
        print("❌ Password must be at least 8 characters.")
        return 1

    app = create_app()
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        if not u:
            print(f"❌ User not found: {username}")
            return 1
        u.set_password(new_password)
        u.failed_login_count = 0
        u.locked_until = None
        u.is_active = True
        db.session.commit()
        print(f"✓ Password reset for '{username}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
