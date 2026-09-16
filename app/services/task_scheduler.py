"""
Task Scheduler — Background thread (60s loop)
- Check due tasks
- Send Telegram reminders
- Record task_history
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime

log = logging.getLogger(__name__)


# ★ Global app reference (set by start_scheduler)
_app = None


def start_scheduler(app=None) -> None:
    """Start background scheduler thread with app context."""
    global _app
    if app is None:
        try:
            from flask import current_app
            _app = current_app._get_current_object()
        except Exception:
            _app = None
    else:
        _app = app

    t = threading.Thread(target=_loop, daemon=True, name="task-scheduler")
    t.start()
    log.info("✓ Task scheduler started (app=%s)", _app is not None)


def _loop() -> None:
    log.info("Scheduler loop running (60s interval)")
    time.sleep(15)  # Initial delay
    while True:
        try:
            if _app is not None:
                with _app.app_context():
                    _check_and_notify()
                    _cleanup_old_messages()   # ★ 5 min cleanup
            else:
                _check_and_notify()
                _cleanup_old_messages()
        except Exception as e:
            log.exception("Scheduler error: %s", e)
        time.sleep(60)


def _check_and_notify() -> None:
    from app.extensions import db
    from app.models.task import Task, TaskHistory

    now = datetime.now()
    today = now.date()

    tasks = Task.query.filter(
        Task.is_deleted.is_(False),
        Task.status.in_(["PENDING", "IN_PROGRESS"]),
    ).all()

    sent = 0
    for task in tasks:
        try:
            if not _is_due(task, now):
                continue

            # Already sent today?
            existing = TaskHistory.query.filter(
                TaskHistory.task_id == task.id,
                db.func.date(TaskHistory.created_at) == today,
                TaskHistory.status == "SENT",
            ).first()
            if existing:
                continue

            _send_reminder(task, now)

            hist = TaskHistory(
                task_id=task.id,
                status="SENT",
                note=f"Auto reminder at {now.strftime('%H:%M')}",
            )
            db.session.add(hist)
            db.session.commit()
            sent += 1
            log.info("📢 Task reminder #%d: %s", task.id, task.title[:50])
        except Exception as e:
            db.session.rollback()
            log.warning("Reminder failed task #%d: %s", task.id, e)

    if sent:
        log.info("Scheduler: %d reminders sent", sent)


def _is_due(task, now: datetime) -> bool:
    """Task due now?"""
    if not task.task_time:
        return False

    try:
        hh, mm = map(int, task.task_time.split(":"))
    except (ValueError, AttributeError):
        return False

    task_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    delta = (now - task_dt).total_seconds()

    # Not yet due (allow 1 min early)
    if delta < -60:
        return False
    # Too late (30 min window — catch-up)
    if delta > 1800:
        return False
    # Within 30 min — due ✅

    freq = (task.frequency or "").upper()

    if freq == "DAILY":
        return True
    if freq == "WEEKLY":
        return task.weekday is not None and now.weekday() == task.weekday
    if freq == "MONTHLY":
        return task.day_of_month is not None and now.day == task.day_of_month
    if freq == "YEARLY":
        return (task.month == now.month
                and task.day_of_month is not None
                and now.day == task.day_of_month)
    if freq == "ONE_TIME":
        if not task.specific_date:
            return False
        try:
            return now.date() == task.specific_date
        except Exception:
            return False
    return False


def _cleanup_old_messages() -> None:
    """Delete SENT messages older than 5 min (user no action)."""
    from app.extensions import db
    from app.models.task import TaskHistory
    from app.telegram.client import _api_url, _post_with_retry
    from datetime import datetime, timedelta
    from sqlalchemy import text as _sql

    cutoff = datetime.now() - timedelta(minutes=5)

    olds = TaskHistory.query.filter(
        TaskHistory.status == "SENT",
        TaskHistory.created_at < cutoff,
        TaskHistory.message_id.isnot(None),
        TaskHistory.chat_id.isnot(None),
        TaskHistory.is_deleted == False,  # noqa: E712
    ).all()

    deleted = 0
    for h in olds:
        try:
            r = _post_with_retry(
                _api_url("deleteMessage"),
                json={"chat_id": h.chat_id, "message_id": h.message_id},
                timeout=10,
            )
            if r.status_code == 200 and r.json().get("ok"):
                # Mark as deleted (soft)
                h.is_deleted = True
                h.deleted_at = datetime.now()
                db.session.commit()
                deleted += 1
        except Exception as e:
            log.warning("delete failed msg=%s: %s", h.message_id, e)

    if deleted:
        log.info("🧹 Cleanup: %d old messages deleted", deleted)


def _send_reminder(task, now: datetime) -> None:
    """Send Telegram reminder to shop group/topic + assigned user."""
    from app.telegram.client import _api_url, _post_with_retry
    from app.models import Shop, TelegramGroupConfig
    from app.extensions import db

    shop = Shop.query.get(task.shop_id) if task.shop_id else None
    shop_code = shop.code if shop else "—"

    prio_emoji = {"LOW": "🟢", "NORMAL": "🔵", "HIGH": "🟠", "URGENT": "🔴"}
    emoji = prio_emoji.get(task.priority, "🔵")

    text = (
        f"🔔 <b>Task Reminder</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 <b>{task.title}</b>\n"
        f"🏪 Shop: <b>{shop_code}</b>\n"
        f"⏰ {task.task_time} · {task.describe_schedule()}\n"
        f"{emoji} {task.priority}\n"
    )
    if task.description:
        text += f"\n{task.description}\n"

    kb = {
        "inline_keyboard": [[
            {"text": "✅ Complete", "callback_data": f"task|complete|{task.id}"},
            {"text": "⏭️ Skip", "callback_data": f"task|skip|{task.id}"},
        ]]
    }

    # ★ A3 shop users (via telegram_user_shops)
    from app.models import TelegramUser, TelegramUserShop
    SKIP_TG_IDS = {777000, 1087968824, 136817688}

    shop_users = (
        TelegramUser.query
        .join(TelegramUserShop, TelegramUserShop.telegram_user_id == TelegramUser.id)
        .filter(
            TelegramUserShop.shop_id == task.shop_id,
            TelegramUserShop.is_active == True,      # noqa: E712
            TelegramUserShop.is_deleted == False,    # noqa: E712
            TelegramUser.is_verified == True,        # noqa: E712
            TelegramUser.is_blocked == False,        # noqa: E712
            TelegramUser.is_deleted == False,        # noqa: E712
        )
        .all()
    )

    for u in shop_users:
        tg_id = u.telegram_user_id
        if not tg_id or tg_id in SKIP_TG_IDS:
            continue
        payload = {
            "chat_id": tg_id,
            "text": text[:4000],
            "parse_mode": "HTML",
            "reply_markup": kb,
        }
        try:
            r = _post_with_retry(_api_url("sendMessage"), json=payload, timeout=15)
            data = r.json() if r.status_code == 200 else {}
            if data.get("ok"):
                any_sent = True
                msg_id = (data.get("result") or {}).get("message_id")
                log.info("→ Reminder DM sent: user=%s (msg=%s)", tg_id, msg_id)
                if msg_id:
                    from app.models.task import TaskHistory as _TH
                    _TH_rec = _TH(
                        task_id=task.id,
                        status="SENT",
                        note=f"DM {tg_id}",
                        message_id=msg_id,
                        chat_id=tg_id,
                    )
                    db.session.add(_TH_rec)
                    db.session.commit()
            else:
                log.warning("DM failed for %s: %s", tg_id, (r.text or "")[:200])
        except Exception as e:
            log.warning("DM exception %s: %s", tg_id, e)
            log.warning("DM exception %s: %s", tg_id, e)

    # Groups (all enabled)
    groups = TelegramGroupConfig.query.filter_by(
        is_enabled=True, is_deleted=False
    ).all()

    any_sent = False
    for g in groups:
        thread_ids = g.allowed_thread_ids or [None]
        if isinstance(thread_ids, str):
            try:
                thread_ids = json.loads(thread_ids)
            except Exception:
                thread_ids = [None]
        if not thread_ids:
            thread_ids = [None]

        for tid in thread_ids:
            payload = {
                "chat_id": g.chat_id,
                "text": text[:4000],
                "parse_mode": "HTML",
                "reply_markup": kb,
            }
            if tid:
                payload["message_thread_id"] = tid
            try:
                r = _post_with_retry(_api_url("sendMessage"), json=payload, timeout=15)
                data = r.json() if r.status_code == 200 else {}
                if data.get("ok"):
                    any_sent = True
                    msg_id = (data.get("result") or {}).get("message_id")
                    log.info("→ Reminder sent: chat=%s thread=%s (msg=%s)", g.chat_id, tid, msg_id)
                    # ★ Save message_id in history
                    if msg_id:
                        from app.models.task import TaskHistory as _TH
                        _TH(
                            task_id=task.id,
                            status="SENT",
                            note=f"Group {g.chat_id}",
                            message_id=msg_id,
                            chat_id=g.chat_id,
                        )
                        db.session.add(_TH())
                        db.session.commit()
            except Exception as e:
                log.warning("Send failed: %s", e)

    if not any_sent:
        log.warning("Task #%d — no group/user recipient", task.id)
