"""Task schedule tests."""

from datetime import date

from app.extensions import db
from app.models import Shop, Task
from app.services import task_service as TS
from app.services import task_nl_parser as TNP


def test_nl_parse_weekly_monday():
    p = TNP.parse("A3 Crocodile ကို တနင်္လာနေ့တိုင်း မနက် 9 နာရီ စစ်မယ်")
    assert p.frequency == "WEEKLY"
    assert p.weekday == 0
    assert p.task_time == "09:00"


def test_nl_parse_daily():
    p = TNP.parse("Carnival ကို နေ့စဉ် 09:00 စစ်မယ်")
    assert p.frequency == "DAILY"
    assert p.task_time == "09:00"


def test_nl_parse_specific_date():
    p = TNP.parse("A3 Test ကို 2026-09-15 မှာ")
    assert p.frequency == "ONE_TIME"
    assert p.specific_date == "2026-09-15"


def test_matches_daily():
    t = Task(frequency="DAILY", task_time="09:00")
    assert TS._matches(t, date(2026, 9, 14))


def test_matches_weekly_monday():
    t = Task(frequency="WEEKLY", weekday=0)  # Monday
    assert TS._matches(t, date(2026, 9, 14))  # 2026-09-14 is Monday
    assert not TS._matches(t, date(2026, 9, 15))  # Tuesday


def test_matches_one_time():
    t = Task(frequency="ONE_TIME", specific_date=date(2026, 9, 15))
    assert TS._matches(t, date(2026, 9, 15))
    assert not TS._matches(t, date(2026, 9, 14))


def test_local_today(app):
    with app.app_context():
        d = TS.local_today()
        assert d.year >= 2026
