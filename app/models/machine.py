"""
Machine model + aliases.

A machine belongs to exactly one Shop (strict isolation).
Aliases provide alternative names / abbreviations / keywords for search.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class Machine(BaseModel):
    """A physical machine (game, unit, device) inside a shop."""

    __tablename__ = "machines"
    __table_args__ = (
        db.UniqueConstraint("shop_id", "name", name="uq_machine_shop_name"),
        db.Index("ix_machine_shop_name", "shop_id", "name"),
    )

    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(255), nullable=False, index=True)
    model = db.Column(db.String(128), nullable=True, index=True)
    unit = db.Column(db.String(64), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(32), nullable=False, default="ACTIVE", index=True
    )  # ACTIVE, MAINTENANCE, RETIRED

    # Relationships
    shop = db.relationship("Shop", lazy="joined")
    aliases = db.relationship(
        "MachineAlias",
        back_populates="machine",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Machine {self.name} shop={self.shop_id}>"

    def all_names(self) -> list[str]:
        """Return canonical name + every alias value for search."""
        names = [self.name]
        if self.model:
            names.append(self.model)
        for a in self.aliases:
            if a.alias and a.alias not in names:
                names.append(a.alias)
        return names


class MachineAlias(BaseModel):
    """Alternative name / abbreviation / keyword for a machine."""

    __tablename__ = "machine_aliases"
    __table_args__ = (
        db.UniqueConstraint("machine_id", "alias", name="uq_alias_machine_alias"),
        db.Index("ix_alias_lookup", "alias"),
    )

    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias = db.Column(db.String(255), nullable=False, index=True)
    alias_type = db.Column(
        db.String(32), nullable=False, default="KEYWORD"
    )  # SHORT, ABBREVIATION, ALTERNATIVE, KEYWORD, MISSPELLING

    machine = db.relationship("Machine", back_populates="aliases")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MachineAlias {self.alias}>"
