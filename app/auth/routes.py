"""
Authentication routes.

Implements:
- login (with rate limiting / lockout via User model)
- logout
- generic authentication error messages
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


def _audit(action: str, **details) -> None:
    """Best-effort audit log. Silently ignore failures."""
    try:
        from app.models import AuditLog  # type: ignore

        db.session.add(
            AuditLog(
                actor_user_id=current_user.id if current_user.is_authenticated else None,
                action=action,
                details=str(details) if details else None,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        username = (form.username.data or "").strip()
        password = form.password.data or ""

        user = User.query.filter_by(username=username).first()

        # Generic error for both wrong user and wrong password
        generic_error = "Username သို့မဟုတ် Password မှားနေပါတယ်။"

        if user is None or user.is_deleted:
            _audit("login_failed", username=username, reason="unknown_user")
            flash(generic_error, "error")
            return render_template("auth/login.html", form=form), 401

        if not user.is_active:
            _audit("login_failed", username=username, reason="inactive")
            flash("ဒီအကောင့်ကို ပိတ်ထားပါတယ်။", "error")
            return render_template("auth/login.html", form=form), 403

        if user.is_locked():
            _audit("login_failed", username=username, reason="locked")
            flash("အကောင့် ခဏပိတ်ထားပါတယ်။ ခဏနေရင် ပြန်စမ်းပါ။", "error")
            return render_template("auth/login.html", form=form), 429

        if not user.check_password(password):
            user.register_failed_login()
            db.session.commit()
            _audit("login_failed", username=username, reason="bad_password")
            flash(generic_error, "error")
            return render_template("auth/login.html", form=form), 401

        # Success
        user.register_successful_login()
        db.session.commit()

        login_user(user, remember=bool(form.remember.data))
        _audit("login_success", username=username)

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("admin.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Log out current user."""
    _audit("logout", username=current_user.username)
    logout_user()
    flash("Logout ဖြစ်သွားပါပြီ။", "info")
    return redirect(url_for("auth.login"))
