"""R62 回归：登录页离线首装导入权限包（2026-11-14）。

背景：SEC-1 只允许「空库 + 本机」匿名导入；但启动种子
``app.startup.seed._seed_default_admin`` 会在空库立即创建出厂 admin，
于是全新安装（以及卸载后清库重装）在登录页导入权限包时必然 403
「系统已存在账号，请先登录管理员账号后再导入权限包」。

本文件钉死新契约：
1. 仅 1 个出厂 admin（must_change_password=True、last_login=None）且未初始化
   → 视同空库，允许匿名导入；
2. 管理员登录过 / 改过密码 / 存在第二个账号 / 已初始化 / 非种子用户名
   → 仍然 403（SEC-1 不回归）；
3. 已登录非管理员仍然 403。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.v1 import permission_package as mod

VIEWER = SimpleNamespace(id=3, username="viewer", role="viewer", is_superuser=False)


class _Query:
    def __init__(self, users):
        self._users = users

    def limit(self, _n):
        return self

    def all(self):
        return list(self._users)

    def first(self):
        return self._users[0] if self._users else None


class _DB:
    def __init__(self, users):
        self._users = list(users)

    def query(self, *_args):
        return _Query(self._users)


def _request(host: str = "127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def _seed_admin(**overrides):
    data = dict(
        id=1,
        username="admin",
        role="admin",
        is_superuser=True,
        must_change_password=True,
        last_login=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _principal(users, *, initialized=False, host="127.0.0.1", current_user=None):
    with patch(
        "app.services.system_config_service.SystemConfigService.is_initialized",
        return_value=initialized,
    ):
        return mod._assert_package_import_principal(
            _request(host), current_user, _DB(users)
        )


def _assert_403(users, **kwargs):
    with pytest.raises(HTTPException) as exc:
        _principal(users, **kwargs)
    assert exc.value.status_code == 403


# ---------------- 放行：空库 / 出厂种子 admin 未使用 ----------------

def test_empty_database_still_allowed():
    assert _principal([]) is True


def test_pristine_seed_admin_allowed():
    """全新安装的真实形态：users 只有出厂 admin，登录页可直接导入权限包。"""
    assert _principal([_seed_admin()]) is True


def test_seed_username_from_env_allowed(monkeypatch):
    """DEFAULT_ADMIN_USERNAME 覆盖时，按其用户名识别出厂种子账号。"""
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "  root  ")
    assert _principal([_seed_admin(username="root")]) is True


# ---------------- 拒绝：机器已被使用 ----------------

def test_seed_admin_logged_in_rejected():
    _assert_403([_seed_admin(last_login=SimpleNamespace())])


def test_seed_admin_password_changed_rejected():
    _assert_403([_seed_admin(must_change_password=False)])


def test_not_superuser_rejected():
    _assert_403([_seed_admin(is_superuser=False)])


def test_second_account_rejected():
    _assert_403([_seed_admin(), _seed_admin(id=2, username="fqs001")])


def test_non_seed_username_rejected():
    _assert_403([_seed_admin(username="other_admin")])


def test_initialized_system_rejected():
    _assert_403([_seed_admin()], initialized=True)


def test_initialization_state_unavailable_fails_closed():
    db = _DB([_seed_admin()])
    with patch(
        "app.services.system_config_service.SystemConfigService.is_initialized",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(HTTPException) as exc:
            mod._assert_package_import_principal(_request(), None, db)
    assert exc.value.status_code == 403


def test_pristine_seed_admin_from_remote_host_rejected():
    _assert_403([_seed_admin()], host="10.0.0.8")


def test_logged_in_viewer_still_rejected():
    """SEC-1 核心不变量：已登录非管理员，即使库是种子状态也拒绝。"""
    with patch(
        "app.services.system_config_service.SystemConfigService.is_initialized",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            mod._assert_package_import_principal(_request(), VIEWER, _DB([_seed_admin()]))
    assert exc.value.status_code == 403


# ---------------- 端点级：门禁放行后才进入格式校验 ----------------

def test_import_endpoint_passes_guard_for_pristine_install():
    """非 .zip 文件应返回 400（说明已越过 403 门禁），而不是 403。"""
    body = SimpleNamespace(filename="pkg.txt")
    with patch(
        "app.services.system_config_service.SystemConfigService.is_initialized",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                mod.import_permission_package(
                    request=_request(),
                    file=body,
                    password=None,
                    current_user=None,
                    db=_DB([_seed_admin()]),
                )
            )
    assert exc.value.status_code == 400
    assert "zip" in str(exc.value.detail)
