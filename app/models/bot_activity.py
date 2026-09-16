"""Bot activity log — for Live Monitor."""
from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class BotActivity(BaseModel):
    __tablename__ = "bot_activity"
    __table_args__ = (
        db.Index("ix_bot_activity_created", "created_at"),
        db.Index("ix_bot_activity_user", "telegram_user_id"),
        db.Index("ix_bot_activity_shop", "shop_code"),
    )

    telegram_user_id = db.Column(db.BigInteger, nullable=True, index=True)
    first_name = db.Column(db.String(255), nullable=True)
    shop_code = db.Column(db.String(16), nullable=True, index=True)
    activity_type = db.Column(db.String(32), nullable=True)
    content = db.Column(db.Text, nullable=True)
    response_ok = db.Column(db.Boolean, default=True)
    chat_id = db.Column(db.BigInteger, nullable=True)
    thread_id = db.Column(db.Integer, nullable=True)

    # ★ Bot response
    response = db.Column(db.Text, nullable=True)
    response_type = db.Column(db.String(32), nullable=True)
