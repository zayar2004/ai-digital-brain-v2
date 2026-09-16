"""Standalone smoke test for the Excel import pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)  # ensure cwd == project root

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import MachineCode, MachineCodeSource, Shop  # noqa: E402
from app.ingestion import machine_code_importer as mci  # noqa: E402


def main() -> int:
    excel_path = "Machine_Code_A3_test.xlsx"
    if not Path(excel_path).exists():
        print(f"ERROR: {excel_path} not found. Run the file-creation step first.")
        return 1

    app = create_app()
    with app.app_context():
        a3 = Shop.query.filter_by(code="A3").first()
        if not a3:
            print("ERROR: Shop A3 not found.")
            return 1

        # clean previous test data for A3
        MachineCode.query.filter_by(shop_id=a3.id).delete()
        MachineCodeSource.query.filter_by(shop_id=a3.id).delete()
        db.session.commit()

        src = MachineCodeSource(
            shop_id=a3.id,
            original_filename=excel_path,
            stored_filename="test.xlsx",
            file_path=excel_path,
            uploaded_by_id=1,
            status="UPLOADED",
        )
        db.session.add(src)
        db.session.commit()

        pv = mci.parse_excel_for_preview(excel_path, shop=a3, source_id=src.id)
        print("Sheets:     ", pv.sheets)
        print("Valid:      ", len(pv.valid_rows))
        print("Invalid:    ", len(pv.invalid_rows))
        print("Duplicates: ", len(pv.duplicate_rows))
        print("Conflicts:  ", len(pv.conflict_rows))

        stats = mci.commit_import(src, pv.valid_rows)
        print("Stats:      ", stats)

        approved = mci.approve_source(src.id)
        print("Approved:   ", approved)

        rows = MachineCode.query.filter_by(shop_id=a3.id).order_by(MachineCode.id).all()
        print("Codes in A3:")
        for r in rows:
            print(f"  {r.machine_name} | unit={r.unit} | code={r.code}")

        # cleanup
        MachineCode.query.filter_by(shop_id=a3.id).delete()
        MachineCodeSource.query.filter_by(id=src.id).delete()
        db.session.commit()
        print("Cleanup: done")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
