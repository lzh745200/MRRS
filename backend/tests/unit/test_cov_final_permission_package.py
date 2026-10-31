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

    async def test_import_allowed_for_anonymous_preview_on_empty_database(self):
        # SEC-1：匿名预览只保留「空库 + 本机来源」的离线首装通道（不写库）。
        # 非 zip 文件在权限检查之后返回 400，证明该通道可达（不是 403）。
        file = SimpleNamespace(filename="pkg.tar")
        request = MagicMock()
        request.client.host = "127.0.0.1"
        db = MagicMock()
        db.query.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await pp.import_permission_package(request, file, None, None, db)
        assert exc_info.value.status_code == 400
        assert "zip" in exc_info.value.detail

    def test_confirm_forbidden_for_non_admin(self):
        # SEC-1：已登录非管理员 → 403（本机来源不再是免认证通道）
        body = pp.PermissionPackageConfirmRequest()
        request = MagicMock()
        request.client.host = "10.0.0.5"
        with pytest.raises(HTTPException) as exc_info:
            pp.confirm_import_permission_package(
                "pkg.zip", body, _non_admin(), MagicMock(), request
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "仅管理员可导入权限配置包"

    def test_confirm_forbidden_for_local_non_admin(self):
        # SEC-1 核心回归：本机来源 + 非管理员同样 403（历史提权路径）
        body = pp.PermissionPackageConfirmRequest()
        request = MagicMock()
        request.client.host = "127.0.0.1"
        with patch("os.path.exists", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package(
                    "pkg.zip", body, _non_admin(), MagicMock(), request
                )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "仅管理员可导入权限配置包"
