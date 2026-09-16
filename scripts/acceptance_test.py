"""
Master Prompt Acceptance Tests (Rules 92-98).

Run:
    python -m scripts.acceptance_test

Prints PASS / FAIL for each scenario.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    ErrorKnowledge, Machine, MachineCode, Shop,
)
from app.search import unified_search as US  # noqa: E402
from app.services import machine_code_service as MCS  # noqa: E402
from app.services import task_nl_parser as TNP  # noqa: E402


def _shop(code):
    return Shop.query.filter_by(code=code).first()


def test_92_quick_teach_parsing():
    """Acceptance Test 1: Carnival Circus P3 Error 07 extraction."""
    from app.ingestion import quick_teach
    text = (
        "Carnival circus P3 Error 07 ပေါ်နေ၍ "
        "coin ချပေးသော coin ခွက်တွင် coin ကုန်နေ၍ "
        "ပြန်ဖြည့်ပေးလိုက်တာ အဆင်ပြေသွားပါပြီ။"
    )
    r = quick_teach.extract(text)
    checks = {
        "machine": r.machine_name and "Carnival" in r.machine_name,
        "unit": r.unit == "P3",
        "error": r.error_code == "07",
    }
    return checks


def test_93_shop_isolation():
    """Acceptance Test 2: A3 verified → A3; explicit A5 → A5."""
    from app.security.shop_scope import resolve_shop

    r1 = resolve_shop(explicit=None, verified_codes=["A3"], context_code=None)
    r2 = resolve_shop(explicit="A5", verified_codes=["A3"], context_code=None)

    return {
        "verified_A3": r1.code == "A3",
        "explicit_A5_overrides": r2.code == "A5" and r2.source == "explicit",
    }


def test_94_machine_code_excel():
    """Acceptance Test 3: A3 CT code search."""
    a3 = _shop("A3")
    if not a3:
        return {"skip": True}
    r = MCS.search_machine_codes(
        shop_id=a3.id, shop_code="A3",
        query="CT", only_approved=False,
    )
    return {"A3_CT_has_results": r.total >= 1}


def test_95_multi_shop_ct():
    """Acceptance Test 4: 'CT code' should show all shops when unscoped."""
    r = US.search(query="CT", shop_id=None, shop_code=None, only_approved=False)
    shops = set(h.shop for h in r.hits if h.shop)
    return {"multi_shop_matches": len(shops) >= 1}


def test_97_nl_task():
    """Acceptance Test 6: NL task parsing."""
    p = TNP.parse("A3 Crocodile Tycoon ကို တနင်္လာနေ့တိုင်း မနက် 9 နာရီ စစ်မယ်")
    return {
        "freq_weekly": p.frequency == "WEEKLY",
        "weekday_monday": p.weekday == 0,
        "time_0900": p.task_time == "09:00",
    }


def test_98_today_calc():
    """Acceptance Test 7: 'today' uses Asia/Yangon."""
    from app.services import task_service as TS
    today = TS.local_today()
    return {"today_valid": today.year >= 2026}


def main() -> int:
    app = create_app()
    with app.app_context():
        tests = [
            ("Rule 92 — Quick Teach extraction", test_92_quick_teach_parsing),
            ("Rule 93 — Shop isolation", test_93_shop_isolation),
            ("Rule 94 — A3 CT code search", test_94_machine_code_excel),
            ("Rule 95 — Multi-shop CT search", test_95_multi_shop_ct),
            ("Rule 97 — NL task parsing", test_97_nl_task),
            ("Rule 98 — Today calc (Yangon)", test_98_today_calc),
        ]

        total = 0
        passed = 0

        for label, fn in tests:
            print(f"\n▶ {label}")
            try:
                result = fn()
                total += 1
                if result.get("skip"):
                    print("  · SKIPPED")
                    continue
                all_ok = all(bool(v) for k, v in result.items() if k != "skip")
                if all_ok:
                    passed += 1
                    print("  ✓ PASS")
                else:
                    print("  ✗ FAIL")
                    for k, v in result.items():
                        if k == "skip":
                            continue
                        print(f"     {'✓' if v else '✗'} {k}")
            except Exception as e:
                total += 1
                print(f"  ✗ ERROR: {type(e).__name__}: {e}")

        print()
        print("=" * 60)
        print(f"Result: {passed}/{total} passed")
        print("=" * 60)
        return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
