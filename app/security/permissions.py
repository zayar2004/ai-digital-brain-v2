"""
Centralized permission matrix.

Every backend route must check permissions via this module.
Never rely only on hiding frontend buttons.
"""

from __future__ import annotations

from app.models.user import Role

# ----------------------------------------------------------------
# Permission constants
# ----------------------------------------------------------------
DASHBOARD_VIEW = "dashboard.view"

KNOWLEDGE_VIEW = "knowledge.view"
KNOWLEDGE_CREATE = "knowledge.create"
KNOWLEDGE_EDIT = "knowledge.edit"
KNOWLEDGE_DELETE = "knowledge.delete"
KNOWLEDGE_APPROVE = "knowledge.approve"

MACHINE_VIEW = "machine.view"
MACHINE_CREATE = "machine.create"
MACHINE_EDIT = "machine.edit"
MACHINE_DELETE = "machine.delete"

MACHINE_CODE_VIEW = "machine_code.view"
MACHINE_CODE_IMPORT = "machine_code.import"
MACHINE_CODE_EDIT = "machine_code.edit"

ERROR_VIEW = "error.view"
ERROR_CREATE = "error.create"
ERROR_EDIT = "error.edit"
ERROR_APPROVE = "error.approve"

TASK_VIEW = "task.view"
TASK_CREATE = "task.create"
TASK_EDIT = "task.edit"
TASK_COMPLETE = "task.complete"

REPORT_VIEW = "report.view"
REPORT_CREATE = "report.create"
REPORT_EDIT = "report.edit"

FILE_VIEW = "file.view"
FILE_UPLOAD = "file.upload"
FILE_DELETE = "file.delete"

SHOP_VIEW = "shop.view"
SHOP_MANAGE = "shop.manage"

USER_VIEW = "user.view"
USER_CREATE = "user.create"
USER_EDIT = "user.edit"
USER_DISABLE = "user.disable"

AUDIT_VIEW = "audit.view"

SETTINGS_VIEW = "settings.view"
SETTINGS_EDIT = "settings.edit"


# ----------------------------------------------------------------
# Role → permissions matrix
# ----------------------------------------------------------------
_VIEWER_PERMS = frozenset({
    DASHBOARD_VIEW,
    KNOWLEDGE_VIEW,
    MACHINE_VIEW,
    MACHINE_CODE_VIEW,
    ERROR_VIEW,
    TASK_VIEW,
    REPORT_VIEW,
    FILE_VIEW,
    SHOP_VIEW,
})

_EDITOR_PERMS = _VIEWER_PERMS | frozenset({
    KNOWLEDGE_CREATE,
    KNOWLEDGE_EDIT,
    MACHINE_CREATE,
    MACHINE_EDIT,
    MACHINE_CODE_IMPORT,
    MACHINE_CODE_EDIT,
    ERROR_CREATE,
    ERROR_EDIT,
    TASK_CREATE,
    TASK_EDIT,
    TASK_COMPLETE,
    REPORT_CREATE,
    REPORT_EDIT,
    FILE_UPLOAD,
})

_ADMIN_PERMS = _EDITOR_PERMS | frozenset({
    KNOWLEDGE_DELETE,
    KNOWLEDGE_APPROVE,
    MACHINE_DELETE,
    ERROR_APPROVE,
    FILE_DELETE,
    USER_VIEW,
    USER_CREATE,
    USER_EDIT,
    USER_DISABLE,
    AUDIT_VIEW,
    SETTINGS_VIEW,
})

_SUPER_ADMIN_PERMS = _ADMIN_PERMS | frozenset({
    SHOP_MANAGE,
    SETTINGS_EDIT,
})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.VIEWER: _VIEWER_PERMS,
    Role.EDITOR: _EDITOR_PERMS,
    Role.ADMIN: _ADMIN_PERMS,
    Role.SUPER_ADMIN: _SUPER_ADMIN_PERMS,
}


def get_permissions(role: str) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    """Return True if the given role has the given permission."""
    return permission in get_permissions(role)


def has_any_permission(role: str, *permissions: str) -> bool:
    perms = get_permissions(role)
    return any(p in perms for p in permissions)


def has_all_permissions(role: str, *permissions: str) -> bool:
    perms = get_permissions(role)
    return all(p in perms for p in permissions)
