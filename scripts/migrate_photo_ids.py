"""
Pre-upload existing knowledge photos to Telegram to cache their file_id.

Usage:
    python -m scripts.migrate_photo_ids

Requires: TELEGRAM_BOT_TOKEN set.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.models import KnowledgePhoto, TelegramUser  # noqa: E402


def main() -> int:
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return 1

    app = create_app()
    with app.app_context():
        # Get any verified Telegram user's chat_id (our bot admin)
        tg = TelegramUser.query.filter_by(is_verified=True).first()
        if not tg:
            print("❌ No verified Telegram user — add one first")
            return 1

        chat_id = tg.telegram_user_id
        print(f"→ Uploading to chat {chat_id} ({tg.first_name})")

        from app.telegram import client as tg_client

        pending = KnowledgePhoto.query.filter(
            KnowledgePhoto.is_deleted.is_(False),
            KnowledgePhoto.telegram_file_id.is_(None),
        ).all()

        print(f"→ {len(pending)} photos need file_id")

        ok = 0
        fail = 0
        for i, p in enumerate(pending, 1):
            if not p.file_path or not Path(p.file_path).exists():
                fail += 1
                continue
            r = tg_client.upload_photo_get_file_id(
                chat_id, p.file_path, caption="[cache]",
            )
            if r.get("ok") and r.get("file_id"):
                p.telegram_file_id = r["file_id"]
                from app.extensions import db
                db.session.commit()
                ok += 1
                print(f"  {i}/{len(pending)}: OK (id={p.id})")
            else:
                fail += 1
                print(f"  {i}/{len(pending)}: FAIL — {r.get('error')}")
            time.sleep(0.5)   # rate-limit

        print(f"\n✓ Done. OK={ok}, FAIL={fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
