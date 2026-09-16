"""
Telegram bot — library-free long polling with group support.
"""

from __future__ import annotations

import logging
import time

from app.config import Config
from app.telegram import handlers

log = logging.getLogger(__name__)


def _command_of(text: str) -> str | None:
    if not text or not text.startswith("/"):
        return None
    cmd = text[1:].split()[0].lower()
    if "@" in cmd:
        cmd = cmd.split("@", 1)[0]
    return cmd


def run_polling() -> None:
    if not Config.TELEGRAM_ENABLED:
        raise RuntimeError("Telegram is disabled.")
    if not Config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

    log.info("Starting Telegram bot (library-free polling)...")

    offset: int | None = None

    while True:
        try:
            updates = handlers.get_updates(offset=offset, timeout=30)
        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
            return
        except Exception as e:
            log.error("getUpdates error: %s", e)
            time.sleep(3)
            continue

        for upd in updates:
            offset = upd.get("update_id", 0) + 1

            # --- Callback query (inline button) ---
            cb = upd.get("callback_query")
            if cb:
                try:
                    handlers.handle_callback(cb)
                except Exception as e:
                    log.exception("callback failed: %s", e)
                continue

            # --- Message ---
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue

            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            from_user = msg.get("from") or {}
            tg_id = from_user.get("id")
            if not chat_id or not tg_id:
                continue

            text = (msg.get("text") or "").strip()
            if not text:
                continue

            # ★ DEBUG
            import json as _json
            log.info("MSG chat=%s type=%s thread=%s text=%r",
                     chat.get("id"), chat.get("type"),
                     msg.get("message_thread_id"), text[:50])
            log.info("RAW CHAT: %s", _json.dumps(chat)[:300])

            tg_username = from_user.get("username")
            first_name = from_user.get("first_name")
            last_name = from_user.get("last_name")
            chat_type = (chat.get("type") or "private")
            thread_id = msg.get("message_thread_id")
            title = chat.get("title")

            try:
                cmd = _command_of(text)

                # ---------- /setup in group ----------
                if cmd == "setup" and chat_type in ("group", "supergroup"):
                    reply = handlers.handle_setup_command(
                        chat_id=chat_id,
                        thread_id=thread_id,
                        chat_type=chat_type,
                        title=title,
                        tg_id=tg_id,
                        tg_username=tg_username,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    handlers.send_message(
                        chat_id, reply,
                        message_thread_id=thread_id if thread_id else None,
                    )
                    continue

                # ---------- Group / Supergroup ----------
                if chat_type in ("group", "supergroup"):
                    is_mention = handlers._is_bot_mentioned(text, msg)
                    body, kb = handlers.handle_group_message(
                        chat_id=chat_id,
                        thread_id=thread_id,
                        text=text,
                        tg_id=tg_id,
                        tg_username=tg_username,
                        first_name=first_name,
                        last_name=last_name,
                        is_bot_mentioned=is_mention,
                        message_id=msg.get("message_id"),
                    )
                    if body:
                        handlers.send_message(
                            chat_id, body,
                            reply_markup=kb,
                            message_thread_id=thread_id if thread_id else None,
                        )
                        try:
                            kid = handlers.last_knowledge_id.pop(chat_id, None)
                            if kid:
                                handlers._send_knowledge_photos(
                                    chat_id, kid,
                                    message_thread_id=thread_id if thread_id else None,
                                )
                        except Exception:
                            pass
                    continue

                # ---------- Private chat ----------
                if cmd:
                    reply = handlers.handle_command(
                        cmd, text, chat_id, tg_id,
                        tg_username, first_name, last_name,
                    )
                    if isinstance(reply, tuple):
                        body, kb = reply
                    else:
                        body, kb = reply, None
                    if body:
                        handlers.send_message(chat_id, body, reply_markup=kb)

                        # ★ Live activity log
                        try:
                            from app.services.activity_log import log_activity
                            _act_type = "command" if text.startswith("/") else "message"
                            _shop = None
                            import re as _re
                            _m = _re.match(r"^(A\d{1,2})\b", text)
                            if _m:
                                _shop = _m.group(1)
                            log_activity(
                                telegram_user_id=tg_id,
                                first_name=first_name,
                                shop_code=_shop,
                                activity_type=_act_type,
                                content=text,
                                response=body,
                                chat_id=chat_id,
                                thread_id=thread_id,
                            )
                        except Exception:
                            pass
                else:
                    result = handlers.handle_text(
                        text, chat_id, tg_id,
                        tg_username, first_name, last_name,
                    )
                    if isinstance(result, tuple):
                        body, kb = result
                    else:
                        body, kb = result, None
                    if body:
                        handlers.send_message(chat_id, body, reply_markup=kb)

                        # ★ Live activity log
                        try:
                            from app.services.activity_log import log_activity
                            _act_type = "command" if text.startswith("/") else "message"
                            _shop = None
                            import re as _re
                            _m = _re.match(r"^(A\d{1,2})\b", text)
                            if _m:
                                _shop = _m.group(1)
                            log_activity(
                                telegram_user_id=tg_id,
                                first_name=first_name,
                                shop_code=_shop,
                                activity_type=_act_type,
                                content=text,
                                response=body,
                                chat_id=chat_id,
                                thread_id=thread_id,
                            )
                        except Exception:
                            pass
                        try:
                            kid = handlers.last_knowledge_id.get(chat_id)
                            if kid:
                                handlers._send_knowledge_photos(
                                    chat_id, kid,
                                    message_thread_id=thread_id if thread_id else None,
                                )
                                handlers.last_knowledge_id.pop(chat_id, None)
                        except Exception:
                            pass
            except Exception as e:
                log.exception("handle failed: %s", e)
                try:
                    handlers.send_message(chat_id, "⚠️ Internal error.")
                except Exception:
                    pass
