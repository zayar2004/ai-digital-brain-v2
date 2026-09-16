"""Model registry."""

from app.models.analytics import EventLog, SearchLog  # noqa: F401
from app.models.broadcast import (  # noqa: F401
    Broadcast, BroadcastPhoto, BroadcastRecipient,
    BroadcastStatus, RecipientStatus,
)
from app.models.audit import AuditLog  # noqa: F401
from app.models.base import BaseModel, utcnow  # noqa: F401
from app.models.error import (  # noqa: F401
    ErrorCase, ErrorKnowledge, ErrorKnowledgeStatus,
)
from app.models.knowledge_photo import (  # noqa: F401
    KnowledgePhoto, MAX_PHOTOS_PER_KNOWLEDGE,
)
from app.models.knowledge import (  # noqa: F401
    Knowledge, KnowledgeConflict, KnowledgeConflictStatus,
    KnowledgeStatus, KnowledgeVersion,
)
from app.models.machine import Machine, MachineAlias  # noqa: F401
from app.models.machine_code import MachineCode, MachineCodeSource  # noqa: F401
from app.models.media import MediaCategory, MediaFile  # noqa: F401
from app.models.report import ReportStatus, WorkReport  # noqa: F401
from app.models.telegram_group import TelegramGroupConfig  # noqa: F401
from app.models.setting import AppSetting  # noqa: F401
from app.models.shop import Shop, TelegramUser, TelegramUserShop  # noqa: F401
from app.models.task import (  # noqa: F401
    Task, TaskFrequency, TaskHistory, TaskPriority, TaskStatus,
)
from app.models.user import Role, User  # noqa: F401

__all__ = [
    "BaseModel", "utcnow",
    "Broadcast", "BroadcastPhoto", "BroadcastRecipient",
    "TelegramGroupConfig",
    "BroadcastStatus", "RecipientStatus",
    "SearchLog", "EventLog",
    "AuditLog",
    "Shop", "TelegramUser", "TelegramUserShop",
    "User", "Role",
    "Machine", "MachineAlias",
    "MachineCode", "MachineCodeSource",
    "Knowledge", "KnowledgePhoto", "MAX_PHOTOS_PER_KNOWLEDGE",
    "KnowledgeVersion", "KnowledgeConflict",
    "KnowledgeConflictStatus", "KnowledgeStatus",
    "ErrorKnowledge", "ErrorCase", "ErrorKnowledgeStatus",
    "MediaFile", "MediaCategory",
    "Task", "TaskHistory",
    "WorkReport", "ReportStatus",
    "AppSetting",
    "TaskFrequency", "TaskStatus", "TaskPriority",
]
