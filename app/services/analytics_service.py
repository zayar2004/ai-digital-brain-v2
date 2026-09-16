"""Analytics service — aggregate queries for dashboard."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.models import EventLog, SearchLog


def log_search(
    *,
    query: str,
    source: str = "web",
    shop_id: int | None = None,
    user_id: int | None = None,
    telegram_user_id: int | None = None,
    result_count: int = 0,
    kinds: list[str] | None = None,
) -> None:
    """Best-effort log a search. Never raises."""
    try:
        q = (query or "").strip()[:500]
        if not q:
            return
        entry = SearchLog(
            search_text=q,
            source=source,
            shop_id=shop_id,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            result_count=result_count,
            kinds=",".join(kinds) if kinds else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def log_event(
    *,
    name: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    shop_id: int | None = None,
    user_id: int | None = None,
    details: str | None = None,
) -> None:
    """Best-effort log an event."""
    try:
        e = EventLog(
            name=name,
            entity_type=entity_type,
            entity_id=entity_id,
            shop_id=shop_id,
            user_id=user_id,
            details=details,
        )
        db.session.add(e)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


# ----------------------------------------------------------------
# Aggregates
# ----------------------------------------------------------------
def summary(days: int = 7) -> dict[str, Any]:
    """Return summary stats for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_searches = SearchLog.query.filter(SearchLog.created_at >= since).count()
    total_events = EventLog.query.filter(EventLog.created_at >= since).count()

    return {
        "period_days": days,
        "total_searches": total_searches,
        "total_events": total_events,
    }


def top_queries(*, days: int = 7, limit: int = 20) -> list[dict]:
    """Most searched queries."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            func.lower(SearchLog.search_text).label("q"),
            func.count(SearchLog.id).label("n"),
        )
        .filter(SearchLog.created_at >= since)
        .group_by(func.lower(SearchLog.search_text))
        .order_by(func.count(SearchLog.id).desc())
        .limit(limit)
        .all()
    )
    return [{"query": q, "count": n} for q, n in rows]


def top_shops(*, days: int = 7, limit: int = 10) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    from app.models import Shop
    rows = (
        db.session.query(
            Shop.code,
            func.count(SearchLog.id).label("n"),
        )
        .join(SearchLog, SearchLog.shop_id == Shop.id)
        .filter(SearchLog.created_at >= since)
        .group_by(Shop.code)
        .order_by(func.count(SearchLog.id).desc())
        .limit(limit)
        .all()
    )
    return [{"shop": c, "count": n} for c, n in rows]


def search_sources(*, days: int = 7) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            SearchLog.source,
            func.count(SearchLog.id).label("n"),
        )
        .filter(SearchLog.created_at >= since)
        .group_by(SearchLog.source)
        .order_by(func.count(SearchLog.id).desc())
        .all()
    )
    return [{"source": s, "count": n} for s, n in rows]


def daily_counts(*, days: int = 14) -> list[dict]:
    """Searches per day (last N days)."""
    result: list[dict] = []
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        next_d = d + timedelta(days=1)
        start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        end = datetime(next_d.year, next_d.month, next_d.day, tzinfo=timezone.utc)
        n = SearchLog.query.filter(
            SearchLog.created_at >= start,
            SearchLog.created_at < end,
        ).count()
        result.append({"date": d.isoformat(), "count": n})
    return result


def top_events(*, days: int = 7, limit: int = 20) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            EventLog.name,
            func.count(EventLog.id).label("n"),
        )
        .filter(EventLog.created_at >= since)
        .group_by(EventLog.name)
        .order_by(func.count(EventLog.id).desc())
        .limit(limit)
        .all()
    )
    return [{"event": n, "count": c} for n, c in rows]


def top_telegram_users(*, days: int = 7, limit: int = 10) -> list[dict]:
    from app.models import TelegramUser
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            TelegramUser.first_name,
            TelegramUser.telegram_username,
            func.count(SearchLog.id).label("n"),
        )
        .join(SearchLog, SearchLog.telegram_user_id == TelegramUser.telegram_user_id)
        .filter(SearchLog.created_at >= since)
        .group_by(TelegramUser.first_name, TelegramUser.telegram_username)
        .order_by(func.count(SearchLog.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": n or "@" + (u or "?"), "count": c} for n, u, c in rows]
