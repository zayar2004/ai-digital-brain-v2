"""
List all users (admin + telegram).

Usage:
    python -m scripts.list_users
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.models import TelegramUser, TelegramUserShop, User  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("ADMIN USERS (Website)")
        print("=" * 60)
        users = User.query.order_by(User.id).all()
        if not users:
            print("(none)")
        for u in users:
            print(
                f"  #{u.id} {u.username:<20} role={u.role:<12} "
                f"active={u.is_active} locked={u.is_locked()} "
                f"failed={u.failed_login_count}"
            )
        print()

        print("=" * 60)
        print("TELEGRAM USERS")
        print("=" * 60)
        tus = TelegramUser.query.order_by(TelegramUser.id).all()
        if not tus:
            print("(none)")
        for tu in tus:
            links = TelegramUserShop.query.filter_by(
                telegram_user_id=tu.id, is_active=True
            ).all()
            shops = [lk.shop.code for lk in links if lk.shop]
            print(
                f"  #{tu.id} tg_id={tu.telegram_user_id} "
                f"@{tu.telegram_username or '-'} "
                f"name={(tu.first_name or '')} "
                f"verified={tu.is_verified} blocked={tu.is_blocked} "
                f"shops={shops}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
