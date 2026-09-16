"""
Task model + TaskHistory.

Frequency:
    DAILY    — every day
    WEEKLY   — specific weekday (MONDAY..SUNDAY)
    MONTHLY  — specific day-of-month (1..31)
    YEARLY   — specific month + day
    ONE_TIME — specific date only
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import BaseModel


class TaskFrequency:
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    ONE_TIME = "ONE_TIME"
    ALL = (DAILY, WEEKLY, MONTHLY, YEARLY, ONE_TIME)


class TaskStatus:
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    ALL = (PENDING, IN_PROGRESS, COMPLETED, SKIPPED, CANCELLED)


class TaskPriority:
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    ALL = (LOW, NORMAL, HIGH, URGENT)


class Task(BaseModel):
    __tablename__ = "tasks"
    __table_args__ = (
        db.Index("ix_task_shop_status", "shop_id", "status"),
        db.Index("ix_task_due", "specific_date", "weekday"),
    )

    shop_id = db.Column(
        db.Integer, db.ForeignKey("shops.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    machine_id = db.Column(
        db.Integer, db.ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    title = db.Column(db.String(512), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    frequency = db.Column(db.String(16), nullable=False, default=TaskFrequency.DAILY, index=True)
    weekday = db.Column(db.Integer, nullable=True)      # 0=Monday .. 6=Sunday
    day_of_month = db.Column(db.Integer, nullable=True) # 1..31
    month = db.Column(db.Integer, nullable=True)        # 1..12
    specific_date = db.Column(db.Date, nullable=True, index=True)
    task_time = db.Column(db.String(8), nullable=True)  # "HH:MM"

    priority = db.Column(db.String(16), nullable=False, default=TaskPriority.NORMAL, index=True)
    status = db.Column(db.String(16), nullable=False, default=TaskStatus.PENDING, index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    shop = db.relationship("Shop", lazy="joined")
    machine = db.relationship("Machine", lazy="joined")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], lazy="joined")

    def describe_schedule(self) -> str:
        """Return a short Myanmar description of the schedule."""
        wd_names = ["တနင်္လာ", "အင်္ဂါ", "ဗုဒ္ဓဟူး", "ကြာသပတေး", "သောကြာ", "စနေ", "တနင်္ဂနွေ"]
        if self.frequency == TaskFrequency.DAILY:
            s = "နေ့စဉ်"
        elif self.frequency == TaskFrequency.WEEKLY:
            s = f"အပတ်စဉ် ({wd_names[self.weekday] if self.weekday is not None and 0 <= self.weekday < 7 else '?'})"
        elif self.frequency == TaskFrequency.MONTHLY:
            s = f"လစဉ် ({self.day_of_month or '?'} ရက်)"
        elif self.frequency == TaskFrequency.YEARLY:
            s = f"နှစ်စဉ် ({self.month or '?'}/{self.day_of_month or '?'})"
        elif self.frequency == TaskFrequency.ONE_TIME:
            s = f"တစ်ခါတည်း ({self.specific_date})"
        else:
            s = self.frequency
        if self.task_time:
            s += f" · {self.task_time}"
        return s

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task {self.title[:30]!r} {self.frequency}>"


class TaskHistory(BaseModel):
    __tablename__ = "task_history"
    __table_args__ = (
        db.Index("ix_taskhist_task", "task_id", "created_at"),
    )

    task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status = db.Column(db.String(16), nullable=False)
    note = db.Column(db.Text, nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # ★ Telegram message tracking
    message_id = db.Column(db.Integer, nullable=True)
    chat_id = db.Column(db.BigInteger, nullable=True)

    task = db.relationship("Task", lazy="joined")
    completed_by = db.relationship("User", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TaskHistory task={self.task_id} {self.status}>"
