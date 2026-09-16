"""
Settings service.

Defaults are hardcoded; DB overrides them.
Types: str | int | float | bool
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import AppSetting


DEFAULTS: dict[str, tuple[Any, str, str]] = {
    # key: (default, type, description)
    "ai.answer_language": ("my", "str", "Default answer language (my/en)"),
    "ai.strict_grounding": (True, "bool", "Reject ungrounded AI answers"),
    "ai.temperature": (0.2, "float", "AI temperature"),
    "ai.max_tokens": (1200, "int", "Max answer length"),

    "search.default_shop_filter": ("", "str", "Default shop filter"),
    "search.results_per_page": (50, "int", "Results per page"),

    "telegram.welcome_enabled": (True, "bool", "Send welcome on /start"),
    "telegram.notify_on_link": (True, "bool", "Notify on shop link"),

    "system.site_name": ("AI Digital Brain", "str", "Site name"),
    "system.timezone": ("Asia/Yangon", "str", "Timezone"),

    "backup.auto_daily": (False, "bool", "Auto daily backup"),
    "backup.keep_days": (30, "int", "Keep backups for N days"),
}


def _to_type(value: Any, vtype: str) -> Any:
    if vtype == "int":
        return int(value)
    if vtype == "float":
        return float(value)
    if vtype == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    return str(value)


def _to_db_str(value: Any, vtype: str) -> str:
    if vtype == "bool":
        return "true" if value else "false"
    return str(value)


def get(key: str) -> Any:
    """Return setting value (default if not in DB)."""
    default, vtype, _ = DEFAULTS.get(key, (None, "str", ""))
    row = AppSetting.query.filter_by(key=key).first()
    if row is None:
        return default
    try:
        return _to_type(row.value, row.value_type)
    except Exception:
        return default


def set(key: str, value: Any) -> None:  # noqa: A001
    default, vtype, desc = DEFAULTS.get(key, (None, "str", None))
    row = AppSetting.query.filter_by(key=key).first()
    if row is None:
        row = AppSetting(key=key, value=_to_db_str(value, vtype),
                         value_type=vtype, description=desc)
        db.session.add(row)
    else:
        row.value = _to_db_str(value, vtype)
    db.session.commit()


def all_settings() -> dict[str, Any]:
    """Return all known settings with current values."""
    out = {}
    for key in DEFAULTS:
        out[key] = get(key)
    return out


def list_with_meta() -> list[dict]:
    """Return list of {key, value, default, type, description}."""
    out = []
    for key, (default, vtype, desc) in DEFAULTS.items():
        out.append({
            "key": key,
            "value": get(key),
            "default": default,
            "type": vtype,
            "description": desc,
        })
    return out
