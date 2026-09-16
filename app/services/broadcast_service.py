"""
Admin Broadcast service.

- Create a draft
- Load recipients (verified Telegram users)
- Send via Telegram bot API (text or photo)
- Track per-recipient status
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from flask_login import current_user
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Broadcast,
    BroadcastPhoto,
    BroadcastRecipient,
    BroadcastStatus,
    RecipientStatus,
    TelegramUser,
    TelegramUserShop,
)
from app.services import audit_service, file_service
from app.telegram import client as tg_client

log = logging.getLogger(__name__)


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


# ----------------------------------------------------------------
# Recipients
# ----------------------------------------------------------------
def get_recipients(shop_id: int | None = None) -> list[TelegramUser]:
    """Return verified (non-blocked) Telegram users. Optional shop filter."""
    q = TelegramUser.query.filter(
        TelegramUser.is_deleted.is_(False),
        TelegramUser.is_verified.is_(True),
        TelegramUser.is_blocked.is_(False),
    )
    if shop_id:
        # Join through TelegramUserShop
        q = q.join(
            TelegramUserShop,
            TelegramUserShop.telegram_user_id == TelegramUser.id,
        ).filter(
            TelegramUserShop.shop_id == shop_id,
            TelegramUserShop.is_active.is_(True),
        )
    return q.all()


def preview_recipients(shop_id: int | None = None) -> dict:
    """Return counts for the preview UI."""
    all_users = get_recipients(shop_id=None)
    filtered = get_recipients(shop_id=shop_id) if shop_id else all_users
    return {
        "total": len(all_users),
        "filtered": len(filtered),
        "shop_id": shop_id,
    }


# ----------------------------------------------------------------
# Create + send
# ----------------------------------------------------------------
MAX_BROADCAST_PHOTOS = 10


def create_broadcast(
    *,
    message: str | None,
    photos: list = None,          # list of FileStorage
    shop_id: int | None = None,
) -> Broadcast:
    message = (message or "").strip()
    photos = photos or []
    # Filter valid photos
    photos = [f for f in photos if f and getattr(f, "filename", "")]

    if not message and not photos:
        raise ValueError("စာ ဒါမှမဟုတ် ပုံ တစ်ခုခု ထည့်ပါ။")

    if len(photos) > MAX_BROADCAST_PHOTOS:
        photos = photos[:MAX_BROADCAST_PHOTOS]

    b = Broadcast(
        message=message or None,
        has_photo=bool(photos),
        filter_shop_id=shop_id,
        status=BroadcastStatus.DRAFT,
        sent_by_id=_current_user_id(),
    )
    db.session.add(b)
    db.session.flush()

    # Save each photo
    for i, f in enumerate(photos, start=1):
        try:
            meta = file_service.save_upload(f, category="image")
            bp = BroadcastPhoto(
                broadcast_id=b.id,
                file_path=meta["file_path"],
                original_filename=meta["original_filename"],
                mime_type=meta.get("mime_type"),
                size_bytes=meta.get("size_bytes"),
                position=i,
            )
            db.session.add(bp)
        except Exception as e:
            log.warning("broadcast photo save failed: %s", e)

    db.session.commit()
    audit_service.log(
        "broadcast.create",
        entity_type="broadcast",
        entity_id=b.id,
        details={"has_photo": bool(photos), "photos": len(photos)},
    )
    return b



def send_broadcast(broadcast_id: int) -> dict:
    """Send broadcast to all matching recipients (text or album of ≤10 photos)."""
    b = db.session.get(Broadcast, broadcast_id)
    if not b:
        raise ValueError("Broadcast not found.")
    if b.status == BroadcastStatus.SENT:
        return {"ok": True, "already_sent": True, "sent": b.sent_count}

    recipients_users = get_recipients(shop_id=b.filter_shop_id)
    b.status = BroadcastStatus.SENDING
    b.recipient_count = len(recipients_users)
    b.sent_count = 0
    b.failed_count = 0
    db.session.commit()

    photo_rows = [p for p in b.photos_rel if p.file_path]

    # Pre-upload photos once (to get file_ids) — speeds up repeated sends
    if photo_rows:
        admin_chat = _first_admin_chat_id()
        if admin_chat:
            for p in photo_rows:
                if p.telegram_file_id:
                    continue
                try:
                    from app.telegram.client import (
                        upload_photo_get_file_id, delete_message,
                    )
                    r = upload_photo_get_file_id(
                        admin_chat, p.file_path, caption="[broadcast upload]"
                    )
                    if r.get("ok") and r.get("file_id"):
                        p.telegram_file_id = r["file_id"]
                        db.session.commit()
                        # ★ Auto-delete the upload notification from admin DM
                        msg_id = r.get("message_id")
                        if msg_id:
                            try:
                                delete_message(admin_chat, msg_id)
                            except Exception as _e:
                                log.warning("admin upload cleanup failed: %s", _e)
                except Exception as e:
                    log.warning("pre-upload failed: %s", e)

    sent = 0
    failed = 0

    for tu in recipients_users:
        row = BroadcastRecipient(
            broadcast_id=b.id,
            telegram_user_id=tu.telegram_user_id,
            telegram_display_name=(
                f"{tu.first_name or ''} {tu.last_name or ''}".strip()
                or (f"@{tu.telegram_username}" if tu.telegram_username else None)
            ),
            status=RecipientStatus.PENDING,
        )
        db.session.add(row)
        db.session.flush()

        try:
            resp = _send_to_recipient(b, photo_rows, tu.telegram_user_id)
            if resp.get("ok"):
                row.status = RecipientStatus.SENT
                row.sent_at = datetime.now(timezone.utc)
                sent += 1
            else:
                row.status = RecipientStatus.FAILED
                row.error = (resp.get("description") or resp.get("error") or "unknown")[:500]
                failed += 1
        except Exception as e:
            row.status = RecipientStatus.FAILED
            row.error = str(e)[:500]
            failed += 1

        db.session.commit()
        time.sleep(0.05)

    b.sent_count = sent
    b.failed_count = failed
    if failed == 0:
        b.status = BroadcastStatus.SENT
    elif sent == 0:
        b.status = BroadcastStatus.FAILED
    else:
        b.status = BroadcastStatus.PARTIAL
    b.sent_at = datetime.now(timezone.utc)
    db.session.commit()

    audit_service.log(
        "broadcast.send",
        entity_type="broadcast",
        entity_id=b.id,
        details={"sent": sent, "failed": failed, "total": len(recipients_users)},
    )
    # ★ Send to groups (with their configured topic threads)
    from app.models import TelegramGroupConfig as _TGC
    import json as _json

    groups = _TGC.query.filter_by(is_enabled=True, is_deleted=False).all()
    groups_sent = 0
    groups_failed = 0
    for g in groups:
        thread_ids = g.allowed_thread_ids or []
        if isinstance(thread_ids, str):
            try:
                thread_ids = _json.loads(thread_ids)
            except Exception:
                thread_ids = []
        if not thread_ids:
            thread_ids = [None]

        for tid in thread_ids:
            display = f"{g.title or ''} (thread {tid})" if tid else (g.title or "")
            row = BroadcastRecipient(
                broadcast_id=b.id,
                telegram_user_id=g.chat_id,
                telegram_display_name=display[:255],
                status=RecipientStatus.PENDING,
            )
            db.session.add(row)
            db.session.flush()
            try:
                resp = _send_to_recipient(b, photo_rows, g.chat_id,
                                          message_thread_id=tid)
                if resp.get("ok"):
                    row.status = RecipientStatus.SENT
                    row.sent_at = datetime.now(timezone.utc)
                    sent += 1
                    groups_sent += 1
                else:
                    row.status = RecipientStatus.FAILED
                    row.error = (resp.get("description") or resp.get("error") or "unknown")[:500]
                    failed += 1
                    groups_failed += 1
            except Exception as e:
                row.status = RecipientStatus.FAILED
                row.error = str(e)[:500]
                failed += 1
                groups_failed += 1

    b.sent_count = sent
    b.failed_count = failed
    db.session.commit()

    return {"ok": True, "sent": sent, "failed": failed,
            "total": len(recipients_users) + groups_sent + groups_failed}


def _send_to_recipient(b: Broadcast, photo_rows: list, chat_id: int,
                       message_thread_id: int | None = None) -> dict:
    """Send text OR album depending on photos, optionally to a topic thread."""
    from app.telegram.client import (
        send_media_group_with_cache, send_media_group_by_file_ids,
        send_photo_by_file_id, send_photo_via_file,
    )
    from app.telegram.handlers import send_message

    caption = (b.message or "")[:1000]

    # No photo → text only
    if not photo_rows:
        return send_message(chat_id, b.message or "", parse_mode="",
                            message_thread_id=message_thread_id)

    # Multiple photos → album
    if len(photo_rows) > 1:
        # If all cached → instant
        fids = [p.telegram_file_id for p in photo_rows if p.telegram_file_id]
        if len(fids) == len(photo_rows):
            return send_media_group_by_file_ids(chat_id, fids, caption=caption,
                                                message_thread_id=message_thread_id)

        # Else → fall back to generic album with cache (multipart)
        class _P:
            def __init__(self, row):
                self.id = row.id
                self.file_path = row.file_path
                self.telegram_file_id = row.telegram_file_id

        wrapper = [_P(r) for r in photo_rows]

        def _save(pid, fid):
            try:
                db.session.execute(
                    db.text("UPDATE broadcast_photos SET telegram_file_id = :f WHERE id = :i"),
                    {"f": fid, "i": pid},
                )
                db.session.commit()
            except Exception:
                db.session.rollback()

        return send_media_group_with_cache(
            chat_id, wrapper, caption=caption, save_callback=_save,
            message_thread_id=message_thread_id,
        )

    # Single photo
    p0 = photo_rows[0]
    if p0.telegram_file_id:
        return send_photo_by_file_id(chat_id, p0.telegram_file_id, caption=caption,
                                     message_thread_id=message_thread_id)
    return send_photo_via_file(chat_id, p0.file_path, caption=caption,
                               message_thread_id=message_thread_id)



def _first_admin_chat_id() -> int | None:
    u = TelegramUser.query.filter_by(is_verified=True, is_blocked=False).first()
    return u.telegram_user_id if u else None


def list_broadcasts(limit: int = 100) -> list[Broadcast]:
    return (
        Broadcast.query
        .filter(Broadcast.is_deleted.is_(False))
        .order_by(Broadcast.id.desc())
        .limit(limit)
        .all()
    )


def get_broadcast(bid: int) -> Broadcast | None:
    return db.session.get(Broadcast, bid)
