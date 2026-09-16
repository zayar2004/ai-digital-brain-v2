"""Pytest fixtures for AI Digital Brain.

CRITICAL: Tests use an isolated temp DB, NOT the real one.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Store original DATABASE_URL so we can restore if needed
_ORIGINAL_DB_URL = os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def app():
    from app import create_app
    from app.extensions import db
    from app.models import Role, Shop, User

    # Create a temporary SQLite file (auto-cleanup)
    tmpdir = tempfile.mkdtemp(prefix="adb_test_")
    test_db_path = Path(tmpdir) / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    # Also disable network integrations
    os.environ["AI_ENABLED"] = "false"
    os.environ["TELEGRAM_ENABLED"] = "false"
    os.environ["SECRET_KEY"] = "test-secret-key-only"

    # ★ Reload Config class so it picks up the new env
    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)

    # Now create the app — it will read the new DATABASE_URL
    from app import create_app
    app = create_app()

    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()

        # Seed A1-A13
        for i in range(1, 14):
            db.session.add(Shop(code=f"A{i}", name=f"A{i}", is_active=True))

        admin = User(username="testadmin", role=Role.SUPER_ADMIN, is_active=True)
        admin.set_password("TestPass123!")
        db.session.add(admin)

        editor = User(username="testeditor", role=Role.EDITOR, is_active=True)
        editor.set_password("TestPass123!")
        db.session.add(editor)

        viewer = User(username="testviewer", role=Role.VIEWER, is_active=True)
        viewer.set_password("TestPass123!")
        db.session.add(viewer)

        db.session.commit()

    yield app

    # Teardown: remove test DB
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

    try:
        if test_db_path.exists():
            test_db_path.unlink()
        os.rmdir(tmpdir)
    except Exception:
        pass

    # Restore original env (if any)
    if _ORIGINAL_DB_URL:
        os.environ["DATABASE_URL"] = _ORIGINAL_DB_URL
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    c = app.test_client()
    with app.app_context():
        c.post("/login", data={
            "username": "testadmin",
            "password": "TestPass123!",
        }, follow_redirects=True)
    return c


@pytest.fixture()
def db_session(app):
    from app.extensions import db
    with app.app_context():
        yield db.session
