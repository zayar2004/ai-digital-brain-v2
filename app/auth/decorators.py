"""
Centralized authorization decorators.

Never rely only on hiding frontend buttons.
Backend must enforce permissions.
"""

from __future__ import annotations

from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user, login_required


def _wants_json() -> bool:
    return (
        request.path.startswith("/api/")
        or request.accept_mimetypes.best == "application/json"
    )


def require_role(*allowed_roles: str):
    """Require the current user to have one of the given roles."""

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_active:
                if _wants_json():
                    return jsonify(
                        {"success": False, "error": {"code": "forbidden", "message": "Account disabled."}}
                    ), 403
                abort(403)

            if allowed_roles and current_user.role not in allowed_roles:
                if _wants_json():
                    return jsonify(
                        {"success": False, "error": {"code": "forbidden", "message": "Insufficient role."}}
                    ), 403
                abort(403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_super_admin(fn):
    """Shortcut: require SUPER_ADMIN."""
    return require_role("SUPER_ADMIN")(fn)
