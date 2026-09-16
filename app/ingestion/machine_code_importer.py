"""
Machine Code Excel import pipeline.

Flow:
    upload → select shop → read all sheets → detect headers
    → normalize rows → validate → detect duplicates
    → detect conflicts → preview → (admin approve) → save

Smart parsing:
    A bare "code" cell like "M_SLOT_ALADDIN_008" is split into:
        full_code = "M_SLOT_ALADDIN_008"
        machine_name_hint = "M SLOT ALADDIN"
        unit_hint = "008"
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.extensions import db
from app.ingestion.excel_reader import read_excel
from app.models import MachineCode, MachineCodeSource, Shop
from app.services import machine_service


# ----------------------------------------------------------------
# Code decomposition
# ----------------------------------------------------------------
_CODE_SPLIT_RE = re.compile(r"^(?P<prefix>.+?)_(?P<suffix>\d{1,6})$")


def decompose_code(raw: str) -> tuple[str, str | None, str | None]:
    """
    Split a code like 'M_SLOT_ALADDIN_008' into:
        full_code, machine_name_hint, unit_hint

    Returns (full_code, machine_hint_or_None, unit_or_None).
    If it doesn't look like a compound code, returns (raw, None, None).
    """
    if not raw:
        return ("", None, None)
    s = str(raw).strip()
    m = _CODE_SPLIT_RE.match(s)
    if not m:
        return (s, None, None)
    prefix = m.group("prefix")
    suffix = m.group("suffix")
    # Convert underscores to spaces for the machine hint
    machine_hint = prefix.replace("_", " ").strip()
    # Clean up multiple spaces
    machine_hint = re.sub(r"\s+", " ", machine_hint)
    if not machine_hint:
        return (s, None, None)
    return (s, machine_hint, suffix)


@dataclass
class ParsedRow:
    sheet: str
    row_number: int
    machine_name: str | None = None
    model: str | None = None
    unit: str | None = None
    code: str | None = None
    aliases: list[str] = field(default_factory=list)
    arrival_date: str | None = None
    location: str | None = None
    raw: dict[str, str] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return bool(self.code)


@dataclass
class ImportPreview:
    source_id: int
    shop_code: str
    total_rows: int = 0
    valid_rows: list[ParsedRow] = field(default_factory=list)
    invalid_rows: list[ParsedRow] = field(default_factory=list)
    duplicate_rows: list[ParsedRow] = field(default_factory=list)
    conflict_rows: list[ParsedRow] = field(default_factory=list)
    sheets: list[str] = field(default_factory=list)


def _resolve_machine_and_unit(
    *,
    explicit_machine: str | None,
    explicit_unit: str | None,
    code: str,
) -> tuple[str | None, str | None]:
    """
    Return (machine_name, unit) using best-effort resolution.

    Priority:
        - explicit machine column wins
        - otherwise, derive from code
    """
    if explicit_machine:
        return (explicit_machine, explicit_unit)

    full_code, hint_machine, hint_unit = decompose_code(code)
    return (hint_machine, explicit_unit or hint_unit)


def parse_excel_for_preview(path: str, shop: Shop,
                            source_id: int) -> ImportPreview:
    """Parse an uploaded Excel file and return a preview."""
    sheets = read_excel(path)
    preview = ImportPreview(source_id=source_id, shop_code=shop.code)
    preview.sheets = [s.name for s in sheets]

    # Build set of existing (code, unit) pairs in this shop for duplicate/conflict check
    existing_pairs: set[tuple[str, str]] = set()
    for mc in MachineCode.query.filter_by(shop_id=shop.id).all():
        existing_pairs.add(((mc.code or "").upper(), (mc.unit or "").upper()))

    seen_in_file: set[tuple[str, str]] = set()

    for s in sheets:
        for row in s.rows:
            raw_code = (row.values.get("code") or "").strip() or None
            if not raw_code:
                preview.total_rows += 1
                preview.invalid_rows.append(
                    ParsedRow(sheet=row.sheet, row_number=row.row_number, raw=row.values)
                )
                continue

            machine_in, unit_in = _resolve_machine_and_unit(
                explicit_machine=(row.values.get("machine_name") or "").strip() or None,
                explicit_unit=(row.values.get("unit") or "").strip() or None,
                code=raw_code,
            )

            parsed = ParsedRow(
                sheet=row.sheet,
                row_number=row.row_number,
                machine_name=machine_in,
                model=(row.values.get("model") or "").strip() or None,
                unit=unit_in,
                code=raw_code,
                aliases=[a.strip() for a in (row.values.get("alias") or "").split(",") if a.strip()],
                arrival_date=(row.values.get("arrival_date") or "").strip() or None,
                location=(row.values.get("location") or "").strip() or None,
                raw=row.values,
            )
            preview.total_rows += 1

            key = ((parsed.code or "").upper(), (parsed.unit or "").upper())

            # duplicate inside file
            if key in seen_in_file:
                preview.duplicate_rows.append(parsed)
                continue

            # conflict: same code, different unit
            same_code_other_unit = any(
                c == key[0] and u != key[1] for (c, u) in existing_pairs
            ) or any(c == key[0] and u != key[1] for (c, u) in seen_in_file)
            if same_code_other_unit:
                preview.conflict_rows.append(parsed)
                continue

            seen_in_file.add(key)
            preview.valid_rows.append(parsed)

    return preview


def commit_import(source: MachineCodeSource, rows: list[ParsedRow]) -> dict:
    """
    Write parsed rows to the database.

    ★ REPLACE MODE: Deletes all existing codes for this shop
       before importing the new ones.

    Row-level isolation: one bad row does not roll back the entire batch.
    Auto-creates machines if missing.
    """
    stats = {
        "imported": 0,
        "deleted": 0,
        "machines_created": 0,
        "machines_linked": 0,
        "failed": 0,
        "errors": [],
    }

    # ★ REPLACE MODE: Delete all existing codes for this shop
    existing_codes = MachineCode.query.filter_by(
        shop_id=source.shop_id
    ).all()
    stats["deleted"] = len(existing_codes)
    for mc in existing_codes:
        db.session.delete(mc)
    db.session.flush()

    from app.models import Machine
    name_cache: dict[str, Machine] = {}

    for row in rows:
        try:
            machine: Machine | None = None
            if row.machine_name:
                key = row.machine_name.lower()
                machine = name_cache.get(key)
                if machine is None:
                    machine = machine_service.find_machine_in_shop(
                        source.shop_id, row.machine_name
                    )
                    if machine is None:
                        machine = Machine(
                            shop_id=source.shop_id,
                            name=row.machine_name,
                            model=row.model,
                            unit=row.unit,
                            status="ACTIVE",
                        )
                        db.session.add(machine)
                        db.session.flush()
                        stats["machines_created"] += 1
                    else:
                        stats["machines_linked"] += 1
                    name_cache[key] = machine

            mc = MachineCode(
                shop_id=source.shop_id,
                machine_id=machine.id if machine else None,
                source_id=source.id,
                machine_name=row.machine_name,
                model=row.model,
                unit=row.unit,
                code=row.code,
                source_sheet=row.sheet,
                source_row=row.row_number,
                raw_data=json.dumps(row.raw, ensure_ascii=False) if row.raw else None,
                status="APPROVED",  # ★ auto-approve
                confidence=1.0,
            )
            db.session.add(mc)
            db.session.flush()
            stats["imported"] += 1
        except Exception as e:
            db.session.rollback()
            stats["failed"] += 1
            if len(stats["errors"]) < 10:
                stats["errors"].append(
                    f"row {row.row_number} ({row.code}): {type(e).__name__}: {e}"
                )
            # Continue with next row

    source.status = "APPROVED"  # ★ auto-approve
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        source.status = "FAILED"
        source.notes = f"Final commit failed: {e}"
        db.session.commit()
        raise

    return stats


def approve_source(source_id: int) -> int:
    """Approve all PENDING codes belonging to a source. Returns count."""
    codes = MachineCode.query.filter_by(source_id=source_id, status="PENDING").all()
    for c in codes:
        c.status = "APPROVED"
    db.session.commit()
    return len(codes)
