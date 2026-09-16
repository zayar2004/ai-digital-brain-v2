"""Helpers to safely read values from HTML form submissions."""

from __future__ import annotations

from flask import request

from app.security.validators import clean_text


def ftext(name: str, default: str = "", max_len: int = 500) -> str:
    """Read a trimmed text field."""
    return clean_text(request.form.get(name, default), max_len=max_len)


def fint(name: str, default: int | None = None) -> int | None:
    """Read an integer form field, or default."""
    raw = request.form.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        return default


def flines(name: str, max_lines: int = 50) -> list[str]:
    """Read a newline- or comma-separated list."""
    raw = request.form.get(name, "") or ""
    items: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        s = line.strip()
        if s:
            items.append(s)
        if len(items) >= max_lines:
            break
    return items
