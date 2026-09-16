"""Telegram Notification Service — called from Website backend."""

from __future__ import annotations

import logging
import httpx

from app.config import Config

log = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(Config.TELEGRAM_ENABLED and Config.TELEGRAM_BOT_TOKEN)


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/{method}"


def send_message(chat_id: int, text: str, *, parse_mode: str = "HTML",
                 disable_web_page_preview: bool = True) -> dict:
    if not is_enabled():
        return {"ok": False, "error": "telegram_not_configured"}
    try:
        payload = {"chat_id": chat_id, "text": text[:4000],
                   "disable_web_page_preview": disable_web_page_preview}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        r = httpx.post(
            _api_url("sendMessage"),
            json=payload,
            timeout=15,
        )
        return r.json()
    except Exception as e:
        log.warning("send_message failed: %s", e)
        return {"ok": False, "error": str(e)}


def _esc(s) -> str:
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def notify_link_success(*, chat_id: int, shop_codes: list[str],
                        full_name: str | None = None) -> dict:
    shops = ", ".join(f"<code>{_esc(c)}</code>" for c in shop_codes) or "—"
    greeting = f"မင်္ဂလာပါ {_esc(full_name)}!" if full_name else "မင်္ဂလာပါ!"
    text = (
        f"✅ <b>{greeting}</b>\n\n"
        f"သင့် Telegram account ကို အောက်ပါဆိုင်တွေနဲ့ ချိတ်ဆက်ပြီးပါပြီ:\n\n"
        f"🏪 {shops}\n\n"
        "📱 <b>အခု သင်လုပ်နိုင်တာများ:</b>\n"
        "• <code>/start</code> — Bot ကို စတင်\n"
        "• <code>/shop</code>  — သင့်ဆိုင် ကြည့်\n"
        "• <code>/today</code> — ဒီနေ့ Task ကြည့်\n"
        "• <code>A3 CT code</code> — Machine Code ရှာ\n"
        "• <code>Carnival Circus P3 Error 07</code> — Error မေး\n\n"
        "⚠️ သင်ရိုက်တဲ့ ဆိုင်ကုဒ် မပါရင် verified ဆိုင်ထဲကပဲ ရှာပါမယ်။\n\n"
        "❓ အကူအညီ: <code>/help</code>"
    )
    return send_message(chat_id, text)


def notify_unlink(*, chat_id: int, shop_code: str) -> dict:
    text = (f"⚠️ <b>ချိတ်ဆက်မှု ဖျက်ပြီးပါပြီ</b>\n\n"
            f"<code>{_esc(shop_code)}</code> ဆိုင်နဲ့ ချိတ်ဆက်မှု ဖျက်လိုက်ပါပြီ။")
    return send_message(chat_id, text)


def notify_verify(*, chat_id: int) -> dict:
    return send_message(chat_id, "✅ <b>Verified</b>\n\nသင့် account ကို verified သတ်မှတ်ပြီးပါပြီ။")


def notify_block(*, chat_id: int) -> dict:
    return send_message(chat_id, "🚫 <b>သင့် account ကို ပိတ်ထားပါတယ်</b>")


def notify_unblock(*, chat_id: int) -> dict:
    return send_message(chat_id, "✅ <b>သင့် account ကို ပြန်ဖွင့်ပြီးပါပြီ</b>")
