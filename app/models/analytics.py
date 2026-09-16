"""
Analytics models.

- SearchLog: every search query (via web or bot)
- EventLog: generic events (view, click, approve, etc.)
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class SearchLog(BaseModel):
    __tablename__ = "search_logs"
    __table_args__ = (
        db.Index("ix_searchlog_created", "created_at"),
        db.Index("ix_searchlog_query", "search_text"),
        db.Index("ix_searchlog_source", "source"),
    )

    search_text = db.Column(db.String(512), nullable=False, index=True)
    source = db.Column(db.String(32), nullable=False, default="web", index=True)
    # web | telegram | api
    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    telegram_user_id = db.Column(db.BigInteger, nullable=True, index=True)

    result_count = db.Column(db.Integer, nullable=False, default=0)
    kinds = db.Column(db.String(255), nullable=True)   # "error,machine,code"

    shop = db.relationship("Shop", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SearchLog {self.search_text[:30]!r} src={self.source}>"


class EventLog(BaseModel):
    __tablename__ = "event_logs"
    __table_args__ = (
        db.Index("ix_eventlog_created", "created_at"),
        db.Index("ix_eventlog_name", "name"),
    )

    name = db.Column(db.String(64), nullable=False, index=True)
    # view_knowledge | view_error | click_code | approve | ...

    entity_type = db.Column(db.String(64), nullable=True, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    details = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventLog {self.name}>"
