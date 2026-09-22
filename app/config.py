"""Centralized configuration for AI DIGITAL BRAIN."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_ROOT = BASE_DIR / os.getenv("UPLOAD_ROOT", "uploads")
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")

for _p in (INSTANCE_DIR, UPLOAD_ROOT, LOG_DIR):
    _p.mkdir(parents=True, exist_ok=True)

for _sub in ("documents", "excel", "pdf", "word", "photos"):
    (UPLOAD_ROOT / _sub).mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")

    # ★ Session — long-lived (30 days)
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False   # HTTP (Termux local)

    # ★ Remember cookie — 30 days
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    DEBUG = _bool("FLASK_DEBUG", True)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{INSTANCE_DIR / 'ai_brain.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ★ Supabase Session Pooler — Transaction Aborted Fix
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 5,
        'max_overflow': 10,
        'isolation_level': 'AUTOCOMMIT',
    }

    UPLOAD_ROOT = str(UPLOAD_ROOT)
    MAX_CONTENT_LENGTH = _int("MAX_CONTENT_LENGTH_MB", 32) * 1024 * 1024

    AI_ENABLED = _bool("AI_ENABLED", True)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip()
    AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
    AI_MODEL = os.getenv("AI_MODEL", "").strip()
    AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip()
    AI_TIMEOUT = _int("AI_TIMEOUT", 30)
    AI_MAX_RETRIES = _int("AI_MAX_RETRIES", 2)

    TELEGRAM_ENABLED = _bool("TELEGRAM_ENABLED", True)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_API_BASE = os.getenv("TELEGRAM_API_BASE", "http://127.0.0.1:5000").strip()

    # ★ Bot ↔ API security (Bot က API ကို ခေါ်တဲ့အခါ သုံး)
    BOT_API_KEY = os.getenv("BOT_API_KEY", "").strip()

    OCR_ENABLED = _bool("OCR_ENABLED", True)
    WEB_RESEARCH_ENABLED = _bool("WEB_RESEARCH_ENABLED", False)
    GOOGLE_DRIVE_ENABLED = _bool("GOOGLE_DRIVE_ENABLED", False)

    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Yangon")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_DIR = str(LOG_DIR)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config() -> type[Config]:
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig
