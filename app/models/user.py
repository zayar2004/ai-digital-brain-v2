"""
User model for Admin Website authentication.

Roles:
    SUPER_ADMIN - full system access
    ADMIN       - manage operational data + approve knowledge
    EDITOR      - create/edit knowledge and operational info
    VIEWER      - read-only
"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import BaseModel, utcnow


class Role:
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

    ALL = (SUPER_ADMIN, ADMIN, EDITOR, VIEWER)


class User(BaseModel, UserMixin):
    """Admin/Staff user account."""

    __tablename__ = "users"

    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default=Role.VIEWER, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # ----------------------------------------------------------------
    # Password handling
    # ----------------------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        """Hash and store the given plaintext password."""
        self.password_hash = generate_password_hash(raw_password, method="pbkdf2:sha256")

    def check_password(self, raw_password: str) -> bool:
        """Return True if the given plaintext matches the stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)

    # ----------------------------------------------------------------
    # Flask-Login required property
    # ----------------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:  # type: ignore[override]
        return True

    @property
    def is_anonymous(self) -> bool:  # type: ignore[override]
        return False

    def get_id(self) -> str:  # type: ignore[override]
        return str(self.id)

    # ----------------------------------------------------------------
    # Role helpers
    # ----------------------------------------------------------------
    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN)

    @property
    def is_editor(self) -> bool:
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN, Role.EDITOR)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    # ----------------------------------------------------------------
    # Lockout helpers
    # ----------------------------------------------------------------
    def register_failed_login(self, max_attempts: int = 5, lock_minutes: int = 15) -> None:
        """Increment failed login count and lock the account if needed."""
        self.failed_login_count = (self.failed_login_count or 0) + 1
        if self.failed_login_count >= max_attempts:
            from datetime import timedelta

            self.locked_until = utcnow() + timedelta(minutes=lock_minutes)

    def register_successful_login(self) -> None:
        """Reset counters on successful login."""
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login_at = utcnow()

    def is_locked(self) -> bool:
        """Return True if the account is currently locked."""
        if self.locked_until is None:
            return False
        return self.locked_until > utcnow()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role})>"
