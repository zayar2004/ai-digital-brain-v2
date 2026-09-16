"""
WorkReport model.

One report = one dated snapshot of workplace metrics.
Never overwrites previous reports.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class ReportStatus:
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
    ALL = (DRAFT, PENDING, APPROVED, ARCHIVED)


class WorkReport(BaseModel):
    __tablename__ = "work_reports"
    __table_args__ = (
        db.Index("ix_report_shop_date", "shop_id", "report_date"),
        db.UniqueConstraint("shop_id", "report_date",
                            name="uq_report_shop_date"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    report_date = db.Column(db.Date, nullable=False, index=True)
    title = db.Column(db.String(512), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Structured metrics — JSON text
    metrics_json = db.Column(db.Text, nullable=True)

    original_content = db.Column(db.Text, nullable=True)
    myanmar_content = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)
    source_type = db.Column(db.String(32), nullable=True)
    source_file = db.Column(db.String(512), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    shop = db.relationship("Shop", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkReport {self.shop.code if self.shop else '?'} {self.report_date}>"
