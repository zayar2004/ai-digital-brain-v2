"""Quick Teach rule-based extraction tests."""

from app.ingestion import quick_teach


def test_basic_extraction():
    text = "Carnival circus P3 Error 07 ပေါ်နေ၍ coin ကုန်နေတာ တွေ့ပြီး ပြန်ဖြည့်လိုက်တာ အဆင်ပြေသွားပါပြီ"
    r = quick_teach.extract(text)
    assert r.unit == "P3"
    assert r.error_code == "07"
    assert r.machine_name and "Carnival" in r.machine_name


def test_empty_text():
    r = quick_teach.extract("")
    assert r.unit is None
    assert r.error_code is None


def test_no_error():
    r = quick_teach.extract("Just a normal note.")
    assert r.unit is None
    assert r.error_code is None
