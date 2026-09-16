"""
Shop model + Telegram user mapping.

Shops are A1 - A13. Every shop-scoped record references shop_id.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class Shop(BaseModel):
    """A workplace shop (A1 - A13)."""

    __tablename__ = "shops"

    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Shop {self.code}>"

    @classmethod
    def all_codes(cls) -> list[str]:
        return [f"A{i}" for i in range(1, 14)]


class TelegramUser(BaseModel):
    """
    Telegram user identity.

    IMPORTANT: identity is the numeric telegram_user_id,
    NEVER the username or display name.
    """

    __tablename__ = "telegram_users"

    telegram_user_id = db.Column(
        db.BigInteger, unique=True, nullable=False, index=True
    )
    telegram_username = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_blocked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    language = db.Column(db.String(8), default="my", nullable=False)

    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    shop_links = db.relationship(
        "TelegramUserShop",
        back_populates="telegram_user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def verified_shop_codes(self) -> list[str]:
        """Return the list of shop codes this user is verified for."""
        return [link.shop.code for link in self.shop_links if link.shop and link.is_active]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TelegramUser {self.telegram_user_id}>"


class TelegramUserShop(BaseModel):
    """Verified mapping between a Telegram user and one Shop."""

    __tablename__ = "telegram_user_shops"
    __table_args__ = (
        db.UniqueConstraint(
            "telegram_user_id", "shop_id", name="uq_tg_user_shop"
        ),
    )

    telegram_user_id = db.Column(
        db.Integer,
        db.ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    telegram_user = db.relationship("TelegramUser", back_populates="shop_links")
    shop = db.relationship("Shop", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TGUserShop u={self.telegram_user_id} s={self.shop_id}>"
