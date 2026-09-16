"""Grounding (anti-hallucination) tests."""

from app.ai import grounding


def test_good_answer():
    ctx = "Error 07 = coin empty. Machine CT-P6-015. Unit P3."
    ans = "Error 07 က coin empty ဖြစ်ပါတယ်။"
    r = grounding.check(ans, ctx)
    assert r.ok
    assert r.problems == []


def test_bad_error_code():
    ctx = "Error 07 = coin empty."
    ans = "Error 99 ဖြစ်ပါတယ်။"
    r = grounding.check(ans, ctx)
    assert not r.ok
    assert any("99" in p for p in r.problems)


def test_bad_machine_code():
    ctx = "Machine CT-P6-015."
    ans = "CT-P9-999 ကို စစ်ပါ။"
    r = grounding.check(ans, ctx)
    assert not r.ok
    assert any("CT-P9-999" in p for p in r.problems)


def test_bad_unit():
    ctx = "Unit P3."
    ans = "P9 ကို စစ်ပါ။"
    r = grounding.check(ans, ctx)
    assert not r.ok


def test_empty_answer_ok():
    r = grounding.check("", "anything")
    assert r.ok
