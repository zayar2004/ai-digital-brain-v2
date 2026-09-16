"""
Audit log.

Track important actions: login, create, update, delete, approve,
archive, upload, import, user changes, permission changes,
shop mapping changes, AI configuration changes.

NEVER log: passwords, API keys, Telegram tokens, secrets.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_actor_created", "actor_user_id", "created_at"),
        db.Index("ix_audit_action_created", "action", "created_at"),
    )

    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_label = db.Column(db.String(255), nullable=True)  # fallback: username at time

    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=True, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)

    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    details = db.Column(db.Text, nullable=True)  # JSON string (secrets already stripped)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    actor = db.relationship("User", lazy="joined")
    shop = db.relationship("Shop", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} by={self.actor_user_id}>"
