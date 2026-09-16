"""Permission matrix tests."""

from app.security import permissions as P
from app.models import Role


def test_viewer_can_view():
    assert P.has_permission(Role.VIEWER, P.KNOWLEDGE_VIEW)
    assert P.has_permission(Role.VIEWER, P.MACHINE_VIEW)
    assert P.has_permission(Role.VIEWER, P.ERROR_VIEW)


def test_viewer_cannot_approve():
    assert not P.has_permission(Role.VIEWER, P.KNOWLEDGE_APPROVE)
    assert not P.has_permission(Role.VIEWER, P.USER_VIEW)


def test_editor_can_edit():
    assert P.has_permission(Role.EDITOR, P.KNOWLEDGE_EDIT)
    assert P.has_permission(Role.EDITOR, P.MACHINE_CREATE)
    assert not P.has_permission(Role.EDITOR, P.KNOWLEDGE_APPROVE)


def test_admin_can_approve():
    assert P.has_permission(Role.ADMIN, P.KNOWLEDGE_APPROVE)
    assert P.has_permission(Role.ADMIN, P.USER_VIEW)
    assert not P.has_permission(Role.ADMIN, P.SETTINGS_EDIT)


def test_super_admin_all():
    assert P.has_permission(Role.SUPER_ADMIN, P.SETTINGS_EDIT)
    assert P.has_permission(Role.SUPER_ADMIN, P.SHOP_MANAGE)
