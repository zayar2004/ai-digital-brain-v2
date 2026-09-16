"""Machine code search tests."""

from app.extensions import db
from app.models import Machine, MachineCode, Shop
from app.services import machine_code_service as MCS


def test_search_exact(app, db_session):
    with app.app_context():
        a3 = Shop.query.filter_by(code="A3").first()
        m = Machine(shop_id=a3.id, name="Test CT", model="P6", unit="P6")
        db_session.add(m); db_session.flush()
        mc = MachineCode(
            shop_id=a3.id, machine_id=m.id, machine_name="Test CT",
            model="P6", unit="P6", code="CT-P6-999", status="APPROVED",
        )
        db_session.add(mc); db_session.commit()

        r = MCS.search_machine_codes(
            shop_id=a3.id, shop_code="A3",
            query="CT-P6-999", only_approved=False,
        )
        assert r.total >= 1
        assert any(m.code == "CT-P6-999" for m in r.matches)


def test_search_partial(app, db_session):
    with app.app_context():
        a3 = Shop.query.filter_by(code="A3").first()
        r = MCS.search_machine_codes(
            shop_id=a3.id, shop_code="A3",
            query="CT", only_approved=False,
        )
        assert r.total >= 1


def test_strict_shop_isolation(app, db_session):
    """A3 code must NOT appear when searching A5."""
    with app.app_context():
        a5 = Shop.query.filter_by(code="A5").first()
        r = MCS.search_machine_codes(
            shop_id=a5.id, shop_code="A5",
            query="CT-P6-999", only_approved=False,
        )
        assert r.total == 0
