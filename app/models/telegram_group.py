"""
Telegram Group configuration.

Each group can have:
  - allowed_thread_ids: which Topics bot replies in
  - is_enabled: on/off
  - require_mention: only reply if @bot mentioned
"""

from __future__ import annotations

import json

from app.extensions import db
from app.models.base import BaseModel


class TelegramGroupConfig(BaseModel):
    __tablename__ = "telegram_group_configs"
    __table_args__ = (
        db.Index("ix_tggroup_chat", "chat_id"),
    )

    chat_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)
    chat_type = db.Column(db.String(32), nullable=True)  # group | supergroup

    # JSON list of ints, e.g. "[5, 12]"
    allowed_thread_ids = db.Column(db.Text, nullable=True)

    is_enabled = db.Column(db.Boolean, default=True, nullable=False, index=True)
    reply_in_thread = db.Column(db.Boolean, default=True, nullable=False)
    require_mention = db.Column(db.Boolean, default=False, nullable=False)

    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    last_message_at = db.Column(db.DateTime(timezone=True), nullable=True)
    message_count = db.Column(db.Integer, nullable=False, default=0)

    # --- helpers ---
    def thread_list(self) -> list[int]:
        if not self.allowed_thread_ids:
            return []
        try:
            data = json.loads(self.allowed_thread_ids)
            return [int(x) for x in data]
        except Exception:
            return []

    def set_threads(self, threads: list[int]) -> None:
        threads = sorted({int(t) for t in threads if t is not None})
        self.allowed_thread_ids = json.dumps(threads) if threads else None

    def allows_thread(self, thread_id: int | None) -> bool:
        """
        True if bot should reply in the given thread.

        - If allowed_thread_ids is empty/None → allow ALL topics (backward compat)
        - Otherwise → must be in the list
        """
        threads = self.thread_list()
        if not threads:
            return True
        return thread_id in threads

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TGGroup {self.chat_id} {self.title!r}>"
