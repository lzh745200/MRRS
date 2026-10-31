"""SEC-1 回归：权限包导入不得成为提权通道（2026-10-31 审计）。

历史缺陷（Critical）：``/permission-packages/import`` 与 ``/confirm/{file_name}``
的鉴权是「非管理员 + 本机来源即放行」，而桌面应用天然从 loopback 调用 ——
于是**已登录的 viewer/user 就可上传自造权限包，把自己写成 super_admin /
data_scope=all**（包内容与校验和均由上传者自造，签名验证默认关闭）。

本文件把三条不变量钉死：
1. 已登录但非管理员 → 403（不再看 loopback）；
2. 匿名导入只允许「空库 + 本机」（离线首装一次性引导）；
3. 部门级 admin 确认导入时，包内 super_admin / all 必须被收敛为 admin / org。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import permission_package as mod
from app.services.permission_package_service import PermissionPackageService

SUPER_ADMIN = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True)
DEPT_ADMIN = SimpleNamespace(id=2, username="dept", role="admin", is_superuser=False)
VIEWER = SimpleNamespace(id=3, username="viewer", role="viewer", is_superuser=False)


def _request(host: str = "127.0.0.1") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=host))


def _db(has_users: bool) -> MagicMock:
    db = MagicMock()
    db.query.return_value.first.return_value = object() if has_users else None
    return db


def _assert_403(fn, *args, **kwargs) -> None:
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    assert exc.value.status_code == 403


# ---------------- 调用者判定（_assert_package_import_principal） ----------------


def test_logged_in_non_admin_is_rejected_even_from_loopback():
    """核心缺陷回归：viewer 从本机调用不再被放行。"""
    _assert_403(
        mod._assert_package_import_principal,
        _request("127.0.0.1"),
        VIEWER,
        _db(has_users=True),
    )


def test_logged_in_plain_user_is_rejected():
    _assert_403(
        mod._assert_package_import_principal,
        _request("127.0.0.1"),
        SimpleNamespace(id=4, username="u", role="user", is_superuser=False),
        _db(has_users=False),
    )


def test_department_admin_may_preview_but_not_grant_superuser():
    assert (
        mod._assert_package_import_principal(_request(), DEPT_ADMIN, _db(True)) is False
    )


def test_super_admin_may_grant_superuser():
    assert (
        mod._assert_package_import_principal(_request(), SUPER_ADMIN, _db(True)) is True
    )


def test_anonymous_import_requires_loopback():
    _assert_403(
        mod._assert_package_import_principal,
        _request("10.0.0.8"),
        None,
        _db(has_users=False),
    )


def test_anonymous_import_rejected_when_accounts_exist():
    """机器上已有账号时，匿名导入必须要求先登录（防本机任意进程改写 RBAC）。"""
    _assert_403(
        mod._assert_package_import_principal,
        _request("::1"),
        None,
        _db(has_users=True),
    )


def test_anonymous_import_allowed_only_for_empty_database():
    assert mod._assert_package_import_principal(_request(), None, _db(has_users=False)) is True


# ---------------- 端点级：viewer 无法调用 import / confirm ----------------


def test_import_endpoint_rejects_viewer_before_touching_file():
    body = SimpleNamespace(filename="pkg.zip")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mod.import_permission_package(
                request=_request(),
                file=body,
                password=None,
                current_user=VIEWER,
                db=_db(has_users=True),
            )
        )
    assert exc.value.status_code == 403


def test_confirm_endpoint_rejects_viewer_before_touching_file():
    _assert_403(
        mod.confirm_import_permission_package,
        file_name="pkg.zip",
        body=SimpleNamespace(overwrite_existing=True, mode=None),
        current_user=VIEWER,
        db=_db(has_users=True),
        request=_request(),
        force=False,
    )


def test_confirm_admin_passes_allow_privileged_false(tmp_path):
    """部门级 admin 确认导入时必须以 allow_privileged=False 调服务层。"""
    package = tmp_path / "pkg.zip"
    package.write_bytes(b"PK\x03\x04stub")

    service = MagicMock()
    service.confirm_import.return_value = {"success": True}
    with (
        patch.object(mod, "_resolve_package_upload_path", return_value=str(package)),
        patch.object(mod, "assert_not_duplicate", return_value=("sum", None)),
        patch.object(mod, "PermissionPackageService", return_value=service),
        patch.object(mod, "write_work_log"),
        patch.object(mod, "record_import"),
    ):
        mod.confirm_import_permission_package(
            file_name="pkg.zip",
            body=SimpleNamespace(overwrite_existing=True, mode=None),
            current_user=DEPT_ADMIN,
            db=_db(has_users=True),
            request=_request(),
            force=False,
        )

    assert service.confirm_import.call_args.kwargs["allow_privileged"] is False


# ---------------- 服务层：超管级取值收敛 ----------------


def test_sanitize_clamps_super_admin_and_all_for_non_privileged():
    svc = PermissionPackageService(db=None)
    stats: dict = {}
    role, scope = svc._sanitize_legacy_privilege(
        {"username": "x", "role": "super_admin", "data_scope": "all"}, False, stats
    )
    assert (role, scope) == ("admin", "org")
    assert stats["privileged_values_downgraded"] == 1


def test_sanitize_keeps_privileged_values_for_superuser_import():
    svc = PermissionPackageService(db=None)
    stats: dict = {}
    role, scope = svc._sanitize_legacy_privilege(
        {"role": "super_admin", "data_scope": "all"}, True, stats
    )
    assert (role, scope) == ("super_admin", "all")
    assert "privileged_values_downgraded" not in stats


def test_sanitize_normalizes_legacy_role_and_unknown_values():
    svc = PermissionPackageService(db=None)
    stats: dict = {}
    # 历史角色 manager/operator → admin/user；未知值回落最小权限
    assert svc._sanitize_legacy_privilege({"role": "manager"}, False, stats)[0] == "admin"
    assert svc._sanitize_legacy_privilege({"role": "operator"}, False, stats)[0] == "user"
    assert svc._sanitize_legacy_privilege({"role": "wizard"}, False, stats)[0] == "user"
    assert (
        svc._sanitize_legacy_privilege({"data_scope": "galaxy"}, False, stats)[1] == "org"
    )


def test_import_user_legacy_writes_clamped_role_for_non_privileged():
    svc = PermissionPackageService(db=None)
    user = SimpleNamespace(role="user", permissions="", data_scope="org")
    svc._resolve_user_by_username_or_id = lambda *a, **kw: user

    stats: dict = {}
    svc._import_user_legacy(
        [{"username": "x", "role": "super_admin", "data_scope": "all", "organization_id": None}],
        stats,
        [],
        merge_mode=False,
        allow_privileged=False,
    )

    assert user.role == "admin"
    assert user.data_scope == "org"
    assert stats["privileged_values_downgraded"] == 1
