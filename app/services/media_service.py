"""
Media file service.

Safe upload, listing, download, and delete.
"""

from __future__ import annotations

from flask import send_file
from flask_login import current_user

from app.extensions import db
from app.models import MediaCategory, MediaFile
from app.services import file_service, audit_service


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def save_media(
    *,
    uploaded_file,
    shop_id: int | None = None,
    category: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    machine_id: int | None = None,
) -> MediaFile:
    meta = file_service.save_upload(uploaded_file, category=category)

    mf = MediaFile(
        shop_id=shop_id,
        machine_id=machine_id,
        original_filename=meta["original_filename"],
        stored_filename=meta["stored_filename"],
        file_path=meta["file_path"],
        file_hash=meta["file_hash"],
        mime_type=meta.get("mime_type"),
        size_bytes=meta.get("size_bytes"),
        category=_map_category(meta.get("category")),
        caption=(caption or "").strip() or None,
        description=(description or "").strip() or None,
        uploaded_by_id=_current_user_id(),
    )
    db.session.add(mf)
    db.session.commit()

    audit_service.log(
        "media.upload", entity_type="media_file", entity_id=mf.id,
        shop_id=shop_id, details={"filename": mf.original_filename, "category": mf.category},
    )
    return mf


def _map_category(raw: str | None) -> str:
    if not raw:
        return MediaCategory.OTHER
    raw = raw.lower()
    if raw == "image":
        return MediaCategory.IMAGE
    if raw == "excel":
        return MediaCategory.EXCEL
    if raw == "pdf":
        return MediaCategory.PDF
    if raw == "word":
        return MediaCategory.WORD
    if raw in ("text", "documents", "document"):
        return MediaCategory.DOCUMENT
    return MediaCategory.OTHER


def list_media(
    *,
    shop_id: int | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = 200,
) -> list[MediaFile]:
    query = MediaFile.query.filter(MediaFile.is_deleted.is_(False))
    if shop_id:
        query = query.filter(MediaFile.shop_id == shop_id)
    if category:
        query = query.filter(MediaFile.category == category)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(db.or_(
            db.func.lower(MediaFile.original_filename).like(like),
            db.func.lower(db.func.coalesce(MediaFile.caption, "")).like(like),
        ))
    return query.order_by(MediaFile.id.desc()).limit(limit).all()


def get_media(media_id: int) -> MediaFile | None:
    if not media_id:
        return None
    return db.session.get(MediaFile, media_id)


def delete_media(media_id: int) -> bool:
    mf = db.session.get(MediaFile, media_id)
    if not mf:
        return False
    # Best-effort remove from disk
    try:
        file_service.delete_stored_file(mf.file_path)
    except Exception:
        pass
    mf.soft_delete()
    db.session.commit()
    audit_service.log("media.delete", entity_type="media_file",
                      entity_id=media_id, shop_id=mf.shop_id)
    return True


def send_media_file(media_id: int):
    """Return a Flask response that streams the file to the client."""
    mf = get_media(media_id)
    if not mf:
        return None
    return send_file(
        mf.file_path,
        as_attachment=(mf.category != MediaCategory.IMAGE),
        download_name=mf.original_filename,
        mimetype=mf.mime_type or "application/octet-stream",
    )
