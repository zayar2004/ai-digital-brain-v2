"""
Telegram handlers — library-free + inline buttons + pagination.

Data flow:
  1. Resolve shop (explicit → verified → context)
  2. Route by intent:
       - code query → MachineCode search
       - error code (exact) → direct ErrorKnowledge
       - error keyword → Error list (paginated)
       - general → Knowledge search
  3. Reply with inline keyboard where useful
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import Any

import httpx

from app.config import Config
from app.extensions import db
from app.models import TelegramUser, TelegramUserShop
from app.security.shop_scope import normalize_shop_code
from app.telegram.client import BackendClient

# Module-level state: last matched knowledge per chat (for photo album hook)
last_knowledge_id: dict = {}


log = logging.getLogger(__name__)

SHOP_TOKEN_RE = re.compile(r"\b([Aa]\s?\d{1,2})\b")
ERROR_CODE_RE = re.compile(r"\b([A-Z]{2,8}(?:-[A-Z0-9]+)*-\d{1,4})\b")

_CONTEXT: dict[int, dict[str, Any]] = {}
_CONTEXT_TTL = 3600

# ★ Last knowledge list — for number reply
_last_list: dict[int, list] = {}
_last_list_time: dict[int, float] = {}
_LAST_LIST_TTL = 1800   # 30 min

PER_PAGE = 10


# ----------------------------------------------------------------
# Telegram API
# ----------------------------------------------------------------
def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/{method}"


def send_message(chat_id: int, text: str, *,
                 parse_mode: str = "HTML",
                 reply_markup: dict | None = None,
                 message_thread_id: int | None = None,
                 disable_web_page_preview: bool = True) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    try:
        from app.telegram import client as _tg
        r = _tg._http_client.post(_api_url("sendMessage"), json=payload, timeout=10)
        return r.json()
    except Exception as e:
        log.error("sendMessage failed: %s", e)
        return {"ok": False, "error": str(e)}


def edit_message(chat_id: int, message_id: int, text: str, *,
                 parse_mode: str = "HTML",
                 reply_markup: dict | None = None) -> dict:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text[:4000],
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        from app.telegram import client as _tg
        r = _tg._http_client.post(_api_url("editMessageText"), json=payload, timeout=10)
        return r.json()
    except Exception as e:
        log.error("editMessage failed: %s", e)
        return {"ok": False, "error": str(e)}


def answer_callback(callback_id: str, text: str = "") -> dict:
    try:
        from app.telegram import client as _tg
        r = _tg._http_client.post(
            _api_url("answerCallbackQuery"),
            json={"callback_query_id": callback_id, "text": text[:200]},
            timeout=8,
        )
        return r.json()
    except Exception as e:
        log.error("answerCallback failed: %s", e)
        return {"ok": False, "error": str(e)}


def delete_message(chat_id: int, message_id: int) -> dict:
    """Delete a Telegram message."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    try:
        from app.telegram import client as _tg
        r = _tg._http_client.post(_api_url("deleteMessage"), json=payload, timeout=10)
        return r.json()
    except Exception as e:
        log.error("deleteMessage failed: %s", e)
        return {"ok": False, "error": str(e)}


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    try:
        # ★ Explicitly allow message + callback_query updates
        import json as _json
        r = httpx.get(
            _api_url("getUpdates"),
            params={
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": _json.dumps(["message", "callback_query", "edited_message"]),
            },
            timeout=timeout + 10,
        )
        data = r.json()
        if not data.get("ok"):
            log.error("getUpdates failed: %s", data)
            return []
        return data.get("result", [])
    except httpx.TimeoutException:
        return []
    except Exception as e:
        log.error("getUpdates exception: %s", e)
        return []


# ----------------------------------------------------------------
# User helpers
# ----------------------------------------------------------------
def _get_or_create_tg_user(tg_id: int, tg_username: str | None,
                           first_name: str | None, last_name: str | None
                           ) -> TelegramUser:
    tu = TelegramUser.query.filter_by(telegram_user_id=tg_id).first()
    if tu is None:
        tu = TelegramUser(
            telegram_user_id=tg_id,
            telegram_username=tg_username,
            first_name=first_name,
            last_name=last_name,
            is_verified=False,
        )
        db.session.add(tu)
        db.session.commit()
    else:
        changed = False
        if tg_username != tu.telegram_username:
            tu.telegram_username = tg_username; changed = True
        if first_name != tu.first_name:
            tu.first_name = first_name; changed = True
        if last_name != tu.last_name:
            tu.last_name = last_name; changed = True
        if changed:
            db.session.commit()
    return tu


def _verified_shop_codes(tg_user: TelegramUser) -> list[str]:
    links = TelegramUserShop.query.filter_by(
        telegram_user_id=tg_user.id, is_active=True
    ).all()
    return [lk.shop.code for lk in links if lk.shop]


def _extract_explicit_shop(text: str) -> str | None:
    m = SHOP_TOKEN_RE.search(text or "")
    if m:
        return normalize_shop_code(m.group(1))
    return None


def _resolve_shop(text: str, tg_user: TelegramUser,
                  chat_id: int) -> tuple[str | None, str]:
    explicit = _extract_explicit_shop(text)
    if explicit:
        _CONTEXT[chat_id] = {"shop": explicit, "ts": time.time()}
        return explicit, "explicit"

    verified = _verified_shop_codes(tg_user)
    if len(verified) == 1:
        _CONTEXT[chat_id] = {"shop": verified[0], "ts": time.time()}
        return verified[0], "verified"

    ctx = _CONTEXT.get(chat_id)
    if ctx and (time.time() - ctx.get("ts", 0)) < _CONTEXT_TTL:
        return ctx.get("shop"), "context"

    return None, "none"


def _esc(s) -> str:
    return html.escape(str(s) if s is not None else "")


# ----------------------------------------------------------------
# Inline keyboards
# ----------------------------------------------------------------
def _error_list_keyboard(shop: str, q: str, page: int, total: int) -> dict | None:
    """Build pagination keyboard for error list."""
    pages = (total + PER_PAGE - 1) // PER_PAGE
    if pages <= 1:
        return None

    row: list[dict] = []
    if page > 1:
        row.append({"text": "◀ Prev", "callback_data": f"err|{shop}|{page-1}|{q or '-'}"})
    row.append({"text": f"{page}/{pages}", "callback_data": "noop"})
    if page < pages:
        row.append({"text": "Next ▶", "callback_data": f"err|{shop}|{page+1}|{q or '-'}"})

    return {"inline_keyboard": [row]}


def _error_detail_keyboard(shop: str, code: str) -> dict:
    """Keyboard for error detail."""
    return {
        "inline_keyboard": [
            [{"text": "📋 All errors", "callback_data": f"err|{shop}|1|-"}],
            [{"text": "❓ Help", "callback_data": f"help|{shop}|0|-"}],
        ]
    }


# ----------------------------------------------------------------
# Formatters
# ----------------------------------------------------------------
def _format_machine_codes(data: dict) -> str:
    matches = (data or {}).get("matches") or []
    shop = (data or {}).get("shop") or ""
    if not matches:
        return "❌ Machine Code မတွေ့ပါ။"
    lines = [f"🔑 <b>Machine Codes</b> · <code>{_esc(shop)}</code>\n"]
    for m in matches[:20]:
        lines.append(
            f"🎮 <b>{_esc(m.get('machine') or '—')}</b>\n"
            f"🏪 {_esc(m.get('shop') or '')}"
            f"{(' · ' + _esc(m.get('unit'))) if m.get('unit') else ''}\n"
            f"🔑 <code>{_esc(m.get('code') or '')}</code>\n"
        )
    if len(matches) > 20:
        lines.append(f"…နောက်ထပ် {len(matches) - 20} ခု")
    return "\n".join(lines)


def _format_error_detail(data: dict) -> str:
    """Format one ErrorKnowledge record (full)."""
    if not data:
        return "❌ မတွေ့ပါ။"
    lines: list[str] = []
    lines.append(f"📌 <b>Machine:</b> {_esc(data.get('machine') or '—')}")
    if data.get("model"):
        lines.append(f"🔧 <b>Model:</b> {_esc(data['model'])}")
    if data.get("unit"):
        lines.append(f"📍 <b>Unit:</b> {_esc(data['unit'])}")
    if data.get("code"):
        lines.append(f"⚠️ <b>Error Code:</b> <code>{_esc(data['code'])}</code>")
    if data.get("name"):
        lines.append(f"📛 <b>Error Name:</b> {_esc(data['name'])}")
    if data.get("symptoms"):
        lines.append(f"\n🩺 <b>Symptoms:</b>\n{_esc(data['symptoms'])}")
    if data.get("cause"):
        lines.append(f"\n🔍 <b>Cause:</b>\n{_esc(data['cause'])}")
    if data.get("check_steps"):
        lines.append(f"\n✅ <b>Check Steps:</b>\n{_esc(data['check_steps'])}")
    if data.get("solution"):
        lines.append(f"\n🔧 <b>ဖြေရှင်းနည်း:</b>\n{_esc(data['solution'])}")
    if data.get("notes"):
        lines.append(f"\n📝 <b>Notes:</b>\n{_esc(data['notes'])}")
    return "\n".join(lines)


def _format_error_list(data: dict) -> str:
    """Format paginated error list."""
    items = (data or {}).get("items") or []
    total = (data or {}).get("total") or 0
    page = (data or {}).get("page") or 1
    shop = (data or {}).get("shop") or ""
    q = (data or {}).get("q") or ""

    if not items:
        return f"❌ <code>{_esc(shop)}</code> မှာ Error Knowledge မတွေ့ပါ။"

    header = f"⚠️ <b>Error Knowledge</b> · <code>{_esc(shop)}</code>"
    if q:
        header += f" · <i>'{_esc(q)}'</i>"
    lines = [header, f"Total: {total}", ""]

    for i, it in enumerate(items, start=(page - 1) * PER_PAGE + 1):
        lines.append(
            f"<b>{i}.</b> <code>{_esc(it.get('code') or '—')}</code>\n"
            f"    {_esc(it.get('name') or '')}"
        )
    lines.append("")
    lines.append("💡 ကုဒ်ကို နှိပ်ပြီး အသေးစိတ် ကြည့်နိုင်ပါတယ် — <code>SDPAO-33</code>")
    return "\n".join(lines)


# ----------------------------------------------------------------
# Direct DB lookup (fallback for short text)
# ----------------------------------------------------------------
def _try_exact_error_code(shop_code: str, code: str) -> str:
    """Try to look up error by exact code — returns formatted HTML or ''."""
    client = BackendClient()
    resp = client.get_error(shop=shop_code, ident=code)
    if not resp.get("success"):
        return ""
    return _format_error_detail(resp.get("data") or {})


def _try_error_keyword(shop_code: str, text: str) -> tuple[str, dict | None]:
    """Search error list by keyword. Returns (html, keyboard)."""
    client = BackendClient()
    resp = client.list_errors(shop=shop_code, q=text, page=1, per=PER_PAGE)
    if not resp.get("success"):
        return "", None
    data = resp.get("data") or {}
    total = data.get("total") or 0
    if total == 0:
        return "", None
    html_out = _format_error_list(data)
    keyboard = _error_list_keyboard(shop_code, text, 1, total)
    return html_out, keyboard


# ----------------------------------------------------------------
# Commands
# ----------------------------------------------------------------
def handle_command(cmd: str, text: str, chat_id: int, tg_id: int,
                   tg_username: str | None, first_name: str | None,
                   last_name: str | None):
    """
    Handle Telegram commands.
    Returns: str OR (str, dict) where dict = reply_markup.
    """
    tu = _get_or_create_tg_user(tg_id, tg_username, first_name, last_name)
    verified = _verified_shop_codes(tu)
    shop, _ = _resolve_shop("", tu, chat_id)

    # ---- /start ----
    if cmd == "start":
        verified_line = (
            f"🏪 Verified: <b>{', '.join(verified)}</b>"
            if verified
            else "⚠️ သင့် account ကို ဆိုင်နဲ့ မချိတ်ရသေးပါ။ Admin ကို ဆက်သွယ်ပါ။"
        )
        text = (
            "🧠 <b>AI Digital Brain</b>\n"
            "\n"
            "မင်္ဂလာပါ! 👋\n"
            "ကျွန်တော် က စက် error + knowledge ကူညီပေးပါမယ်။\n"
            "\n"
            f"{verified_line}\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📖 <b>Knowledge အသုံးပြုနည်း</b>\n"
            "\n"
            "📚 <b>All Knowledge</b> — အောက်မှာ button နှိပ်\n"
            "   ↓ List ပြ → နံပါတ် ရိုက် (1, 2, 3)\n"
            "   ↓ Content + Photo\n"
            "\n"
            "🔍 <b>Error + Knowledge ရှာနည်း</b>\n"
            "   • <code>Demon Tower Error 1</code>  — machine + error\n"
            "   • <code>Error 2</code>               — error code\n"
            "   • <code>Demon Tower</code>           — machine\n"
            "   • <code>Key Write OFF</code>         — knowledge\n"
            "\n"
            "⚙️ <b>Machine Code ရှာနည်း</b>\n"
            "   • <code>A3 CT code</code>            — shop + machine code\n"
            "   • <code>A3 Dragon</code>             — shop + machine name\n"
            "   • <code>12345</code>                 — machine code\n"
            "   → Excel imported code ရှာ — machine info ပြ\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ <b>Commands</b>\n"
            "\n"
            "/help     — အကူအညီ\n"
            "/shop     — သင့် ဆိုင်\n"
            "/today    — ဒီနေ့ tasks\n"
            "/tasks    — tasks အားလုံး\n"
            "/errors   — error list\n"
            "/machine  — machine info\n"
            "/search   — search"
        )
        return (text, _persistent_keyboard())

    # ---- /help ----
    if cmd == "help":
        return (
            "🧠 <b>အကူအညီ</b>\n\n"
            "<b>Commands</b>\n"
            "/start  — စတင်\n"
            "/help   — ဒီစာ\n"
            "/shop   — သင့် verified ဆိုင်\n"
            "/today  — ဒီနေ့ Task\n"
            "/tasks  — Task အားလုံး\n"
            "/errors — Error list (paginated)\n"
            "/machine &lt;name&gt; — Machine info\n"
            "/search &lt;keyword&gt; — Search\n\n"
            "<b>Free text</b>\n"
            "• <code>SDPAO-33</code> — Error code\n"
            "• <code>Dragon Blade error</code> — Keyword\n"
            "• <code>A3 CT code</code> — Machine code\n\n"
            "⚠️ Strict shop isolation."
        )

    # ---- /shop ----
    if cmd == "shop":
        if verified:
            return "🏪 <b>Verified shops:</b>\n" + "\n".join(
                f"• <code>{_esc(s)}</code>" for s in verified
            )
        return "⚠️ သင့် account ကို ဆိုင်နဲ့ မချိတ်ရသေးပါ။ Admin ကို ဆက်သွယ်ပါ။"

    # ---- /today ----
    if cmd == "today":
        if not shop:
            return "ဘယ်ဆိုင်လဲ? (ဥပမာ: <code>A3 /today</code>)"
        client = BackendClient()
        data = client.tasks_today(shop=shop)
        tasks = (data.get("data") or {}).get("tasks") or []
        if not tasks:
            return f"📋 ဒီနေ့ Task မရှိပါ။ (<code>{_esc(shop)}</code>)"
        lines = [f"📋 <b>ဒီနေ့ Tasks</b> · <code>{_esc(shop)}</code>", ""]
        for t in tasks[:20]:
            lines.append(
                f"• <b>{_esc(t.get('title'))}</b>\n"
                f"  {_esc(t.get('schedule'))} · {_esc(t.get('status'))}"
            )
        return "\n".join(lines)

    # ---- /tasks (all) ----
    if cmd == "tasks":
        if not shop:
            return "ဘယ်ဆိုင်လဲ? (ဥပမာ: <code>A3 /tasks</code>)"
        # Show tasks from DB directly for this shop
        from app.models import Task
        from app.services.shop_service import get_shop_by_code
        s_obj = get_shop_by_code(shop)
        if not s_obj:
            return "❌ ဆိုင်မတွေ့ပါ။"
        tasks = Task.query.filter_by(
            shop_id=s_obj.id, is_deleted=False
        ).order_by(Task.id.desc()).limit(20).all()
        if not tasks:
            return f"📋 Task မရှိပါ။ (<code>{_esc(shop)}</code>)"
        lines = [f"📋 <b>Tasks</b> · <code>{_esc(shop)}</code>", ""]
        for t in tasks:
            lines.append(
                f"• <b>{_esc(t.title)}</b>\n"
                f"  {_esc(t.describe_schedule())} · {_esc(t.status)}"
            )
        return "\n".join(lines)

    # ---- /errors (list with pagination) ----
    if cmd == "errors":
        if not shop:
            return "ဘယ်ဆိုင်လဲ? (ဥပမာ: <code>A3 /errors</code>)"
        client = BackendClient()
        resp = client.list_errors(shop=shop, q="", page=1, per=PER_PAGE)
        if not resp.get("success"):
            return "❌ စနစ်နဲ့ ချိတ်ဆက်လို့ မရပါ။"
        d = resp.get("data") or {}
        total = d.get("total") or 0
        html_out = _format_error_list(d)
        kb = _error_list_keyboard(shop, "", 1, total)
        return (html_out, kb)

    # ---- /machine <name> ----
    if cmd == "machine":
        if not shop:
            return "ဘယ်ဆိုင်လဲ? (ဥပမာ: <code>A3 /machine Dragon Blade</code>)"
        q = text.split(None, 1)[1] if " " in text else ""
        q = SHOP_TOKEN_RE.sub("", q).strip()
        if not q:
            return "Usage: <code>/machine Dragon Blade</code>"
        from app.models import Machine
        from app.services.shop_service import get_shop_by_code
        s_obj = get_shop_by_code(shop)
        if not s_obj:
            return "❌ ဆိုင်မတွေ့ပါ။"
        like = f"%{q.lower()}%"
        machines = Machine.query.filter(
            Machine.shop_id == s_obj.id,
            Machine.is_deleted.is_(False),
            db.func.lower(Machine.name).like(like),
        ).limit(5).all()
        if not machines:
            return f"❌ <code>{_esc(shop)}</code> မှာ machine <i>{_esc(q)}</i> မတွေ့ပါ။"
        lines = [f"🔧 <b>Machines</b> · <code>{_esc(shop)}</code>", ""]
        for m in machines:
            lines.append(
                f"• <b>{_esc(m.name)}</b>\n"
                f"  model={_esc(m.model or '—')} · unit={_esc(m.unit or '—')}"
                + (f"\n  aliases: {', '.join(a.alias for a in m.aliases)}" if m.aliases else "")
            )
        return "\n".join(lines)

    # ---- /search <keyword> ----
    if cmd == "search":
        if not shop:
            return "ဘယ်ဆိုင်လဲ? (ဥပမာ: <code>A3 /search marble</code>)"
        q = text.split(None, 1)[1] if " " in text else ""
        q = SHOP_TOKEN_RE.sub("", q).strip()
        if not q:
            return "Usage: <code>/search marble</code>"
        # Error list first
        client = BackendClient()
        resp = client.list_errors(shop=shop, q=q, page=1, per=PER_PAGE)
        if resp.get("success"):
            d = resp.get("data") or {}
            if (d.get("total") or 0) > 0:
                html_out = _format_error_list(d)
                kb = _error_list_keyboard(shop, q, 1, d.get("total"))
                return (html_out, kb)
        # Machine code search
        resp2 = client.search_machine_codes(shop=shop, q=q)
        if resp2.get("success"):
            data = resp2.get("data") or {}
            if data.get("matches"):
                return _format_machine_codes(data)
        return f"❌ <code>{_esc(shop)}</code> မှာ <i>{_esc(q)}</i> မတွေ့ပါ။"

    return "❓ Command မသိပါ။ /help ကို ကြည့်ပါ။"



# ----------------------------------------------------------------
# Free text
# ----------------------------------------------------------------
def _base_handle_text(text: str, chat_id: int, tg_id: int,
                tg_username: str | None, first_name: str | None,
                last_name: str | None) -> tuple[str, dict | None]:
    """
    Return (message_html, reply_markup_or_None).
    """
    text = (text or "").strip()
    if not text:
        return "", None

    tu = _get_or_create_tg_user(tg_id, tg_username, first_name, last_name)
    shop, source = _resolve_shop(text, tu, chat_id)

    if not shop:
        return ("ဘယ်ဆိုင်လဲ ဖော်ပြပါ။ (ဥပမာ: <code>A3 SDPAO-33</code>)", None)

    # --- 1) Machine code query ---
    if re.search(r"\bcode\b|ကုဒ်", text, re.IGNORECASE) and not ERROR_CODE_RE.search(text):
        q = SHOP_TOKEN_RE.sub("", text).strip()
        q = re.sub(r"\bcode\b|ကုဒ်|🔑", "", q, flags=re.IGNORECASE).strip()
        if not q:
            return ("ဘယ် machine ရဲ့ code လဲ? (ဥပမာ: <code>CT code</code>)", None)
        client = BackendClient()
        resp = client.search_machine_codes(shop=shop, q=q)
        if not resp.get("success"):
            return ("စနစ်နဲ့ ချိတ်ဆက်လို့ မရပါ။", None)
        return (_format_machine_codes(resp.get("data") or {}), None)

    # --- 2) Exact error code pattern (SDPAO-33, MSDAB-1, ...) ---
    m = ERROR_CODE_RE.search(text)
    if m:
        code = m.group(1)
        detail = _try_exact_error_code(shop, code)
        if detail:
            return (detail, _error_detail_keyboard(shop, code))
        # No exact match — try keyword fallback
        html_out, kb = _try_error_keyword(shop, code, chat_id)
        if html_out:
            return (html_out, kb)
        return (f"❌ <code>{_esc(shop)}</code> မှာ <code>{_esc(code)}</code> မတွေ့ပါ။", None)

    # --- 3) Error keyword / general ---
    q = SHOP_TOKEN_RE.sub("", text).strip()
    if not q:
        return ("", None)

    # Try error list by keyword
    html_out, kb = _try_error_keyword(shop, q, chat_id)
    if html_out:
        return (html_out, kb)

    return (f"❌ <code>{_esc(shop)}</code> မှာ <i>{_esc(text)}</i> နဲ့ ကိုက်တာ မတွေ့ပါ။", None)


# ----------------------------------------------------------------
# Callback query (inline buttons)
# ----------------------------------------------------------------
def _knowledge_keyboard():
    """Persistent inline keyboard — knowledge button."""
    return {
        "inline_keyboard": [
            [{"text": "📚 Knowledge", "callback_data": "hint_list"}],
        ]
    }




def _persistent_keyboard():
    """Reply keyboard — always visible (input area)."""
    return {
        "keyboard": [
            [{"text": "📚 Knowledge"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }



def _show_knowledge_list(chat_id: int):
    """Build knowledge list + reply keyboard."""
    try:
        from app.models.knowledge import Knowledge
        kn = (Knowledge.query
              .filter(Knowledge.status == "APPROVED")
              .filter(Knowledge.is_deleted.is_(False))
              .order_by(Knowledge.id.asc())
              .limit(20)
              .all())
    except Exception as e:
        log.warning("knowledge list failed: %s", e)
        return ("❌ Error", _persistent_keyboard())

    if not kn:
        return ("📚 Knowledge မရှိပါ။", _persistent_keyboard())

    import time as _t
    _last_list[chat_id] = list(kn)
    _last_list_time[chat_id] = _t.time()

    lines = ["📚 <b>All Knowledge</b>", ""]
    for i, k in enumerate(kn, 1):
        _t_title = k.title or "—"
        _t_ec = (k.error_code or "").strip()
        _t_label = f"{_t_title} {_t_ec}".strip() if _t_ec else _t_title
        lines.append(f"{i}. 📖 <b>{_esc(_t_label)}</b>")
    lines.append("")
    lines.append(f"Total: <b>{len(kn)}</b>")
    lines.append("")
    lines.append("💡 <b>အသုံးပြုနည်း:</b>")
    lines.append("  • နံပါတ် ရိုက်ပါ — <code>1</code>, <code>2</code>, <code>3</code>")

    return ("\n".join(lines), _persistent_keyboard())

def handle_callback(callback: dict) -> None:
    """Handle inline button presses."""
    cb_id = callback.get("id")
    data = callback.get("data") or ""
    msg = callback.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")

    if not chat_id or not cb_id:
        return

    # Acknowledge
    if data == "noop":
        answer_callback(cb_id)
        return

    parts = data.split("|")

    # ★ TASK callbacks (task|complete|ID or task|skip|ID)
    if parts[0] == "task" and len(parts) >= 3:
        action = parts[1]
        try:
            task_id = int(parts[2])
        except (ValueError, IndexError):
            answer_callback(cb_id, "❌ Invalid task id")
            return

        from app.services import task_service as TS
        try:
            if action == "complete":
                TS.update_status(task_id, "COMPLETED", note="Via Telegram")
                answer_callback(cb_id, "✅ Task ပြီးပါပြီ")
                try:
                    edit_message(chat_id, message_id,
                                 f"✅ <b>Task #{task_id}</b> — ပြီးပါပြီ")
                except Exception:
                    pass
            elif action == "skip":
                TS.update_status(task_id, "SKIPPED", note="Via Telegram")
                answer_callback(cb_id, "⏭️ 10 min နေရင် ပြန်ပို့မယ်")
                try:
                    delete_message(chat_id, message_id)
                except Exception as _e:
                    log.warning("skip delete failed: %s", _e)
            else:
                answer_callback(cb_id)
        except Exception as e:
            log.warning("task callback failed: %s", e)
            answer_callback(cb_id, "❌ Error")
        return


    # ★ hint_search — kid direct (loop fix) + fallback title search
    if parts[0] == "hint_search" and len(parts) >= 3:
        kid_raw = parts[1] if len(parts) > 1 else ""
        title = parts[2] if len(parts) > 2 else ""

        answer_callback(cb_id, f"🔍 {title[:30]}")

        # ★ Try kid — direct Knowledge
        handled = False
        if kid_raw and kid_raw != "-":
            try:
                kid = int(kid_raw)
                from app.models.knowledge import Knowledge
                k = Knowledge.query.get(kid)
                if k:
                    html_out = _format_error_detail({
                        "machine": k.title or "",
                        "code": k.error_code or "",
                        "name": k.title or "",
                        "model": k.model or "",
                        "unit": k.unit or "",
                        "solution": k.myanmar_content or k.original_content or "",
                        "notes": k.original_content if k.myanmar_content else "",
                    })
                    try:
                        last_knowledge_id[chat_id] = k.id
                    except Exception:
                        pass
                    try:
                        delete_message(chat_id, message_id)
                    except Exception:
                        pass
                    send_message(chat_id, html_out)
                    # ★ Photo — direct
                    try:
                        _send_knowledge_photos(chat_id, k.id)
                    except Exception as _pe:
                        log.warning("hint kid photo failed: %s", _pe)
                    handled = True
            except Exception as _e:
                log.warning("hint kid direct failed: %s", _e)

        # Fallback — title search
        if not handled:
            try:
                delete_message(chat_id, message_id)
            except Exception:
                pass
            try:
                from app.telegram.handlers import handle_text as _ht
                result = _ht(title, chat_id, chat_id, None, None, None)
                if isinstance(result, tuple):
                    body, kb = result
                else:
                    body, kb = result, None
                if body:
                    send_message(chat_id, body, reply_markup=kb)
            except Exception as e:
                log.warning("hint search failed: %s", e)
                send_message(chat_id, "❌ Search failed")
        return

    # ★ hint_list — all knowledge (DB direct)
    if parts[0] == "hint_list":
        answer_callback(cb_id, "📚")
        try:
            delete_message(chat_id, message_id)
        except Exception:
            pass
        try:
            from app.extensions import db
            from app.models.knowledge import Knowledge
            kn = (
                Knowledge.query
                .filter(Knowledge.status == "APPROVED")
                .filter(Knowledge.is_deleted.is_(False))
                .order_by(Knowledge.id.asc())
                .limit(20)
                .all()
            )
            if not kn:
                send_message(chat_id, "📚 Knowledge မရှိပါ။")
                return
            # ★ Store for number reply
            import time as _t
            _last_list[chat_id] = list(kn)
            _last_list_time[chat_id] = _t.time()

            lines_out = ["📚 <b>All Knowledge</b>", ""]
            for i, k in enumerate(kn, 1):
                title = getattr(k, "title", None) or "—"
                ec = (getattr(k, "error_code", "") or "").strip()
                label = f"{title} {ec}".strip() if ec else title
                lines_out.append(f"{i}. 📖 <b>{_esc(label)}</b>")
            lines_out.append("")
            lines_out.append(f"Total: <b>{len(kn)}</b>")
            lines_out.append("")
            lines_out.append("💡 <b>အသုံးပြုနည်း:</b>")
            lines_out.append("  • နံပါတ် ရိုက်ပါ — <code>1</code>, <code>2</code>, <code>3</code>")
            if kn:
                _first_title = _esc(kn[0].title or "—")
                lines_out.append(f"  • ဥပမာ: <code>1</code> → {_first_title}")
            send_message(chat_id, "\n".join(lines_out), reply_markup=_knowledge_keyboard())
        except Exception as e:
            log.warning("hint list failed: %s", e)
            send_message(chat_id, "❌ Error")
        return
    # ★ detail lookup
    if parts[0] == "detail" and len(parts) >= 3:
        answer_callback(cb_id, "Loading...")
        shop_code = parts[1]
        code = parts[2]
        client = BackendClient()
        resp = client.get_error(shop=shop_code, ident=code)
        if not resp.get("success"):
            edit_message(chat_id, message_id, f"❌ <code>{_esc(code)}</code> မတွေ့ပါ။")
            return
        html_out = _format_error_detail(resp.get("data") or {})
        kb = {
            "inline_keyboard": [
                [{"text": "📋 All errors", "callback_data": f"err|{shop_code}|1|-"}],
            ],
        }
        edit_message(chat_id, message_id, html_out, reply_markup=kb)
        return

    # ★ hint_search / hint_list / noop — len < 4 — skip length check
    if parts[0] in ("hint_search", "hint_list", "noop"):
        pass
    elif len(parts) < 4:
        answer_callback(cb_id)
        return


    # ---- help callback ----
    if parts[0] == "help":
        answer_callback(cb_id, "Help sent")
        shop_code = parts[1]
        text = (
            "🧠 <b>အကူအညီ</b>\n\n"
            "• <code>SDPAO-33</code> — error code တစ်ခု\n"
            "• <code>Dragon Blade error</code> — error list\n"
            "• <code>A3 CT code</code> — machine code\n"
            "• /errors — error list\n"
            "• /tasks — task list"
        )
        send_message(chat_id, text)
        return

    # ---- error list paging ----
    if parts[0] != "err":
        answer_callback(cb_id)
        return

    shop = parts[1]
    try:
        page = max(1, int(parts[2]))
    except ValueError:
        page = 1
    q = parts[3]
    if q == "-":
        q = ""

    answer_callback(cb_id, "Loading...")

    client = BackendClient()
    resp = client.list_errors(shop=shop, q=q, page=page, per=PER_PAGE)
    if not resp.get("success"):
        edit_message(chat_id, message_id, "❌ စနစ်နဲ့ ချိတ်ဆက်လို့ မရပါ။")
        return

    d = resp.get("data") or {}
    total = d.get("total") or 0
    html_out = _format_error_list(d)
    kb = _error_list_keyboard(shop, q, page, total)
    edit_message(chat_id, message_id, html_out, reply_markup=kb)


# ================================================================
# Override: _try_error_keyword (single match → detail with solution)
# ================================================================
def _try_error_keyword(shop_code: str, text: str) -> tuple[str, dict | None]:
    """
    Search error list by keyword.

    - Single result → full detail (with solution)
    - Multiple results → list + per-item buttons
    """
    client = BackendClient()
    resp = client.list_errors(shop=shop_code, q=text, page=1, per=PER_PAGE)
    if not resp.get("success"):
        return "", None
    data = resp.get("data") or {}
    total = data.get("total") or 0
    if total == 0:
        return "", None

    items = data.get("items") or []

    # ★ Single result → fetch full detail
    if total == 1 and items:
        code = items[0].get("code")
        if code:
            detail = client.get_error(shop=shop_code, ident=code)
            if detail.get("success"):
                html_out = _format_error_detail(detail.get("data") or {})
                kb = {
                    "inline_keyboard": [
                        [{"text": "📋 All errors", "callback_data": f"err|{shop_code}|1|-"}],
                    ],
                }
                return html_out, kb

    # ★ Multiple results → list + per-item buttons
    html_out = _format_error_list(data)
    kb = _error_list_inline_keyboard(shop_code, items, text, 1, total)
    return html_out, kb


def _error_list_inline_keyboard(shop_code: str, items: list, q: str,
                                 page: int, total: int) -> dict | None:
    """Per-item detail buttons + paging."""
    rows: list[list[dict]] = []
    for it in items[:8]:
        code = it.get("code")
        if not code:
            continue
        rows.append([
            {"text": f"📖 {code}", "callback_data": f"detail|{shop_code}|{code}|-"},
        ])

    pages = (total + PER_PAGE - 1) // PER_PAGE
    if pages > 1:
        row: list[dict] = []
        if page > 1:
            row.append({"text": "◀ Prev", "callback_data": f"err|{shop_code}|{page-1}|{q or '-'}"})
        row.append({"text": f"{page}/{pages}", "callback_data": "noop"})
        if page < pages:
            row.append({"text": "Next ▶", "callback_data": f"err|{shop_code}|{page+1}|{q or '-'}"})
        rows.append(row)

    return {"inline_keyboard": rows} if rows else None


# ================================================================
# Override: handle_callback (adds 'detail' support)
# ================================================================
def _try_error_keyword(shop_code: str, text: str, chat_id: int = 0) -> tuple[str, dict | None]:
    """
    Search ErrorKnowledge AND Knowledge (both global) by keyword.

    - Single result → full detail
    - Multiple results → list + per-item buttons
    """
    # ★ Smart Match — Knowledge (4 cases) — PRIORITY
    try:
        from app.search.knowledge_match import search_knowledge_smart
        from app.services.shop_service import get_shop_by_code as _gsc
        _shop = _gsc(shop_code) if shop_code else None
        _shop_id = _shop.id if _shop else None

        status, match_k, score, samples = search_knowledge_smart(text, shop_id=_shop_id)

        # ── Direct match (Machine+Error / Error exact / Machine exact) ──
        if status == "match" and match_k:
            html_out = _format_error_detail({
                "machine": match_k.title or "",
                "code": match_k.error_code or "",
                "name": match_k.title or "",
                "model": match_k.model or "",
                "unit": match_k.unit or "",
                "solution": match_k.myanmar_content or match_k.original_content or "",
                "notes": match_k.original_content if match_k.myanmar_content else "",
            })
            try:
                last_knowledge_id[chat_id] = match_k.id
            except Exception:
                pass
            return html_out, None

        # ── Error only / Machine only — hint buttons ──
        if status in ("error_hint", "machine_hint") and samples:
            return _error_hint(chat_id, text, samples)
    except Exception as e:
        log.warning("smart match failed: %s", e)

    client = BackendClient()
    # ★ Try errors first
    resp = client.list_errors(shop=shop_code, q=text, page=1, per=PER_PAGE)
    if resp.get("success"):
        data = resp.get("data") or {}
        total = data.get("total") or 0
        if total > 0:
            items = data.get("items") or []
            if total == 1 and items:
                code = items[0].get("code")
                if code:
                    detail = client.get_error(shop=shop_code, ident=code)
                    if detail.get("success"):
                        html_out = _format_error_detail(detail.get("data") or {})
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📋 All errors", "callback_data": f"err|{shop_code}|1|-"}],
                            ],
                        }
                        return html_out, kb
            html_out = _format_error_list(data)
            kb = _error_list_inline_keyboard(shop_code, items, text, 1, total)
            return html_out, kb

    # ★ Try general Knowledge (global via unified search)
    try:
        sr = client.unified_search(text, shop=None)  # global
        if sr.get("success"):
            results = (sr.get("data") or {}).get("results") or []
            # Filter to knowledge kind
            kn = [r for r in results if r.get("kind") == "knowledge"]
            kn = _dedupe_knowledge_hits(kn)
            if kn:
                lines = [f"📖 <b>Knowledge</b> · <i>'{_esc(text)}'</i>", ""]
                for r in kn[:8]:
                    title = r.get("title") or "—"
                    raw = (r.get("snippet")
                           or r.get("myanmar_content")
                           or r.get("content")
                           or r.get("original_content")
                           or "")
                    snippet = raw[:3500]
                    lines.append(f"• <b>{_esc(title)}</b>")
                    if snippet:
                        # Preserve original format: blank lines + leading spaces
                        for sline in snippet.split("\n"):
                            if sline.strip():
                                lines.append(_esc(sline))
                            else:
                                lines.append("")
                return "\n".join(lines), None
    except Exception as e:
        log.warning("knowledge search failed: %s", e)

    # ★ Search fail → hint with buttons
    try:
        return _no_result_hint(chat_id, shop_code, text)
    except Exception:
        return "", None


# ================================================================
# Helper: search fail → hint with dynamic buttons
# ================================================================
def _no_result_hint(chat_id: int, shop_code: str | None, query: str):
    """Build search-fail message + inline buttons (DB direct)."""
    # ★ DB direct query — US.search(query="") ပြဿနာ ရှောင်
    samples = []
    try:
        from app.models.knowledge import Knowledge
        kn = (
            Knowledge.query
            .filter(Knowledge.status == "APPROVED")
            .filter(Knowledge.is_deleted.is_(False))
            .order_by(Knowledge.id.asc())
            .limit(4)
            .all()
        )
        # Simple namespace — title + id
        class _Sample:
            __slots__ = ("id", "title")
            def __init__(self, _id, _title):
                self.id = _id
                self.title = _title
        samples = [_Sample(k.id, k.title or "—") for k in kn]
    except Exception as e:
        log.warning("hint samples failed: %s", e)

    lines = [
        f"❌ <b>{_esc(query)}</b> — မတွေ့ပါ။",
        "",
        "💡 <b>ဒါတွေ စမ်းကြည့်ပါ:</b>",
    ]

    kb = {
        "inline_keyboard": [
            *[[{"text": f"📖 {(s.title or '—')[:30]}",
                "callback_data": f"hint_search|{s.id}|{(s.title or '')[:40]}"}]
              for s in samples],
            [{"text": "📚 All Knowledge", "callback_data": "hint_list"}],
        ]
    }
    return "\n".join(lines), kb


def _error_hint(chat_id: int, query: str, samples: list):
    """Hint for Error-only / Machine-only queries — machine/error buttons."""
    lines = [
        f"💡 <b>{_esc(query)}</b> — ဒါတွေ စမ်းကြည့်ပါ:",
        "",
    ]

    kb_rows = []
    for k in samples[:6]:
        title = (k.title or "—")[:40]
        error = (k.error_code or "")[:15]
        label = f"📖 {title[:25]}"
        if error:
            label += f" · {error}"
        kb_rows.append([{
            "text": label[:60],
            "callback_data": f"hint_search|{k.id}|{title[:40]}",
        }])

    kb_rows.append([{"text": "📚 All Knowledge", "callback_data": "hint_list"}])

    kb = {"inline_keyboard": kb_rows}
    return "\n".join(lines), kb
# ================================================================
# Override: handle_text (clean query before search)
# ================================================================






# ================================================================
# Final hook: send knowledge photos as ONE album with caption
# ================================================================
def handle_text(text: str, chat_id: int, tg_id: int,
                tg_username: str | None, first_name: str | None,
                last_name: str | None):
    """Send reply, then if a single knowledge matched → send photos as album."""
    # ★ Clear any stale photo hook from previous query
    last_knowledge_id.pop(chat_id, None)

    txt = (text or "").strip()

    # ★ ReplyKeyboard button — "📚 Knowledge"
    if txt == "📚 Knowledge":
        return _show_knowledge_list(chat_id)

    # ★ Number reply — user typed "1" / "2" / "3"
    if txt.isdigit():
        import time as _t
        n = int(txt)
        ts = _last_list_time.get(chat_id, 0)
        items = _last_list.get(chat_id) or []
        if items and (n >= 1) and (n <= len(items)) and (_t.time() - ts <= _LAST_LIST_TTL):
            k = items[n - 1]
            try:
                html_out = _format_error_detail({
                    "machine": k.title or "",
                    "code": k.error_code or "",
                    "name": k.title or "",
                    "model": k.model or "",
                    "unit": k.unit or "",
                    "solution": k.myanmar_content or k.original_content or "",
                    "notes": k.original_content if k.myanmar_content else "",
                })
            except Exception as _e:
                log.warning("number reply format failed: %s", _e)
                html_out = f"📖 <b>{_esc(k.title or '—')}</b>"
            try:
                last_knowledge_id[chat_id] = k.id
            except Exception:
                pass
            # ★ Keep _last_list — loop ဆက်
            _last_list_time[chat_id] = _t.time()
            return html_out, _persistent_keyboard()

    result = _base_handle_text(
        text, chat_id, tg_id, tg_username, first_name, last_name,
    )

    try:
        from app.search import unified_search as US
        from app.services import knowledge_photo_service as KPS
        from app.services.shop_service import get_shop_by_code

        tu = _get_or_create_tg_user(tg_id, tg_username, first_name, last_name)
        shop, _ = _resolve_shop(text, tu, chat_id)
        shop_obj = get_shop_by_code(shop) if shop else None

        q = SHOP_TOKEN_RE.sub("", text).strip().replace("_", " ").strip()
        if not q:
            return result

        search = US.search(
            query=q,
            shop_id=shop_obj.id if shop_obj else None,
            shop_code=shop,
            only_approved=True,
        )
        kn = [h for h in search.hits if h.kind == "knowledge"]
        # ★ Only send photos if top knowledge has strong score (>= 0.7)
        if len(kn) == 1 and kn[0].score >= 0.7:
            kid = kn[0].id
            photos = KPS.list_photos(kid)
            if photos:
                title = kn[0].title or ""
                cap = f"\U0001F4D6 {title}"[:1000]
                # Signal bot.py to send photos (with message_thread_id)
                last_knowledge_id[chat_id] = kid
    except Exception as e:
        log.warning("photo hook failed: %s", e)

    return result


# ================================================================
# Helper: dedupe knowledge hits by normalized title
# ================================================================
def _dedupe_knowledge_hits(hits: list) -> list:
    """Remove knowledge hits with duplicate titles (case/underscore insensitive)."""
    import re as _re
    seen: dict[str, dict] = {}
    for h in hits:
        t = (h.get("title") or "").lower()
        key = _re.sub(r"\b(error|err|_)\b", "", t)
        key = _re.sub(r"[\s_\-]+", " ", key).strip()
        if key and key not in seen:
            seen[key] = h
        elif key not in seen:
            seen[key or t] = h
    return list(seen.values())


# ================================================================
# Helper: send knowledge photos as ONE album (sendMediaGroup)
# ================================================================
def _send_knowledge_photos(chat_id: int, knowledge_id: int,
                            caption: str | None = None,
                            message_thread_id: int | None = None) -> None:
    """
    Send all photos for a knowledge entry as ONE Telegram album.

    A: Uses cached telegram_file_id when available → instant.
    B: Uploads with resize when not cached → fast.
    """
    try:
        from app.telegram import client as tg_client
        from app.services import knowledge_photo_service as KPS

        photos = KPS.list_photos(knowledge_id)
        if not photos:
            return

        cap = (caption or "")[:1000]

        def _save(pid, fid):
            try:
                KPS.save_telegram_file_id(pid, fid)
            except Exception as e:
                log.warning("save file_id failed: %s", e)

        # ★ Use bot admin's chat as silent upload target (cache fills only)
        admin_chat_id = None
        try:
            from app.models import TelegramUser as _TU
            _admin = _TU.query.filter_by(is_verified=True).first()
            if _admin:
                admin_chat_id = _admin.telegram_user_id
        except Exception:
            pass

        resp = tg_client.send_media_group_with_cache(
            chat_id, photos, caption=cap, save_callback=_save,
            admin_chat_id=admin_chat_id,
            message_thread_id=message_thread_id,
        )
        if not resp.get("ok"):
            log.warning("album send failed: %s",
                        resp.get("description") or resp.get("error"))
    except Exception as e:
        log.warning("send photos failed: %s", e)

# ================================================================
# Group + Topic support
# ================================================================
def _extract_bot_username():
    """Return bot username from Telegram API getMe (cached)."""
    try:
        from app.config import Config
        import httpx
        r = httpx.get(
            "https://api.telegram.org/bot" + Config.TELEGRAM_BOT_TOKEN + "/getMe",
            timeout=8,
        )
        data = r.json()
        if data.get("ok"):
            return data.get("result", {}).get("username")
    except Exception:
        pass
    return None


_BOT_USERNAME_CACHE = {}


def _bot_username():
    if "u" not in _BOT_USERNAME_CACHE:
        _BOT_USERNAME_CACHE["u"] = _extract_bot_username()
    return _BOT_USERNAME_CACHE["u"]


def _is_bot_mentioned(text, msg):
    """Return True if the bot is @mentioned or if the user replied to the bot."""
    uname = _bot_username()
    if uname and ("@" + uname).lower() in (text or "").lower():
        return True
    reply = msg.get("reply_to_message") or {}
    from_user = reply.get("from") or {}
    if uname and from_user.get("username") == uname:
        return True
    return False


def handle_setup_command(*, chat_id, thread_id, chat_type, title,
                          tg_id, tg_username, first_name, last_name):
    """Handle /setup in a group or topic. Registers group + current topic."""
    from app.services import telegram_group_service as TGS

    if chat_type not in ("group", "supergroup"):
        return ("Group မှာပဲ /setup ကို သုံးလို့ရတယ်။")

    cfg = TGS.get_by_chat_id(chat_id)
    if not cfg:
        cfg = TGS.register_or_update(
            chat_id=chat_id, title=title, chat_type=chat_type,
            allowed_thread_ids=[thread_id] if thread_id else [],
        )
    else:
        threads = list(cfg.thread_list())
        if thread_id and thread_id not in threads:
            threads.append(thread_id)
            from app.extensions import db
            cfg.set_threads(threads)
            db.session.commit()

    threads = cfg.thread_list()
    lines = [
        "✅ <b>Group ကို Register လုပ်ပြီးပါပြီ</b>",
        "",
        "📛 <b>Group:</b> " + (title or str(chat_id)),
        "🆔 <b>Chat ID:</b> <code>" + str(chat_id) + "</code>",
    ]
    if thread_id:
        lines.append("📌 <b>Topic ID:</b> <code>" + str(thread_id) + "</code>")
    lines.append("🔓 <b>Allowed topics:</b> " + (str(threads) if threads else "All"))
    lines.append("")
    lines.append("ဒီ Topic မှာ Bot က အလိုအလျောက် ဖြေပါမယ်။")
    lines.append("Web → <b>/telegram-groups</b> မှာ စီမံလို့ရပါတယ်။")
    return "\n".join(lines)


def handle_group_message(*, chat_id, thread_id, text, tg_id,
                          tg_username, first_name, last_name,
                          is_bot_mentioned, message_id=None):
    """
    Handle group messages.
    - Commands (/start, /help, etc.) → handle_command
    - Free text → handle_text
    Returns (reply_text, reply_markup) or (None, None).
    """
    from app.services import telegram_group_service as TGS

    cfg = TGS.check_and_get_config(chat_id)
    if not cfg:
        return None, None

    if not cfg.allows_thread(thread_id):
        return None, None

    if cfg.require_mention and not is_bot_mentioned:
        return None, None

    try:
        TGS.bump_stats(chat_id)
    except Exception:
        pass

    clean = (text or "").strip()
    # Strip @mention
    uname = _bot_username()
    if uname:
        import re as _re
        clean = _re.sub(
            "@" + _re.escape(uname) + r"\s*", "", clean, flags=_re.IGNORECASE
        ).strip()
    if not clean:
        return None, None

    # ★ Command handling
    cmd = None
    if clean.startswith("/"):
        first = clean[1:].split()[0].lower()
        if "@" in first:
            first = first.split("@", 1)[0]
        cmd = first

    try:
        if cmd:
            result = handle_command(
                cmd, clean, chat_id, tg_id,
                tg_username, first_name, last_name,
            )
        else:
            result = handle_text(
                clean, chat_id, tg_id,
                tg_username, first_name, last_name,
            )
    except Exception as e:
        log.exception("group handler failed: %s", e)
        return None, None

    if isinstance(result, tuple):
        return result
    return result, None