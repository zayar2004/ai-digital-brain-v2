"""
Centralized audit logging service.

Never log: passwords, API keys, Telegram tokens, or other secrets.
The `_scrub` function removes obvious secret keys from the details dict.
"""

from __future__ import annotations

import json
from typing import Any

from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog

_SECRET_KEYS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "api_key",
    "token",
    "telegram_bot_token",
    "authorization",
    "cookie",
    "session",
}


def _scrub(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    out: dict[str, Any] = {}
    for k, v in data.items():
        if any(s in k.lower() for s in _SECRET_KEYS):
            out[k] = "***"
        else:
            out[k] = v
    return out


def log(
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    shop_id: int | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog | None:
    """Write an audit entry. Best-effort — never crash the request."""
    try:
        actor_user_id = None
        actor_label = None
        if has_request_context() and current_user.is_authenticated:
            actor_user_id = current_user.id
            actor_label = current_user.username

        ip = request.remote_addr if has_request_context() else None
        ua = (
            request.headers.get("User-Agent") if has_request_context() else None
        )

        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            shop_id=shop_id,
            details=json.dumps(_scrub(details), ensure_ascii=False)
            if details
            else None,
            ip_address=ip,
            user_agent=ua,
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
        return entry
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None
