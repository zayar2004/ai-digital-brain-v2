"""
Telegram bot entry point (library-free).

Run:
    python bot.py

Requires:
    TELEGRAM_ENABLED=true
    TELEGRAM_BOT_TOKEN=<token>
    Backend reachable at TELEGRAM_API_BASE (default http://127.0.0.1:5000)
"""

from __future__ import annotations

import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)


def main() -> int:
    try:
        from app import create_app
        from app.telegram.bot import run_polling
    except Exception as e:
        logging.error("Cannot load bot: %s", e)
        return 1

    _app = create_app()

    # Enter an app context for the lifetime of the bot process
    with _app.app_context():
        try:
            from app.extensions import db
            db.create_all()
        except Exception as e:
            logging.warning("db.create_all skipped: %s", e)

        try:
            run_polling()
        except KeyboardInterrupt:
            logging.info("Bot stopped by user.")
            return 0
        except Exception as e:
            logging.exception("Bot crashed: %s", e)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
