"""Error extraction / code derivation tests."""

from app.ingestion.error_excel_ingestor import _derive_error_code, _make_title, ErrorRow


def test_derive_error_code():
    assert _derive_error_code("Marble Shooting Device Abnormal (Ball Jam)", "1") == "MSDAB-1"
    # "Pusher Abnormality (Motor)" → PAM-3 (P-A-M)
    assert _derive_error_code("Pusher Abnormality (Motor)", "3") == "PAM-3"
    assert _derive_error_code("Simple Error", "1") == "SE-1"


def test_make_title():
    row = ErrorRow(row_number=2, no="1", error_name_en="Ball Jam")
    assert _make_title(row) == "#1 Ball Jam"

    row2 = ErrorRow(row_number=3, no="", error_name_en="")
    assert _make_title(row2) == "Error"


def test_row_content_solution_only():
    from app.ingestion.error_excel_ingestor import _make_content
    row = ErrorRow(
        row_number=1,
        error_name_en="Ball Jam",
        solution="1. Sensor စစ်ပါ\n2. Motor စစ်ပါ",
    )
    content = _make_content(row)
    assert "Sensor" in content
    assert "Ball Jam" not in content  # only solution
