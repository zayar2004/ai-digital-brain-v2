"""Activity logger — writes to bot_activity table."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def log_activity(*, telegram_user_id=None, first_name=None,
                 shop_code=None, activity_type=None, content=None,
                 response_ok=True, chat_id=None, thread_id=None,
                 response=None, response_type=None):
    """Insert one activity row. Never raises."""
    try:
        from app.extensions import db
        from app.models.bot_activity import BotActivity

        row = BotActivity(
            telegram_user_id=telegram_user_id,
            first_name=(first_name or "")[:255] or None,
            shop_code=shop_code,
            activity_type=activity_type,
            content=(content or "")[:2000] or None,
            response_ok=response_ok,
            chat_id=chat_id,
            thread_id=thread_id,
            response=(response or "")[:5000] or None,
            response_type=response_type,
        )
        db.session.add(row)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        log.warning("activity log failed: %s", e)
