"""Knowledge photo service — upload, list, delete, reorder."""

from __future__ import annotations

from flask_login import current_user
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Knowledge, KnowledgePhoto, MAX_PHOTOS_PER_KNOWLEDGE
from app.services import audit_service, file_service


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def list_photos(knowledge_id: int) -> list[KnowledgePhoto]:
    return (
        KnowledgePhoto.query
        .filter_by(knowledge_id=knowledge_id, is_deleted=False)
        .order_by(KnowledgePhoto.position.asc(), KnowledgePhoto.id.asc())
        .all()
    )


def count_photos(knowledge_id: int) -> int:
    return KnowledgePhoto.query.filter_by(
        knowledge_id=knowledge_id, is_deleted=False
    ).count()


def add_photo(
    *,
    knowledge_id: int,
    file: FileStorage,
    caption: str | None = None,
) -> KnowledgePhoto:
    """Upload a photo for a knowledge entry."""
    k = db.session.get(Knowledge, knowledge_id)
    if not k or k.is_deleted:
        raise ValueError("Knowledge not found.")

    n = count_photos(knowledge_id)
    if n >= MAX_PHOTOS_PER_KNOWLEDGE:
        raise ValueError(f"အများဆုံး {MAX_PHOTOS_PER_KNOWLEDGE} ပုံပဲ ထည့်လို့ရပါတယ်။")

    # Save file via file_service
    meta = file_service.save_upload(file, category="image")

    # Next position
    last = (
        KnowledgePhoto.query
        .filter_by(knowledge_id=knowledge_id)
        .order_by(KnowledgePhoto.position.desc())
        .first()
    )
    next_pos = (last.position + 1) if last else 1

    photo = KnowledgePhoto(
        knowledge_id=knowledge_id,
        media_file_id=None,  # set below if you want to link MediaFile
        file_path=meta["file_path"],
        original_filename=meta["original_filename"],
        mime_type=meta.get("mime_type"),
        size_bytes=meta.get("size_bytes"),
        caption=(caption or "").strip() or None,
        position=next_pos,
    )
    db.session.add(photo)
    db.session.commit()

    audit_service.log(
        "knowledge.photo.add",
        entity_type="knowledge",
        entity_id=knowledge_id,
        details={"filename": meta["original_filename"], "photo_id": photo.id},
    )
    return photo


def delete_photo(photo_id: int) -> bool:
    p = db.session.get(KnowledgePhoto, photo_id)
    if not p:
        return False

    # Try remove from disk
    try:
        if p.file_path:
            file_service.delete_stored_file(p.file_path)
    except Exception:
        pass

    p.soft_delete()
    db.session.commit()
    audit_service.log(
        "knowledge.photo.delete",
        entity_type="knowledge_photo",
        entity_id=photo_id,
    )
    return True


def reorder(knowledge_id: int, ordered_ids: list[int]) -> None:
    """Reorder photos by list of photo IDs."""
    for i, pid in enumerate(ordered_ids, start=1):
        p = KnowledgePhoto.query.filter_by(
            id=pid, knowledge_id=knowledge_id
        ).first()
        if p:
            p.position = i
    db.session.commit()


def set_caption(photo_id: int, caption: str | None) -> None:
    p = db.session.get(KnowledgePhoto, photo_id)
    if p:
        p.caption = (caption or "").strip() or None
        db.session.commit()


def get_photos_for_knowledge_display(knowledge_id: int) -> list[dict]:
    """Serializable list for API/Telegram."""
    return [
        {
            "id": p.id,
            "position": p.position,
            "caption": p.caption,
            "file_path": p.file_path,
            "original_filename": p.original_filename,
            "telegram_file_id": p.telegram_file_id,
        }
        for p in list_photos(knowledge_id)
    ]


def add_photos_batch(
    *,
    knowledge_id: int,
    files: list,
    captions: list[str] | None = None,
) -> tuple[int, list[str]]:
    """Add multiple photos at once. Returns (saved_count, errors)."""
    saved = 0
    errors: list[str] = []

    for i, f in enumerate(files):
        if not f or not getattr(f, "filename", ""):
            continue
        try:
            cap = ""
            if captions and i < len(captions):
                cap = (captions[i] or "").strip()
            add_photo(knowledge_id=knowledge_id, file=f, caption=cap or None)
            saved += 1
        except ValueError as e:
            errors.append(f"{getattr(f, 'filename', '?')}: {e}")
        except Exception as e:
            errors.append(f"{getattr(f, 'filename', '?')}: {type(e).__name__}")

    return saved, errors


def save_telegram_file_id(photo_id: int, file_id: str) -> None:
    """Persist Telegram file_id for a photo (for cache)."""
    from app.extensions import db
    p = db.session.get(KnowledgePhoto, photo_id)
    if p and file_id:
        p.telegram_file_id = file_id
        db.session.commit()
