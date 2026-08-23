"""app.api.v1.permission_package 覆盖补全 — 端点权限分支。

- export/download: 非管理员 403(仅管理员可导出)
- import: 允许登录前调用(验证预览,不写库)
- confirm: 非管理员仅允许本机来源(离线权限包导入场景)
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.permission_package as pp


def _non_admin():
    return SimpleNamespace(id=2, username="bob", role="user", is_superuser=False)


class TestNonAdminForbidden:
    def test_export_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            pp.export_permission_package(None, _non_admin(), MagicMock())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "需要管理员权限"

    def test_download_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            pp.download_permission_package("pkg.zip", _non_admin())
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "需要管理员权限"

    async def test_import_allowed_for_anonymous_preview(self):
        # 导入仅做验证预览(不写库),允许登录前调用——离线权限包导入场景
        # 非 zip 文件在权限检查前返回 400,证明非管理员可达(不再 403)
        file = SimpleNamespace(filename="pkg.tar")
        with pytest.raises(HTTPException) as exc_info:
            await pp.import_permission_package(MagicMock(), file, _non_admin(), MagicMock())
        assert exc_info.value.status_code == 400
        assert "zip" in exc_info.value.detail

    def test_confirm_forbidden_for_remote_non_admin(self):
        # 非管理员 + 非本机来源 → 403(仅允许本机离线导入)
        body = pp.PermissionPackageConfirmRequest()
        request = MagicMock()
        request.client.host = "10.0.0.5"
        with pytest.raises(HTTPException) as exc_info:
            pp.confirm_import_permission_package(
                "pkg.zip", body, _non_admin(), MagicMock(), request
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "仅允许本机导入权限包"

    def test_confirm_allowed_for_local_non_admin(self):
        # 非管理员 + 本机来源 → 通过来源校验,走到文件校验(不再 403)
        body = pp.PermissionPackageConfirmRequest()
        request = MagicMock()
        request.client.host = "127.0.0.1"
        with patch("os.path.exists", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package(
                    "pkg.zip", body, _non_admin(), MagicMock(), request
                )
        assert exc_info.value.status_code == 404
        assert "导入文件不存在" in exc_info.value.detail
