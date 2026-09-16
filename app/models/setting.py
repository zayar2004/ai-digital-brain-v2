"""Application-wide settings stored in DB (key-value)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class AppSetting(BaseModel):
    __tablename__ = "app_settings"

    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    value_type = db.Column(db.String(16), nullable=False, default="str")
    description = db.Column(db.String(512), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AppSetting {self.key}>"
