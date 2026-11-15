"""P1：权限包缺失用户必须在确认响应中显式告警。"""

from unittest.mock import MagicMock

from app.services.permission_package_service import PermissionPackageService


def _service():
    return PermissionPackageService(MagicMock())


def test_missing_users_exposed_as_partial_warning():
    svc = _service()
    stats = svc._init_import_stats()
    svc._missing_usernames = {"ghost_a", "ghost_b"}
    result = svc._build_import_response(
        stats,
        [],
        warnings=["以下 2 个用户不存在，个人权限/菜单已跳过"],
    )
    assert result["success"] is True
    assert result["partial"] is True
    assert result["skipped_user_count"] == 2
    assert result["skipped_usernames"] == ["ghost_a", "ghost_b"]
    assert result["warnings"]


def test_no_missing_users_is_not_partial():
    svc = _service()
    result = svc._build_import_response(svc._init_import_stats(), [], warnings=[])
    assert result["partial"] is False
    assert result["skipped_user_count"] == 0
    assert result["skipped_usernames"] == []


def test_note_missing_ignores_empty_values():
    svc = _service()
    svc._note_missing_username(None)
    svc._note_missing_username("")
    assert svc._missing_usernames == set()
