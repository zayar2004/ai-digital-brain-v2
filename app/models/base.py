"""
Shared model mixins and base classes.

All models should inherit from `BaseModel` to get:
- id (auto-increment primary key)
- created_at / updated_at (UTC-aware timestamps)
- soft delete (is_deleted, deleted_at)
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class BaseModel(db.Model):
    """Abstract base model with common columns."""

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        """Mark this record as deleted without removing it."""
        self.is_deleted = True
        self.deleted_at = utcnow()

    def restore(self) -> None:
        """Un-delete a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None

    def to_dict(self, exclude: tuple[str, ...] = ()) -> dict:
        """Serialize to a dictionary. Subclasses may override."""
        result = {}
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            value = getattr(self, col.name, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[col.name] = value
        return result

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} id={self.id}>"
