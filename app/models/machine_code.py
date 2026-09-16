"""
Machine Code model + import source tracking.

Machine codes are primarily imported from Admin Excel files.
Every imported row keeps source traceability:
    source_file, source_sheet, source_row
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class MachineCodeSource(BaseModel):
    """Represents one uploaded Excel file used to import machine codes."""

    __tablename__ = "machine_code_sources"

    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    original_filename = db.Column(db.String(512), nullable=False)
    stored_filename = db.Column(db.String(512), nullable=False)
    file_path = db.Column(db.String(1024), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True, index=True)

    uploaded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    sheet_count = db.Column(db.Integer, nullable=False, default=0)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    imported_count = db.Column(db.Integer, nullable=False, default=0)
    skipped_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    conflict_count = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(
        db.String(32), nullable=False, default="UPLOADED", index=True
    )  # UPLOADED, PROCESSING, REVIEW_REQUIRED, APPROVED, FAILED

    notes = db.Column(db.Text, nullable=True)

    shop = db.relationship("Shop", lazy="joined")
    uploaded_by = db.relationship("User", lazy="joined")
    codes = db.relationship(
        "MachineCode",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MachineCodeSource {self.original_filename} shop={self.shop_id}>"


class MachineCode(BaseModel):
    """One row of machine-code data."""

    __tablename__ = "machine_codes"
    __table_args__ = (
        db.Index("ix_mcode_shop_machine", "shop_id", "machine_id"),
        db.Index("ix_mcode_code", "code"),
        db.UniqueConstraint(
            "shop_id", "machine_id", "unit", "code",
            name="uq_mcode_shop_machine_unit_code",
        ),
    )

    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id = db.Column(
        db.Integer,
        db.ForeignKey("machine_code_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Canonical fields (extracted/normalized)
    machine_name = db.Column(db.String(255), nullable=True, index=True)
    model = db.Column(db.String(128), nullable=True, index=True)
    unit = db.Column(db.String(64), nullable=True, index=True)
    code = db.Column(db.String(255), nullable=False, index=True)

    # Source traceability
    source_sheet = db.Column(db.String(255), nullable=True)
    source_row = db.Column(db.Integer, nullable=True)

    # Raw values (preserve original)
    raw_data = db.Column(db.Text, nullable=True)  # JSON string

    # Status / approval
    status = db.Column(
        db.String(32), nullable=False, default="PENDING", index=True
    )  # PENDING, APPROVED, ARCHIVED
    confidence = db.Column(db.Float, nullable=True, default=1.0)

    # Relationships
    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")
    source = db.relationship("MachineCodeSource", back_populates="codes")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MachineCode {self.code} shop={self.shop_id} unit={self.unit}>"

    def to_result_dict(self) -> dict:
        """Return a compact dict suitable for API/Telegram responses."""
        return {
            "id": self.id,
            "shop": self.shop.code if self.shop else None,
            "machine": self.machine_name or (self.machine.name if self.machine else None),
            "model": self.model,
            "unit": self.unit,
            "code": self.code,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "status": self.status,
        }
