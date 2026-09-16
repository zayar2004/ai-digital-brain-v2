"""Unified search tests."""

from app.search import unified_search as US


def test_empty_query(app):
    with app.app_context():
        r = US.search(query="", shop_id=None, shop_code=None)
        assert r.total == 0


def test_search_returns_result_object(app):
    with app.app_context():
        r = US.search(query="CT", shop_id=None, shop_code=None, only_approved=False)
        assert isinstance(r.hits, list)
        assert isinstance(r.total, int)
