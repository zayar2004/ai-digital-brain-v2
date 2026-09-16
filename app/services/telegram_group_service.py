"""Telegram group config service."""

from __future__ import annotations

from app.extensions import db
from app.models import TelegramGroupConfig
from app.services import audit_service


def get_by_chat_id(chat_id: int) -> TelegramGroupConfig | None:
    return TelegramGroupConfig.query.filter_by(chat_id=int(chat_id)).first()


def list_groups(only_enabled: bool = False) -> list[TelegramGroupConfig]:
    q = TelegramGroupConfig.query.filter_by(is_deleted=False)
    if only_enabled:
        q = q.filter_by(is_enabled=True)
    return q.order_by(TelegramGroupConfig.id.desc()).all()


def register_or_update(
    *,
    chat_id: int,
    title: str | None = None,
    chat_type: str | None = None,
    allowed_thread_ids: list[int] | None = None,
) -> TelegramGroupConfig:
    cfg = get_by_chat_id(chat_id)
    if not cfg:
        cfg = TelegramGroupConfig(
            chat_id=int(chat_id),
            title=(title or "").strip() or None,
            chat_type=chat_type,
            is_enabled=True,
        )
        db.session.add(cfg)

    if title:
        cfg.title = title.strip()[:255]
    if chat_type:
        cfg.chat_type = chat_type

    if allowed_thread_ids is not None:
        cfg.set_threads(allowed_thread_ids)

    db.session.commit()
    return cfg


def set_enabled(chat_id: int, enabled: bool) -> TelegramGroupConfig | None:
    cfg = get_by_chat_id(chat_id)
    if not cfg:
        return None
    cfg.is_enabled = bool(enabled)
    db.session.commit()
    audit_service.log(
        "telegram_group.enable" if enabled else "telegram_group.disable",
        entity_type="telegram_group", entity_id=cfg.id,
        details={"chat_id": chat_id},
    )
    return cfg


def set_options(
    *,
    chat_id: int,
    allowed_thread_ids: list[int] | None = None,
    reply_in_thread: bool | None = None,
    require_mention: bool | None = None,
) -> TelegramGroupConfig | None:
    cfg = get_by_chat_id(chat_id)
    if not cfg:
        return None
    if allowed_thread_ids is not None:
        cfg.set_threads(allowed_thread_ids)
    if reply_in_thread is not None:
        cfg.reply_in_thread = bool(reply_in_thread)
    if require_mention is not None:
        cfg.require_mention = bool(require_mention)
    db.session.commit()
    return cfg


def remove(chat_id: int) -> bool:
    cfg = get_by_chat_id(chat_id)
    if not cfg:
        return False
    cfg.soft_delete()
    db.session.commit()
    return True


def bump_stats(chat_id: int) -> None:
    """Increment message count + update last_message_at."""
    from app.models.base import utcnow
    cfg = get_by_chat_id(chat_id)
    if not cfg:
        return
    cfg.message_count = (cfg.message_count or 0) + 1
    cfg.last_message_at = utcnow()
    db.session.commit()


def check_and_get_config(chat_id: int) -> TelegramGroupConfig | None:
    """Return config if enabled, else None."""
    cfg = get_by_chat_id(chat_id)
    if not cfg or not cfg.is_enabled or cfg.is_deleted:
        return None
    return cfg


def parse_group_link(link: str) -> tuple[int | None, int | None]:
    """
    Parse Telegram message link → (chat_id, thread_id).

    Example: https://t.me/c/1234567890/5
    Returns: (-1001234567890, 5)
    """
    import re
    link = (link or "").strip()
    m = re.match(r"^https?://t\.me/c/(\d+)(?:/(\d+))?/?$", link)
    if not m:
        # Maybe just numeric chat_id
        if re.match(r"^-?\d+$", link):
            return int(link), None
        return None, None
    raw_id = m.group(1)
    thread = int(m.group(2)) if m.group(2) else None
    chat_id = int("-100" + raw_id)
    return chat_id, thread
