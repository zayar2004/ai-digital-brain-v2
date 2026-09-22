"""
API routes.

PART 9: /api/me + /api/machine-codes/search
"""

from __future__ import annotations

import hmac
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user
from app.extensions import db
from app.config import Config

from app.security.shop_scope import normalize_shop_code
from app.services import machine_code_service as MCS
from app.services.shop_service import get_shop_by_code

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


def _err(code: str, message: str, status: int = 400):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


# ================================================================
# ★ API Key authentication (Bot ↔ API security)
# ================================================================
# Public endpoints (Bot/Admin Web က key မလိုဘဲ ခေါ်နိုင်)
_PUBLIC_PATHS = frozenset({
    "/api/me",       # Admin Web / browser session
    "/api/health",   # health check
})


@api_bp.before_request
def require_api_key():
    """
    Bot က API ကို ခေါ်တဲ့အခါ 'Authorization: Bearer <BOT_API_KEY>' လိုတယ်။

    Skip cases:
      1. /api/me, /api/health → public
      2. logged-in admin (current_user.is_authenticated)
      3. BOT_API_KEY မသတ်မှတ်ရင် (dev mode)
    """
    # 1. Public endpoints
    if request.path in _PUBLIC_PATHS:
        return None

    # 2. Logged-in admin (Admin Web session) → skip
    if current_user.is_authenticated:
        return None

    # 3. Bot: Bearer token required
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _err("unauthorized", "API key required.", 401)

    token = auth[7:].strip()
    expected = Config.BOT_API_KEY

    # Dev mode — no key set → allow
    if not expected:
        log.warning("BOT_API_KEY not set — API is open (dev mode).")
        return None

    # Constant-time comparison
    if not hmac.compare_digest(token, expected):
        log.warning("Invalid API key from %s", request.remote_addr)
        return _err("unauthorized", "Invalid API key.", 401)

    return None


@api_bp.route("/me", methods=["GET"])
def me():
    if not current_user.is_authenticated:
        return jsonify({"success": True, "data": {"authenticated": False}})
    return jsonify({
        "success": True,
        "data": {
            "authenticated": True,
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
        },
    })


@api_bp.route("/machine-codes/search", methods=["GET"])
def machine_codes_search():
    """
    Search machine codes.

    Query params:
        q     — search query (required)
        shop  — shop code (required) e.g. A3
        approved — optional, "1" to only return APPROVED
        limit — optional, default 100, max 500
    """
    q = (request.args.get("q") or "").strip()
    shop_raw = (request.args.get("shop") or "").strip()
    only_approved = request.args.get("approved", "0") == "1"
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
    except ValueError:
        limit = 100

    shop_code = normalize_shop_code(shop_raw)
    if not shop_code:
        return _err("bad_shop", "Valid shop code (A1-A13) is required.")

    shop = get_shop_by_code(shop_code)
    if not shop:
        return _err("shop_not_found", "Shop not found.", 404)

    outcome = MCS.search_machine_codes(
        shop_id=shop.id,
        shop_code=shop_code,
        query=q,
        only_approved=only_approved,
        limit=limit,
    )
    return jsonify({"success": True, "data": outcome.to_dict()})


@api_bp.route("/search", methods=["GET"])
def unified_search_api():
    """
    Unified search across knowledge, machines, codes, errors.

    Query params:
        q     — search query (required)
        shop  — optional shop code
        approved — "1" default, "0" to include non-approved
        limit — per-kind limit (default 20, max 100)
    """
    from app.search import unified_search as US

    q = (request.args.get("q") or "").strip()
    shop_raw = (request.args.get("shop") or "").strip()
    only_approved = request.args.get("approved", "1") == "1"
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
    except ValueError:
        limit = 20

    if not q:
        return _err("bad_query", "Search query is required.")

    shop_code = normalize_shop_code(shop_raw) if shop_raw else None
    shop = get_shop_by_code(shop_code) if shop_code else None

    result = US.search(
        query=q,
        shop_id=shop.id if shop else None,
        shop_code=shop.code if shop else None,
        limit_per_kind=limit,
        only_approved=only_approved,
    )
    return jsonify({"success": True, "data": result.to_dict()})


@api_bp.route("/ai/ask", methods=["POST"])
def ai_ask():
    """
    Ask the AI a question. Body (JSON):
        { "question": "...", "shop": "A3" (optional) }
    """
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    shop_raw = (body.get("shop") or "").strip()

    if not question:
        return _err("bad_query", "question is required.")

    shop_code = normalize_shop_code(shop_raw) if shop_raw else None
    shop = get_shop_by_code(shop_code) if shop_code else None

    try:
        from app.ai import rag as AI_RAG
        result = AI_RAG.answer_question(
            user_question=question,
            shop_code=shop.code if shop else None,
            shop_id=shop.id if shop else None,
            only_approved=True,
        )
    except Exception as e:
        return _err("ai_error", f"AI request failed: {e}", 500)

    return jsonify({"success": True, "data": result.to_dict()})


@api_bp.route("/tasks/today", methods=["GET"])
def tasks_today_api():
    shop_code = normalize_shop_code(request.args.get("shop", "")) if request.args.get("shop") else None
    shop = get_shop_by_code(shop_code) if shop_code else None
    try:
        from app.services import task_service as TS
        tasks = TS.tasks_for_date(shop_id=shop.id if shop else None)
        return jsonify({
            "success": True,
            "data": {
                "date": TS.local_today().isoformat(),
                "shop": shop.code if shop else None,
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "schedule": t.describe_schedule(),
                        "time": t.task_time,
                        "priority": t.priority,
                        "status": t.status,
                    }
                    for t in tasks
                ],
            },
        })
    except Exception as e:
        return _err("tasks_error", str(e), 500)




# ================================================================
# Error Knowledge endpoints (for Telegram bot)
# ================================================================
@api_bp.route("/errors/list", methods=["GET"])
def errors_list_api():
    """
    List ErrorKnowledge for a shop, with optional search.

    Query params:
        shop   — required shop code (A1..A13)
        q      — optional search string
        page   — default 1
        per    — default 20, max 50
    """
    from app.models import ErrorKnowledge

    shop_code = normalize_shop_code(request.args.get("shop", ""))
    if not shop_code:
        return _err("bad_shop", "shop required (A1-A13)")

    shop = get_shop_by_code(shop_code)
    if not shop:
        return _err("shop_not_found", "shop not found", 404)

    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per = max(1, min(int(request.args.get("per", 20)), 50))
    except ValueError:
        per = 20

    # ★ GLOBAL — all shops see all errors
    query = ErrorKnowledge.query.filter(
        ErrorKnowledge.is_deleted.is_(False),
        ErrorKnowledge.status == "APPROVED",
    )
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(db.or_(
            db.func.lower(db.func.coalesce(ErrorKnowledge.error_code, "")).like(like),
            db.func.lower(db.func.coalesce(ErrorKnowledge.error_name, "")).like(like),
            db.func.lower(db.func.coalesce(ErrorKnowledge.machine_name, "")).like(like),
        ))

    total = query.count()
    rows = query.order_by(ErrorKnowledge.id).offset((page - 1) * per).limit(per).all()

    return jsonify({
        "success": True,
        "data": {
            "shop": shop_code,
            "q": q,
            "page": page,
            "per": per,
            "total": total,
            "items": [
                {
                    "id": e.id,
                    "code": e.error_code,
                    "name": e.error_name,
                    "machine": e.machine_name,
                    "unit": e.unit,
                }
                for e in rows
            ],
        },
    })


@api_bp.route("/errors/one", methods=["GET"])
def errors_one_api():
    """
    Full ErrorKnowledge record (for detail view).

    Query params:
        shop — required (A1..A13)
        id   — either internal id OR error_code
    """
    from app.models import ErrorKnowledge

    shop_code = normalize_shop_code(request.args.get("shop", ""))
    if not shop_code:
        return _err("bad_shop", "shop required")

    shop = get_shop_by_code(shop_code)
    if not shop:
        return _err("shop_not_found", "shop not found", 404)

    ident = (request.args.get("id") or "").strip()
    if not ident:
        return _err("bad_id", "id or code required")

    ek = None
    # Try numeric id (global — no shop filter)
    if ident.isdigit():
        ek = ErrorKnowledge.query.filter_by(
            id=int(ident),
            status="APPROVED", is_deleted=False,
        ).first()
    # Try code (case-insensitive, global)
    if ek is None:
        ek = ErrorKnowledge.query.filter(
            ErrorKnowledge.status == "APPROVED",
            ErrorKnowledge.is_deleted.is_(False),
            db.func.lower(ErrorKnowledge.error_code) == ident.lower(),
        ).first()

    if ek is None:
        return _err("not_found", "error not found", 404)

    return jsonify({
        "success": True,
        "data": {
            "id": ek.id,
            "shop": shop_code,
            "code": ek.error_code,
            "name": ek.error_name,
            "machine": ek.machine_name,
            "model": ek.model,
            "unit": ek.unit,
            "symptoms": ek.symptoms,
            "cause": ek.cause,
            "check_steps": ek.check_steps,
            "solution": ek.solution,
            "notes": ek.notes,
        },
    })


@api_bp.route("/knowledge/photos", methods=["GET"])
def knowledge_photos_api():
    """List photos for a knowledge entry."""
    from app.services import knowledge_photo_service as KPS

    ident = (request.args.get("id") or "").strip()
    if not ident.isdigit():
        return _err("bad_id", "numeric id required")

    photos = KPS.list_photos(int(ident))
    return jsonify({
        "success": True,
        "data": {
            "knowledge_id": int(ident),
            "count": len(photos),
            "photos": [
                {
                    "id": p.id,
                    "position": p.position,
                    "caption": p.caption,
                    "filename": p.original_filename,
                    "telegram_file_id": p.telegram_file_id,
                }
                for p in photos
            ],
        },
    })
