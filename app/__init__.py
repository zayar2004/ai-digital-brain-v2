"""
AI DIGITAL BRAIN - Flask application factory.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

from app.config import get_config
from app.utils.help_texts import HELP

# ★ Fix: Override SQLAlchemy psycopg2 hstore query (Supabase Session Pooler issue)
def _fix_psycopg2_hstore():
    """Disable psycopg2 hstore auto-query that fails on Supabase Session Pooler."""
    try:
        from sqlalchemy.dialects.postgresql import psycopg2 as pg_psycopg2
        # Override _hstore_oids to return empty list (skip query)
        def _no_hstore(self, dbapi_conn):
            return None
        pg_psycopg2.PGDialect_psycopg2._hstore_oids = _no_hstore
    except Exception:
        pass

_fix_psycopg2_hstore()

from app.extensions import csrf, db, login_manager


def _configure_logging(app: Flask) -> None:
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")

    fh = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    fh.setFormatter(formatter); fh.setLevel(level)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter); sh.setLevel(level)

    app.logger.handlers.clear()
    app.logger.addHandler(fh); app.logger.addHandler(sh)
    app.logger.setLevel(level)


def _register_blueprints(app: Flask) -> None:
    try:
        from app.auth.routes import auth_bp
        app.register_blueprint(auth_bp)
    except Exception as exc:
        app.logger.warning("auth blueprint not loaded: %s", exc)

    try:
        from app.routes.admin import admin_bp
        app.register_blueprint(admin_bp)
    except Exception as exc:
        app.logger.warning("admin blueprint not loaded: %s", exc)

    try:
        from app.routes.api import api_bp
        app.register_blueprint(api_bp, url_prefix="/api")
    except Exception as exc:
        app.logger.warning("api blueprint not loaded: %s", exc)


def _register_error_handlers(app: Flask) -> None:
    def _wants_json() -> bool:
        return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"

    def _handle(status: int, code: str, message: str):
        if _wants_json():
            return jsonify({"success": False, "error": {"code": code, "message": message}}), status
        from flask import render_template
        return render_template("error.html", status=status, message=message), status

    @app.errorhandler(400)
    def _400(e): return _handle(400, "bad_request", "တောင်းဆိုမှု မမှန်ကန်ပါ။")
    @app.errorhandler(401)
    def _401(e): return _handle(401, "unauthorized", "ခွင့်ပြုချက် မရှိပါ။")
    @app.errorhandler(403)
    def _403(e): return _handle(403, "forbidden", "ဒီအပိုင်းကို ဝင်ခွင့်မရှိပါ။")
    @app.errorhandler(404)
    def _404(e): return _handle(404, "not_found", "ရှာမတွေ့ပါ။")
    @app.errorhandler(409)
    def _409(e): return _handle(409, "conflict", "အချက်အလက် ထပ်နေပါတယ်။")
    @app.errorhandler(413)
    def _413(e): return _handle(413, "payload_too_large", "ဖိုင် အရွယ်အစား ကြီးလွန်းပါတယ်။")
    @app.errorhandler(429)
    def _429(e): return _handle(429, "rate_limited", "တောင်းဆိုမှု များလွန်းပါတယ်။ ခဏနေရင် ပြန်စမ်းပါ။")
    @app.errorhandler(500)
    def _500(e):
        app.logger.exception("Internal server error")
        return _handle(500, "internal_error", "စနစ်အတွင်း ပြဿနာ ဖြစ်နေပါတယ်။")
    @app.errorhandler(Exception)
    def _unhandled(e):
        app.logger.exception("Unhandled exception: %s", e)
        return _handle(500, "internal_error", "စနစ်အတွင်း ပြဿနာ ဖြစ်နေပါတယ်။")


def create_app(config_override: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(get_config())
    if config_override:
        app.config.update(config_override)

    _configure_logging(app)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Exempt the API blueprint from CSRF protection.
    # API endpoints rely on their own auth (session or token).
    try:
        from app.routes.api import api_bp
        csrf.exempt(api_bp)
    except Exception as exc:  # pragma: no cover
        app.logger.warning("csrf.exempt(api_bp) skipped: %s", exc)

    # ★ CSRF active — admin protected (TEMP exempt removed)


    _register_blueprints(app)
    _register_error_handlers(app)

    # ★ Static files — no cache in dev, so edits show immediately
    @app.after_request
    def static_cache_buster(response):
        try:
            if request.path.startswith("/static/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        except Exception:
            pass
        return response

    @app.route("/robots.txt")
    def robots_txt():
        from flask import send_from_directory
        import os
        static_dir = os.path.join(app.root_path, "..", "static")
        return send_from_directory(static_dir, "robots.txt", mimetype="text/plain")

    @app.route("/health")
    def health():
        from sqlalchemy import text
        db_status = "ok"
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"
        return jsonify({
            "status": "ok",
            "database": db_status,
            "ai": "configured" if app.config["AI_API_KEY"] else "unconfigured",
            "telegram": "configured" if app.config["TELEGRAM_BOT_TOKEN"] else "unconfigured",
        })

    # Inject help texts into every template context
    @app.context_processor
    def _inject_help():
        return {"_help_data": HELP}

    # Best-effort: seed shops A1-A13 on first request context use
    with app.app_context():
        try:
            from app.services.shop_service import ensure_shops_seeded
            ensure_shops_seeded()
        except Exception as exc:  # pragma: no cover
            app.logger.warning("shop seeding skipped: %s", exc)

    # ★ Start task scheduler (once, skip in reloader parent)
    # ★ Start task scheduler (once per process — no reload duplicates)
    # ★ Start task scheduler (skip reloader parent)
    import os as _os
    _is_reloader_parent = (
        app.debug
        and _os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    )
    if not app.config.get("TESTING") and not _is_reloader_parent:
        try:
            from app.services.task_scheduler import start_scheduler
            start_scheduler(app)
            app.logger.info("✓ Task scheduler started")
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Scheduler start failed: %s", exc)

    # ★ Bot Thread — Start if running on Render (or explicitly enabled)
    # This runs the Telegram bot in a background thread so we don't need
    # a separate Background Worker (which requires a paid Render plan).
    _should_start_bot = (
        _os.environ.get("RENDER")               # Render sets this automatically
        or _os.environ.get("START_BOT_THREAD")  # manual override
    )
    if _should_start_bot and not app.config.get("TESTING"):
        try:
            from app.telegram.bot import run_polling
            import threading

            def _bot_worker():
                with app.app_context():
                    try:
                        app.logger.info("★ Bot thread starting (run_polling)...")
                        run_polling()
                    except Exception as _be:
                        app.logger.exception("Bot thread crashed: %s", _be)

            _bot_thread = threading.Thread(
                target=_bot_worker,
                daemon=True,
                name="telegram-bot",
            )
            _bot_thread.start()
            app.logger.info("★ Bot thread started (daemon)")
        except Exception as exc:
            app.logger.warning("Bot thread start failed: %s", exc)

    return app
