"""Excel reader tests."""

import tempfile
from pathlib import Path

from openpyxl import Workbook


def _make_xlsx(headers, rows, out_path):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(out_path)


def test_excel_reader_basic():
    from app.ingestion.excel_reader import read_excel

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "test.xlsx"
        _make_xlsx(
            ["Machine Name", "Unit", "Machine Code"],
            [["Crocodile Tycoon", "P6", "CT-P6-015"]],
            path,
        )
        sheets = read_excel(path)
        assert len(sheets) == 1
        assert len(sheets[0].rows) == 1
        row = sheets[0].rows[0]
        assert row.values.get("machine_name") == "Crocodile Tycoon"
        assert row.values.get("code") == "CT-P6-015"


def test_excel_reader_myanmar_headers():
    from app.ingestion.excel_reader import read_excel

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "test.xlsx"
        _make_xlsx(
            ["Error Message (English)", "မြန်မာဘာသာပြန်", "ဖြေရှင်းနည်း"],
            [["Ball Jam", "ဘောလုံးပိတ်", "Sensor စစ်ပါ"]],
            path,
        )
        sheets = read_excel(path)
        assert len(sheets) >= 1


def test_error_excel_ingestor():
    from app.ingestion.error_excel_ingestor import read_error_excel

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "Dragon_Blade_Errors.xlsx"
        _make_xlsx(
            ["No.", "Error Message (English)", "မြန်မာဘာသာပြန်",
             "ဖြစ်နိုင်သောအကြောင်း", "ဖြေရှင်းနည်း", "မှတ်ချက်"],
            [
                [1, "Ball Jam", "ဘောလုံးပိတ်", "Sensor စစ်", "1. Sensor\n2. Motor", ""],
                [2, "Empty Ball", "ဘောလုံးမရှိ", "Motor စစ်", "Motor စစ်ပါ", ""],
            ],
            path,
        )
        r = read_error_excel(path)
        assert len(r.candidates) == 2
        assert r.candidates[0].error_name_en == "Ball Jam"
        assert r.candidates[0].error_code.startswith("BJ-")
        assert "Dragon Blade" in (r.machine_name or "")
