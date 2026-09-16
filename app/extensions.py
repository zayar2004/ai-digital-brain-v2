"""Flask extensions singleton module."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL + busy timeout for SQLite concurrency."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    finally:
        cursor.close()


from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"
login_manager.session_protection = "basic"


@login_manager.user_loader
def load_user(user_id: str):
    from app.models.user import User
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
