"""
Create or link a Telegram user to a shop (for testing/onboarding).

Usage:
    python -m scripts.create_telegram_user <telegram_user_id> <shop_code>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Shop, TelegramUser, TelegramUserShop  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python -m scripts.create_telegram_user <tg_user_id> <shop_code>")
        return 1
    try:
        tg_id = int(argv[1])
    except ValueError:
        print("❌ telegram_user_id must be an integer.")
        return 1
    shop_code = argv[2].strip().upper()

    app = create_app()
    with app.app_context():
        shop = Shop.query.filter_by(code=shop_code).first()
        if not shop:
            print(f"❌ Shop not found: {shop_code}")
            return 1

        tu = TelegramUser.query.filter_by(telegram_user_id=tg_id).first()
        if not tu:
            tu = TelegramUser(
                telegram_user_id=tg_id,
                is_verified=True,
            )
            db.session.add(tu)
            db.session.commit()
            print(f"✓ Created TelegramUser id={tu.id} tg_id={tg_id}")
        else:
            tu.is_verified = True
            db.session.commit()
            print(f"ℹ TelegramUser exists id={tu.id}")

        link = TelegramUserShop.query.filter_by(
            telegram_user_id=tu.id, shop_id=shop.id
        ).first()
        if link:
            link.is_active = True
        else:
            link = TelegramUserShop(
                telegram_user_id=tu.id, shop_id=shop.id, is_active=True
            )
            db.session.add(link)
        db.session.commit()
        print(f"✓ Linked to shop {shop.code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
