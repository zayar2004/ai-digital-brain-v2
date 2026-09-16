"""
Admin Broadcast.

Admin writes a message + optional photo → verified Telegram users get it.
Every send attempt is logged per recipient.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class BroadcastStatus:
    DRAFT = "DRAFT"
    SENDING = "SENDING"
    SENT = "SENT"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    ALL = (DRAFT, SENDING, SENT, PARTIAL, FAILED)


class Broadcast(BaseModel):
    __tablename__ = "broadcasts"

    message = db.Column(db.Text, nullable=True)
    has_photo = db.Column(db.Boolean, default=False, nullable=False)

    # Local file info (server-side)
    photo_path = db.Column(db.String(1024), nullable=True)
    photo_original_filename = db.Column(db.String(512), nullable=True)

    # Telegram file_id — for fast resend
    telegram_file_id = db.Column(db.String(512), nullable=True)

    status = db.Column(
        db.String(16), nullable=False, default=BroadcastStatus.DRAFT, index=True
    )

    # Filters (optional)
    filter_shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Stats
    recipient_count = db.Column(db.Integer, nullable=False, default=0)
    sent_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)

    sent_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    shop = db.relationship("Shop", lazy="joined")
    sent_by = db.relationship("User", lazy="joined")

    recipients = db.relationship(
        "BroadcastRecipient",
        back_populates="broadcast",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    photos_rel = db.relationship(
        "BroadcastPhoto",
        back_populates="broadcast",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="BroadcastPhoto.position",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Broadcast {self.id} status={self.status}>"


class RecipientStatus:
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class BroadcastRecipient(BaseModel):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        db.Index("ix_bcast_recip_bcast", "broadcast_id", "status"),
    )

    broadcast_id = db.Column(
        db.Integer, db.ForeignKey("broadcasts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    telegram_user_id = db.Column(db.BigInteger, nullable=False, index=True)
    telegram_display_name = db.Column(db.String(255), nullable=True)

    status = db.Column(
        db.String(16), nullable=False, default=RecipientStatus.PENDING, index=True
    )
    error = db.Column(db.String(512), nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    broadcast = db.relationship("Broadcast", back_populates="recipients")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BroadcastRecipient b={self.broadcast_id} tg={self.telegram_user_id} {self.status}>"


class BroadcastPhoto(BaseModel):
    """Each photo in a broadcast (up to 10)."""
    __tablename__ = "broadcast_photos"
    __table_args__ = (
        db.Index("ix_bphoto_broadcast", "broadcast_id", "position"),
    )

    broadcast_id = db.Column(
        db.Integer, db.ForeignKey("broadcasts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Local file
    file_path = db.Column(db.String(1024), nullable=False)
    original_filename = db.Column(db.String(512), nullable=True)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # Telegram file_id (cache)
    telegram_file_id = db.Column(db.String(512), nullable=True, index=True)

    position = db.Column(db.Integer, nullable=False, default=1)

    broadcast = db.relationship("Broadcast", back_populates="photos_rel")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BroadcastPhoto b={self.broadcast_id} pos={self.position}>"


# Add relationship on Broadcast model — done via backref in __init__
