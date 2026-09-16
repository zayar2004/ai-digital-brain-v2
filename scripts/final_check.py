"""
Final system verification.

Runs all critical checks against a running system.

Usage:
    python -m scripts.final_check
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Results tracking
PASS = []
FAIL = []
WARN = []


def check(name: str, condition: bool, detail: str = "", warn_only: bool = False):
    if condition:
        PASS.append((name, detail))
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
    elif warn_only:
        WARN.append((name, detail))
        print(f"  · {name} (warning)" + (f" — {detail}" if detail else ""))
    else:
        FAIL.append((name, detail))
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print("=" * 70)
    print(" AI DIGITAL BRAIN — FINAL VERIFICATION")
    print("=" * 70)
    print()

    # ---------- 1. Imports ----------
    print("▶ 1. Core Imports")
    try:
        from app import create_app
        from app.config import Config
        from app.extensions import db
        check("Flask app factory", True)
    except Exception as e:
        check("Flask app factory", False, str(e))
        return 1

    try:
        from app.models import (
            Shop, User, Machine, MachineCode, MachineCodeSource,
            Knowledge, KnowledgeVersion, KnowledgeConflict,
            ErrorKnowledge, ErrorCase, Task, TaskHistory,
            WorkReport, MediaFile, TelegramUser, TelegramUserShop,
            AuditLog, AppSetting,
        )
        check("All models importable", True)
    except Exception as e:
        check("All models importable", False, str(e))

    try:
        from app.services import (
            knowledge_service, machine_service, machine_code_service,
            error_service, task_service, report_service,
            settings_service, backup_service, audit_service,
            media_service, file_service, telegram_notify_service,
        )
        check("All services importable", True)
    except Exception as e:
        check("All services importable", False, str(e))

    try:
        from app.ingestion import (
            excel_reader, error_excel_ingestor, document_ingestor,
            quick_teach, pdf_reader, docx_reader, ocr_reader,
            image_ingestor, report_ingestor,
        )
        check("All ingestion modules", True)
    except Exception as e:
        check("All ingestion modules", False, str(e))

    try:
        from app.ai import provider, prompts, service as ai_service, rag, grounding
        check("All AI modules", True)
    except Exception as e:
        check("All AI modules", False, str(e))

    try:
        from app.search import unified_search
        check("Unified search", True)
    except Exception as e:
        check("Unified search", False, str(e))

    try:
        from app.telegram import handlers, client, bot as tg_bot
        check("Telegram modules", True)
    except Exception as e:
        check("Telegram modules", False, str(e))

    try:
        from app.security import permissions, shop_scope, validators
        check("Security modules", True)
    except Exception as e:
        check("Security modules", False, str(e))

    # ---------- 2. App + DB ----------
    print()
    print("▶ 2. App + Database")
    app = create_app()
    with app.app_context():
        from sqlalchemy import text, inspect
        try:
            db.session.execute(text("SELECT 1"))
            check("DB connection", True)
        except Exception as e:
            check("DB connection", False, str(e))

        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        required = {
            "users", "shops", "machines", "machine_aliases",
            "machine_codes", "machine_code_sources",
            "knowledge", "knowledge_versions", "knowledge_conflicts",
            "error_knowledge", "error_cases",
            "tasks", "task_history", "work_reports",
            "media_files", "telegram_users", "telegram_user_shops",
            "audit_logs", "app_settings",
        }
        missing = required - tables
        check("All required tables", not missing,
              f"missing: {missing}" if missing else f"{len(tables)} tables")

        # Shops
        shops = [s.code for s in Shop.query.all()]
        expected = {f"A{i}" for i in range(1, 14)}
        check("Shops A1-A13 seeded", expected.issubset(set(shops)),
              f"got {len(shops)}")

        # Admin user
        admin = User.query.filter_by(role="SUPER_ADMIN").first()
        check("SUPER_ADMIN exists", admin is not None,
              admin.username if admin else "none")

        # Route count
        routes = list(app.url_map.iter_rules())
        check("Routes registered", len(routes) >= 40, f"{len(routes)} routes")

        # Critical routes
        critical = [
            "/", "/login", "/shops", "/machines", "/machine-codes",
            "/knowledge", "/errors", "/error-cases", "/tasks",
            "/reports", "/files", "/ingest", "/search",
            "/telegram-users", "/users", "/settings", "/health", "/backups",
        ]
        existing = {r.rule for r in routes}
        missing_routes = [c for c in critical if c not in existing]
        check("Critical routes", not missing_routes,
              f"missing: {missing_routes}" if missing_routes else f"{len(critical)} checked")

        # API endpoints
        api_routes = [r.rule for r in routes if r.rule.startswith("/api/")]
        check("API endpoints", len(api_routes) >= 6, f"{len(api_routes)} endpoints")

    # ---------- 3. Security ----------
    print()
    print("▶ 3. Security")
    from app.security import permissions as P
    check("Permission: SUPER_ADMIN settings",
          P.has_permission("SUPER_ADMIN", P.SETTINGS_EDIT))
    check("Permission: VIEWER cannot approve",
          not P.has_permission("VIEWER", P.KNOWLEDGE_APPROVE))
    check("Permission: EDITOR can edit",
          P.has_permission("EDITOR", P.KNOWLEDGE_EDIT))

    from app.security.shop_scope import normalize_shop_code, resolve_shop
    check("Shop code normalization", normalize_shop_code("a3") == "A3")
    check("Explicit overrides verified",
          resolve_shop(explicit="A5", verified_codes=["A3"], context_code=None).code == "A5")
    check("No guess on ambiguous",
          resolve_shop(explicit=None, verified_codes=["A1","A3"], context_code=None).code is None)

    from app.security.validators import is_allowed_file, safe_filename, is_within
    check("File type validation", is_allowed_file("x.xlsx") and not is_allowed_file("x.exe"))
    check("Path traversal blocked",
          is_within(Path("/tmp"), Path("/tmp/a.txt")) and not is_within(Path("/tmp"), Path("/etc/passwd")))
    check("Safe filename", "passwd" in safe_filename("../../etc/passwd.xlsx"))

    # ---------- 4. AI / Grounding ----------
    print()
    print("▶ 4. AI / Grounding")
    from app.ai import grounding
    good = grounding.check("Error 07", "Error 07 = coin empty")
    check("Grounding: good answer", good.ok)
    bad = grounding.check("Error 99 and CT-P9-999", "Error 07")
    check("Grounding: detects bad", not bad.ok)

    # ---------- 5. Ingestion ----------
    print()
    print("▶ 5. Ingestion")
    from app.ingestion.error_excel_ingestor import _derive_error_code
    check("Error code derivation (MSDAB-1)",
          _derive_error_code("Marble Shooting Device Abnormal (Ball Jam)", "1") == "MSDAB-1")
    check("Error code derivation (PAM-3)",
          _derive_error_code("Pusher Abnormality (Motor)", "3") == "PAM-3")

    from app.ingestion import quick_teach
    r = quick_teach.extract("Carnival circus P3 Error 07 coin empty")
    check("Quick Teach unit", r.unit == "P3")
    check("Quick Teach error", r.error_code == "07")

    # ---------- 6. Tasks ----------
    print()
    print("▶ 6. Tasks")
    from app.services import task_nl_parser as TNP
    p = TNP.parse("A3 Crocodile ကို တနင်္လာနေ့တိုင်း မနက် 9 နာရီ စစ်မယ်")
    check("NL task: weekly", p.frequency == "WEEKLY")
    check("NL task: monday", p.weekday == 0)
    check("NL task: time", p.task_time == "09:00")

    # ---------- 7. Search ----------
    print()
    print("▶ 7. Search")
    with app.app_context():
        from app.search import unified_search as US
        r = US.search(query="", shop_id=None, shop_code=None)
        check("Search handles empty query", r.total == 0)

    # ---------- 8. Telegram ----------
    print()
    print("▶ 8. Telegram (code-level)")
    from app.telegram import handlers
    check("handle_command exists", hasattr(handlers, "handle_command"))
    check("handle_text exists", hasattr(handlers, "handle_text"))
    check("handle_callback exists", hasattr(handlers, "handle_callback"))
    check("send_message exists", hasattr(handlers, "send_message"))
    check("get_updates exists", hasattr(handlers, "get_updates"))

    import inspect
    gu_src = inspect.getsource(handlers.get_updates)
    check("get_updates allows callback_query", "callback_query" in gu_src)

    # ---------- Summary ----------
    print()
    print("=" * 70)
    print(f" PASS: {len(PASS)}")
    print(f" WARN: {len(WARN)}")
    print(f" FAIL: {len(FAIL)}")
    print("=" * 70)

    if FAIL:
        print()
        print("❌ FAILURES:")
        for name, detail in FAIL:
            print(f"   ✗ {name}" + (f" — {detail}" if detail else ""))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
