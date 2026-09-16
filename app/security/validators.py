"""
Input and file validation.

Never trust: file names, file types, IDs, shop access, Telegram identity.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

# Allowed file extensions by category
ALLOWED_EXTENSIONS = {
    "excel": {".xlsx", ".xlsm", ".xls"},
    "csv": {".csv"},
    "pdf": {".pdf"},
    "word": {".docx", ".doc"},
    "image": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"},
    "text": {".txt", ".md"},
}

ALL_ALLOWED = set().union(*ALLOWED_EXTENSIONS.values())

# Max length for common string fields
MAX_FILENAME_LEN = 255
MAX_TEXT_FIELD = 20_000


def safe_extension(filename: str) -> str:
    """Return the lowercase extension including the dot, or ''."""
    if not filename:
        return ""
    ext = Path(filename).suffix.lower()
    return ext


def is_allowed_file(filename: str, category: str | None = None) -> bool:
    """Return True if filename's extension is allowed (optionally in category)."""
    ext = safe_extension(filename)
    if not ext:
        return False
    if category:
        return ext in ALLOWED_EXTENSIONS.get(category, set())
    return ext in ALL_ALLOWED


def category_for_filename(filename: str) -> str | None:
    """Return the best-matching category for a filename."""
    ext = safe_extension(filename)
    for cat, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return cat
    return None


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original: str, *, keep_ext: bool = True) -> str:
    """
    Generate a safe stored filename.

    Never reuse user-provided name directly.
    """
    ext = safe_extension(original) if keep_ext else ""
    base = Path(original).stem if original else "file"
    base = _SAFE_NAME_RE.sub("_", base)[:64] or "file"
    return f"{base}_{uuid.uuid4().hex[:12]}{ext}"


def sanitize_original_filename(original: str) -> str:
    """Sanitize the original filename for storage as metadata."""
    if not original:
        return "unknown"
    name = os.path.basename(original).strip()
    return name[:MAX_FILENAME_LEN] or "unknown"


def is_within(base: Path, candidate: Path) -> bool:
    """Return True if candidate is inside base (path traversal protection)."""
    try:
        base_r = base.resolve()
        cand_r = candidate.resolve()
    except (OSError, RuntimeError):
        return False
    try:
        cand_r.relative_to(base_r)
        return True
    except ValueError:
        return False


def clean_text(value: str | None, max_len: int = MAX_TEXT_FIELD) -> str:
    """Trim and limit text. Return empty string for None."""
    if value is None:
        return ""
    s = str(value).strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def is_valid_telegram_user_id(value) -> bool:
    """Telegram user IDs are positive integers."""
    try:
        n = int(value)
        return n > 0
    except (TypeError, ValueError):
        return False
