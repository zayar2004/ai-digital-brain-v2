"""
Task service.

Timezone-aware calculation of "today's tasks" etc.
Default timezone: Asia/Yangon.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _HAVE_ZONEINFO = True
except Exception:
    ZoneInfo = None  # type: ignore
    _HAVE_ZONEINFO = False

from flask_login import current_user

from app.config import Config
from app.extensions import db
from app.models import Task, TaskHistory, TaskStatus

WEEKDAY_NAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


# ----------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------
def local_now() -> datetime:
    """Return the current time in the configured timezone."""
    if _HAVE_ZONEINFO:
        try:
            tz = ZoneInfo(Config.DEFAULT_TIMEZONE)
            return datetime.now(tz)
        except Exception:
            pass
    return datetime.now(tz=timezone.utc)


def local_today() -> date:
    return local_now().date()


def _current_user_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


# ----------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------
def create_task(
    *,
    shop_id: int,
    title: str,
    description: str | None = None,
    machine_id: int | None = None,
    frequency: str = "DAILY",
    weekday: int | None = None,
    day_of_month: int | None = None,
    month: int | None = None,
    specific_date: date | None = None,
    task_time: str | None = None,
    priority: str = "NORMAL",
    assigned_to_id: int | None = None,
) -> Task:
    title = (title or "").strip()
    if not title:
        raise ValueError("Task title is required.")
    if not shop_id:
        raise ValueError("shop_id is required.")

    t = Task(
        shop_id=shop_id,
        machine_id=machine_id,
        assigned_to_id=assigned_to_id,
        title=title,
        description=(description or "").strip() or None,
        frequency=frequency,
        weekday=weekday,
        day_of_month=day_of_month,
        month=month,
        specific_date=specific_date,
        task_time=(task_time or "").strip() or None,
        priority=priority,
        status="PENDING",
        created_by_id=_current_user_id(),
    )
    db.session.add(t)
    db.session.flush()
    _record_history(t, status="PENDING", note="created")
    db.session.commit()
    return t


def update_status(task_id: int, status: str, note: str = "") -> Task:
    if status not in ("PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED", "CANCELLED"):
        raise ValueError(f"Invalid status: {status}")
    t = db.session.get(Task, task_id)
    if not t:
        raise ValueError("Task not found.")
    t.status = status
    _record_history(t, status=status, note=note or None)
    db.session.commit()
    return t


def archive_task(task_id: int) -> Task:
    t = db.session.get(Task, task_id)
    if not t:
        raise ValueError("Task not found.")
    t.soft_delete()
    _record_history(t, status="ARCHIVED", note="archived")
    db.session.commit()
    return t


def _record_history(t: Task, *, status: str, note: str | None = None) -> None:
    db.session.add(TaskHistory(
        task_id=t.id,
        status=status,
        note=note,
        completed_by_id=_current_user_id(),
    ))


# ----------------------------------------------------------------
# Scheduling logic
# ----------------------------------------------------------------
def _matches(task: Task, on: date) -> bool:
    f = task.frequency
    if f == "DAILY":
        return True
    if f == "WEEKLY":
        return task.weekday is not None and task.weekday == on.weekday()
    if f == "MONTHLY":
        return task.day_of_month is not None and task.day_of_month == on.day
    if f == "YEARLY":
        return (
            task.month is not None and task.day_of_month is not None
            and task.month == on.month and task.day_of_month == on.day
        )
    if f == "ONE_TIME":
        return task.specific_date is not None and task.specific_date == on
    return False


def tasks_for_date(
    *,
    on: date | None = None,
    shop_id: int | None = None,
    include_archived: bool = False,
) -> list[Task]:
    on = on or local_today()
    q = Task.query.filter(Task.is_deleted.is_(False))
    if not include_archived:
        q = q.filter(Task.status.notin_(("CANCELLED",)))
    if shop_id:
        q = q.filter(Task.shop_id == shop_id)
    all_tasks = q.all()
    matched = [t for t in all_tasks if _matches(t, on)]
    # sort by time (HH:MM) then priority
    matched.sort(key=lambda t: (t.task_time or "99:99", t.id))
    return matched


def upcoming_tasks(
    *,
    days: int = 14,
    shop_id: int | None = None,
    limit: int = 200,
) -> list[tuple[date, Task]]:
    today = local_today()
    out: list[tuple[date, Task]] = []
    q = Task.query.filter(Task.is_deleted.is_(False))
    if shop_id:
        q = q.filter(Task.shop_id == shop_id)
    all_tasks = q.all()

    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        for t in all_tasks:
            if _matches(t, d):
                out.append((d, t))
                if len(out) >= limit:
                    return out
    return out


def overdue_tasks(*, shop_id: int | None = None) -> list[Task]:
    """Completed status missing for a task whose scheduled date has passed."""
    today = local_today()
    q = Task.query.filter(Task.is_deleted.is_(False))
    if shop_id:
        q = q.filter(Task.shop_id == shop_id)
    candidates = q.filter(Task.status.in_(("PENDING", "IN_PROGRESS"))).all()

    overdue: list[Task] = []
    for t in candidates:
        # Check if this task was scheduled on a past date without completion
        if t.frequency == "ONE_TIME" and t.specific_date and t.specific_date < today:
            overdue.append(t)
    return overdue
