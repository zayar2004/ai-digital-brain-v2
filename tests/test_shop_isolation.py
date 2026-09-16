"""Shop isolation tests (critical security)."""

from app.security.shop_scope import normalize_shop_code, resolve_shop


def test_normalize_shop():
    assert normalize_shop_code("a3") == "A3"
    assert normalize_shop_code(" A 3 ") == "A3"
    assert normalize_shop_code("3") == "A3"
    assert normalize_shop_code("A15") is None
    assert normalize_shop_code("") is None


def test_explicit_overrides_verified():
    r = resolve_shop(explicit="A5", verified_codes=["A3"], context_code=None)
    assert r.code == "A5"
    assert r.source == "explicit"


def test_verified_when_no_explicit():
    r = resolve_shop(explicit=None, verified_codes=["A3"], context_code=None)
    assert r.code == "A3"
    assert r.source == "verified_mapping"


def test_no_guess_on_ambiguous_verified():
    r = resolve_shop(explicit=None, verified_codes=["A1", "A3"], context_code=None)
    assert r.code is None
    assert r.candidates == ["A1", "A3"]


def test_context_fallback():
    r = resolve_shop(explicit=None, verified_codes=None, context_code="A7")
    assert r.code == "A7"
    assert r.source == "context"


def test_nothing():
    r = resolve_shop(explicit=None, verified_codes=None, context_code=None)
    assert r.code is None
    assert r.source == "none"
