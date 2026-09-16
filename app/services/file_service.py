"""
File storage service.

Never trust user filenames. Always generate safe stored names.
Never expose real filesystem paths to users.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app.config import UPLOAD_ROOT
from app.security.validators import (
    category_for_filename,
    is_allowed_file,
    is_within,
    safe_filename,
    sanitize_original_filename,
)


def _subdir_for_category(category: str) -> Path:
    mapping = {
        "excel": UPLOAD_ROOT / "excel",
        "csv":   UPLOAD_ROOT / "excel",
        "pdf":   UPLOAD_ROOT / "pdf",
        "word":  UPLOAD_ROOT / "word",
        "image": UPLOAD_ROOT / "photos",
        "text":  UPLOAD_ROOT / "documents",
    }
    p = mapping.get(category, UPLOAD_ROOT / "documents")
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(file: FileStorage, *, category: str | None = None) -> dict:
    """
    Save an uploaded file safely.

    Returns dict with:
        original_filename, stored_filename, file_path, file_hash,
        size_bytes, category, mime_type
    """
    if not file or not file.filename:
        raise ValueError("No file provided.")

    if not is_allowed_file(file.filename, category=category):
        raise ValueError(f"File type not allowed: {file.filename}")

    cat = category or category_for_filename(file.filename) or "documents"
    target_dir = _subdir_for_category(cat)

    stored_name = safe_filename(file.filename)
    target_path = target_dir / stored_name

    if not is_within(UPLOAD_ROOT, target_path):
        raise ValueError("Invalid target path.")

    file.save(str(target_path))

    h = hashlib.sha256()
    size = 0
    with open(target_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
            size += len(chunk)

    return {
        "original_filename": sanitize_original_filename(file.filename),
        "stored_filename": stored_name,
        "file_path": str(target_path),
        "file_hash": h.hexdigest(),
        "size_bytes": size,
        "category": cat,
        "mime_type": getattr(file, "mimetype", None),
    }


def delete_stored_file(file_path: str) -> bool:
    """Delete a stored file if it's inside the uploads directory."""
    p = Path(file_path)
    if not is_within(UPLOAD_ROOT, p):
        return False
    try:
        if p.is_file():
            os.remove(p)
            return True
    except OSError:
        pass
    return False
