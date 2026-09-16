"""
Bootstrap the initial SUPER_ADMIN account.

Reads INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD / INITIAL_ADMIN_EMAIL
from the environment (or .env).

Usage:
    python -m scripts.create_admin

If the username already exists, the script will NOT overwrite the
password. It will print a warning instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Role, User  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        username = (os.getenv("INITIAL_ADMIN_USERNAME") or "").strip()
        password = os.getenv("INITIAL_ADMIN_PASSWORD") or ""
        email = (os.getenv("INITIAL_ADMIN_EMAIL") or "").strip() or None

        if not username or not password:
            print(
                "ERROR: INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be set in .env",
                file=sys.stderr,
            )
            return 1

        if len(password) < 8:
            print("ERROR: INITIAL_ADMIN_PASSWORD must be at least 8 characters.", file=sys.stderr)
            return 1

        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"⚠ User '{username}' already exists. Nothing changed.")
            print(f"  Role: {existing.role}")
            return 0

        user = User(
            username=username,
            email=email,
            full_name="System Administrator",
            role=Role.SUPER_ADMIN,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        print(f"✓ Super admin created: {username}")
        print("  Please log in and change the password immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
