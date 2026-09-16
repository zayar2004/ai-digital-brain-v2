"""
MediaFile model.

Tracks uploaded documents, Excel, PDF, Word, and photos.
Original filename is preserved as metadata.
Actual storage path is never exposed to users directly.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class MediaCategory:
    DOCUMENT = "document"
    EXCEL = "excel"
    PDF = "pdf"
    WORD = "word"
    IMAGE = "image"
    OTHER = "other"


class MediaFile(BaseModel):
    __tablename__ = "media_files"
    __table_args__ = (
        db.Index("ix_media_shop_category", "shop_id", "category"),
        db.Index("ix_media_hash", "file_hash"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    error_knowledge_id = db.Column(
        db.Integer, db.ForeignKey("error_knowledge.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    error_case_id = db.Column(
        db.Integer, db.ForeignKey("error_cases.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    knowledge_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    original_filename = db.Column(db.String(512), nullable=False)
    stored_filename = db.Column(db.String(512), nullable=False)
    file_path = db.Column(db.String(1024), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True, index=True)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    category = db.Column(db.String(32), nullable=False, default=MediaCategory.OTHER, index=True)
    caption = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    uploaded_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")
    uploaded_by = db.relationship("User", lazy="joined")

    def to_dict(self, include_path: bool = False) -> dict:
        d = {
            "id": self.id,
            "shop": self.shop.code if self.shop else None,
            "category": self.category,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "caption": self.caption,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_path:
            d["file_path"] = self.file_path
        return d

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MediaFile {self.original_filename}>"
