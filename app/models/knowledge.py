"""
Knowledge models.

Knowledge        - general approved knowledge (facts, procedures)
KnowledgeVersion - change history (never silently overwrite)
KnowledgeConflict - when two approved sources disagree
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class KnowledgeStatus:
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
    ALL = (DRAFT, PENDING, APPROVED, ARCHIVED)


class Knowledge(BaseModel):
    __tablename__ = "knowledge"
    __table_args__ = (
        db.Index("ix_knowledge_shop_status", "shop_id", "status"),
        db.Index("ix_knowledge_machine", "machine_id"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    title = db.Column(db.String(512), nullable=False, index=True)
    category = db.Column(db.String(64), nullable=True, index=True)

    original_language = db.Column(db.String(8), nullable=True, default="my")
    original_content = db.Column(db.Text, nullable=True)
    myanmar_content = db.Column(db.Text, nullable=True)
    english_content = db.Column(db.Text, nullable=True)

    # Machine-related
    model = db.Column(db.String(128), nullable=True, index=True)
    unit = db.Column(db.String(64), nullable=True, index=True)
    error_code = db.Column(db.String(64), nullable=True, index=True)

    # Classification
    status = db.Column(db.String(32), nullable=False, default=KnowledgeStatus.DRAFT, index=True)
    confidence = db.Column(db.Float, nullable=True, default=1.0)

    # Effective dates
    effective_from = db.Column(db.DateTime(timezone=True), nullable=True)
    effective_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # Source traceability
    source_type = db.Column(db.String(32), nullable=True)  # upload | manual | excel | pdf | image
    source_file = db.Column(db.String(512), nullable=True)
    source_page = db.Column(db.String(32), nullable=True)
    source_sheet = db.Column(db.String(128), nullable=True)
    source_row = db.Column(db.Integer, nullable=True)
    source_reference = db.Column(db.String(512), nullable=True)

    # Approval
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    version = db.Column(db.Integer, nullable=False, default=1)

    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_id], lazy="joined")
    approved_by = db.relationship("User", foreign_keys=[approved_by_id], lazy="joined")

    versions = db.relationship(
        "KnowledgeVersion", back_populates="knowledge",
        cascade="all, delete-orphan", lazy="selectin",
        order_by="KnowledgeVersion.version.desc()",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Knowledge {self.id} {self.title[:30]!r}>"


class KnowledgeVersion(BaseModel):
    __tablename__ = "knowledge_versions"

    knowledge_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version = db.Column(db.Integer, nullable=False)

    # Snapshot fields
    title = db.Column(db.String(512), nullable=False)
    original_content = db.Column(db.Text, nullable=True)
    myanmar_content = db.Column(db.Text, nullable=True)
    english_content = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False)
    confidence = db.Column(db.Float, nullable=True)

    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason = db.Column(db.Text, nullable=True)

    knowledge = db.relationship("Knowledge", back_populates="versions")
    changed_by = db.relationship("User", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeVersion k={self.knowledge_id} v={self.version}>"


class KnowledgeConflictStatus:
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class KnowledgeConflict(BaseModel):
    __tablename__ = "knowledge_conflicts"

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    knowledge_a_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    knowledge_b_id = db.Column(
        db.Integer, db.ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default=KnowledgeConflictStatus.OPEN, index=True)

    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)

    knowledge_a = db.relationship("Knowledge", foreign_keys=[knowledge_a_id])
    knowledge_b = db.relationship("Knowledge", foreign_keys=[knowledge_b_id])
    shop = db.relationship("Shop", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeConflict a={self.knowledge_a_id} b={self.knowledge_b_id}>"
