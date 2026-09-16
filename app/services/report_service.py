"""
Report service.

- Create/list work reports
- Compare two reports (metric deltas)
- Never overwrites previous reports (unique per shop+date)
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from flask_login import current_user

from app.extensions import db
from app.models import ReportStatus, WorkReport


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def create_report(
    *,
    shop_id: int,
    report_date: date,
    title: str | None = None,
    metrics: dict[str, Any] | None = None,
    notes: str | None = None,
    original_content: str | None = None,
    myanmar_content: str | None = None,
    status: str = ReportStatus.PENDING,
    source_type: str | None = "manual",
    source_file: str | None = None,
) -> WorkReport:
    if not shop_id:
        raise ValueError("shop_id is required.")
    if not report_date:
        raise ValueError("report_date is required.")

    existing = WorkReport.query.filter_by(
        shop_id=shop_id, report_date=report_date
    ).first()
    if existing:
        raise ValueError(
            f"Report for {report_date} already exists in this shop. "
            f"Edit or delete the existing one first."
        )

    r = WorkReport(
        shop_id=shop_id,
        report_date=report_date,
        title=(title or "").strip() or None,
        metrics_json=json.dumps(metrics, ensure_ascii=False) if metrics else None,
        notes=(notes or "").strip() or None,
        original_content=original_content,
        myanmar_content=myanmar_content,
        status=status,
        source_type=source_type,
        source_file=source_file,
        created_by_id=_current_user_id(),
    )
    db.session.add(r)
    db.session.commit()
    return r


def update_report(report_id: int, **fields) -> WorkReport:
    r = db.session.get(WorkReport, report_id)
    if not r:
        raise ValueError("Report not found.")

    if "metrics" in fields and fields["metrics"] is not None:
        r.metrics_json = json.dumps(fields["metrics"], ensure_ascii=False)

    for k in ("title", "notes", "original_content", "myanmar_content", "status"):
        if k in fields and fields[k] is not None:
            setattr(r, k, fields[k])

    db.session.commit()
    return r


def approve_report(report_id: int) -> WorkReport:
    from app.models.base import utcnow
    r = db.session.get(WorkReport, report_id)
    if not r:
        raise ValueError("Report not found.")
    r.status = ReportStatus.APPROVED
    r.approved_by_id = _current_user_id()
    db.session.commit()
    return r


def list_reports(
    *,
    shop_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    limit: int = 200,
):
    query = WorkReport.query.filter(WorkReport.is_deleted.is_(False))
    if shop_id:
        query = query.filter(WorkReport.shop_id == shop_id)
    if status:
        query = query.filter(WorkReport.status == status)
    if date_from:
        query = query.filter(WorkReport.report_date >= date_from)
    if date_to:
        query = query.filter(WorkReport.report_date <= date_to)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(db.or_(
            db.func.lower(db.func.coalesce(WorkReport.title, "")).like(like),
            db.func.lower(db.func.coalesce(WorkReport.notes, "")).like(like),
        ))
    return query.order_by(WorkReport.report_date.desc()).limit(limit).all()


def get_report(report_id: int) -> WorkReport | None:
    if not report_id:
        return None
    return db.session.get(WorkReport, report_id)


def get_latest(shop_id: int) -> WorkReport | None:
    return (
        WorkReport.query.filter_by(shop_id=shop_id, is_deleted=False)
        .order_by(WorkReport.report_date.desc())
        .first()
    )


def metrics_of(report: WorkReport) -> dict[str, Any]:
    if not report or not report.metrics_json:
        return {}
    try:
        return json.loads(report.metrics_json)
    except Exception:
        return {}


def compare_reports(a: WorkReport, b: WorkReport) -> dict:
    """Return per-key deltas between two reports (b - a)."""
    ma = metrics_of(a)
    mb = metrics_of(b)
    keys = sorted(set(ma.keys()) | set(mb.keys()))
    rows = []
    for k in keys:
        va = ma.get(k)
        vb = mb.get(k)
        delta = None
        try:
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                delta = vb - va
        except Exception:
            pass
        rows.append({
            "key": k,
            "a": va,
            "b": vb,
            "delta": delta,
        })
    return {
        "a": {"id": a.id, "date": a.report_date.isoformat()},
        "b": {"id": b.id, "date": b.report_date.isoformat()},
        "rows": rows,
    }
