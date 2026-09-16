"""
Error Knowledge + Error Cases.

ErrorKnowledge  - general/official troubleshooting knowledge
ErrorCase       - a real-world incident report

These are DIFFERENT.
A single ErrorCase must NEVER be automatically promoted
to a universal rule.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class ErrorKnowledgeStatus:
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
    ALL = (DRAFT, PENDING, APPROVED, ARCHIVED)


class ErrorKnowledge(BaseModel):
    __tablename__ = "error_knowledge"
    __table_args__ = (
        db.Index("ix_errk_shop_machine", "shop_id", "machine_id"),
        db.Index("ix_errk_code", "error_code"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    machine_name = db.Column(db.String(255), nullable=True, index=True)
    model = db.Column(db.String(128), nullable=True, index=True)
    unit = db.Column(db.String(64), nullable=True, index=True)

    error_code = db.Column(db.String(64), nullable=True, index=True)
    error_name = db.Column(db.String(512), nullable=True)

    symptoms = db.Column(db.Text, nullable=True)
    cause = db.Column(db.Text, nullable=True)
    check_steps = db.Column(db.Text, nullable=True)
    solution = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    original_language = db.Column(db.String(8), nullable=True, default="my")
    original_content = db.Column(db.Text, nullable=True)
    myanmar_content = db.Column(db.Text, nullable=True)
    english_content = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(32), nullable=False, default=ErrorKnowledgeStatus.DRAFT, index=True)
    confidence = db.Column(db.Float, nullable=True, default=1.0)

    source_type = db.Column(db.String(32), nullable=True)
    source_file = db.Column(db.String(512), nullable=True)
    source_page = db.Column(db.String(32), nullable=True)
    source_sheet = db.Column(db.String(128), nullable=True)
    source_row = db.Column(db.Integer, nullable=True)
    source_reference = db.Column(db.String(512), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)

    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ErrorKnowledge {self.error_code} shop={self.shop_id}>"


class ErrorCase(BaseModel):
    """
    A real-world incident report.

    IMPORTANT: these are historical observations, NOT universal rules.
    """

    __tablename__ = "error_cases"
    __table_args__ = (
        db.Index("ix_errcase_shop_machine", "shop_id", "machine_id"),
        db.Index("ix_errcase_code", "error_code"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    error_knowledge_id = db.Column(
        db.Integer, db.ForeignKey("error_knowledge.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    machine_name = db.Column(db.String(255), nullable=True, index=True)
    model = db.Column(db.String(128), nullable=True, index=True)
    unit = db.Column(db.String(64), nullable=True, index=True)

    error_code = db.Column(db.String(64), nullable=True, index=True)
    problem = db.Column(db.Text, nullable=True)     # what admin reported
    finding = db.Column(db.Text, nullable=True)     # what was found
    action_taken = db.Column(db.Text, nullable=True)
    result = db.Column(db.Text, nullable=True)

    original_content = db.Column(db.Text, nullable=True)
    myanmar_content = db.Column(db.Text, nullable=True)

    case_date = db.Column(db.DateTime(timezone=True), nullable=True)

    status = db.Column(db.String(32), nullable=False, default="PENDING", index=True)
    confidence = db.Column(db.Float, nullable=True, default=1.0)

    source_type = db.Column(db.String(32), nullable=True)
    source_file = db.Column(db.String(512), nullable=True)
    source_reference = db.Column(db.String(512), nullable=True)

    # ★ Photo support (added for admin case photos)
    photo_path = db.Column(db.String(1024), nullable=True)          # primary photo path
    photo_paths = db.Column(db.Text, nullable=True)                 # JSON list of all photos
    telegram_file_id = db.Column(db.String(512), nullable=True)     # cached TG file_id

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")
    error_knowledge = db.relationship("ErrorKnowledge", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ErrorCase code={self.error_code} shop={self.shop_id}>"
