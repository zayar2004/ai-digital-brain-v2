"""
Knowledge photos — up to 10 per Knowledge entry.

Admin uploads photos linked to a Knowledge.
When a user (Bot) searches and the name matches, photos are sent.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel

MAX_PHOTOS_PER_KNOWLEDGE = 10


class KnowledgePhoto(BaseModel):
    __tablename__ = "knowledge_photos"
    __table_args__ = (
        db.Index("ix_kphoto_knowledge", "knowledge_id", "position"),
    )

    knowledge_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    media_file_id = db.Column(
        db.Integer, db.ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Telegram file_id (once uploaded via bot)
    telegram_file_id = db.Column(db.String(512), nullable=True, index=True)

    # Stored file info (from media_files)
    file_path = db.Column(db.String(1024), nullable=True)
    original_filename = db.Column(db.String(512), nullable=True)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    caption = db.Column(db.String(512), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=1)

    knowledge = db.relationship("Knowledge", backref="photos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgePhoto k={self.knowledge_id} pos={self.position}>"
