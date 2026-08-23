"""app/api/v1/machine_code.py 覆盖率补缺测试

补缺行：395（POSIX 下重置密码临时文件 chmod 0o600）、
734-736 / 766-768 / 796-798 / 824-826（机器码权限四个端点的异常兜底）、
821（撤销单个权限成功返回）、853-855（用户实际权限端点异常兜底）。
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.machine_code as mc
from app.api.v1.machine_code import (
    MachineCodePermissionGrantRequest,
    MachineCodePermissionRevokeRequest,
    get_machine_code_permissions,
    get_user_effective_permissions,
    grant_machine_code_permissions,
    reset_password_with_machine_code,
    revoke_machine_code_permissions,
    revoke_single_machine_code_permission,
)
from app.services.rbac_service import Permission


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    return u


@pytest.fixture
def mock_db():
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    db.query.return_value = q
    return db


# ── reset_password_with_machine_code：安全加固（不再写明文临时文件） ─────────


class TestResetPasswordNoTempFile:
    async def test_no_plaintext_temp_file_written(self, mock_db):
        """重置密码后不落盘明文临时文件，新密码仅在响应中返回。"""
        q = mock_db.query.return_value
        user = MagicMock()
        user.username = "testuser"
        q.first.return_value = user

        svc = MagicMock()
        svc.get_machine_code.return_value = "MC001"
        svc.verify_machine_code.return_value = True

        with patch.object(mc, "check_rate_limit", AsyncMock(return_value=True)):
            with patch.object(mc, "get_client_ip", return_value="127.0.0.1"):
                with patch.object(mc, "MachineCodeService", return_value=svc):
                    with patch("app.core.security.generate_password", return_value="NewPwd123!x"):
                        with patch.object(os, "name", "posix"):
                            with patch("tempfile.mkstemp") as mock_mkstemp:
                                with patch.object(os, "chmod") as mock_chmod:
                                    result = await reset_password_with_machine_code(
                                        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
                                        username="testuser",
                                        machine_code="MC001",
                                        verification_code="VC001",
                                        db=mock_db,
                                    )
        assert result["code"] == 200
        assert result["data"]["username"] == "testuser"
        assert result["data"]["new_password"] == "NewPwd123!x"
        mock_mkstemp.assert_not_called()
        mock_chmod.assert_not_called()


# ── 机器码权限端点：异常兜底与单权限撤销成功 ──────────────────────────────


class TestMachineCodePermissionEndpoints:
    async def test_get_permissions_exception_raises_500(self, mock_db, admin_user):
        """查询权限服务抛异常 → 500（覆盖 734-736）。"""
        svc = MagicMock()
        svc.get_machine_code_permissions.side_effect = RuntimeError("db down")

        with patch.object(mc, "MachineCodePermissionService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await get_machine_code_permissions(1, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 500
        assert "获取机器码权限失败" in exc_info.value.detail

    async def test_grant_permissions_exception_raises_500(self, mock_db, admin_user):
        """批量授予抛异常 → 500（覆盖 766-768）。"""
        svc = MagicMock()
        svc.batch_grant_permissions.side_effect = RuntimeError("grant boom")
        req = MachineCodePermissionGrantRequest(permissions=[Permission.VILLAGE_READ])

        with patch.object(mc, "MachineCodePermissionService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await grant_machine_code_permissions(1, req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 500
        assert "授予机器码权限失败" in exc_info.value.detail

    async def test_revoke_permissions_exception_raises_500(self, mock_db, admin_user):
        """批量撤销抛异常 → 500（覆盖 796-798）。"""
        svc = MagicMock()
        svc.batch_revoke_permissions.side_effect = RuntimeError("revoke boom")
        req = MachineCodePermissionRevokeRequest(permissions=[Permission.VILLAGE_READ])

        with patch.object(mc, "MachineCodePermissionService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await revoke_machine_code_permissions(1, req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 500
        assert "撤销机器码权限失败" in exc_info.value.detail

    async def test_revoke_single_permission_success(self, mock_db, admin_user):
        """撤销单个权限成功 → 200 权限已撤销（覆盖 821）。"""
        svc = MagicMock()
        svc.revoke_permission.return_value = True

        with patch.object(mc, "MachineCodePermissionService", return_value=svc):
            result = await revoke_single_machine_code_permission(
                1, "village:read", db=mock_db, current_user=admin_user
            )

        assert result["code"] == 200
        assert result["success"] is True
        assert result["message"] == "权限已撤销"
        svc.revoke_permission.assert_called_once_with(1, "village:read")

    async def test_revoke_single_permission_exception_raises_500(self, mock_db, admin_user):
        """撤销单个权限服务抛异常 → 500（覆盖 824-826）。"""
        svc = MagicMock()
        svc.revoke_permission.side_effect = RuntimeError("revoke single boom")

        with patch.object(mc, "MachineCodePermissionService", return_value=svc):
            with pytest.raises(HTTPException) as exc_info:
                await revoke_single_machine_code_permission(
                    1, "village:read", db=mock_db, current_user=admin_user
                )

        assert exc_info.value.status_code == 500
        assert "撤销机器码权限失败" in exc_info.value.detail


# ── 用户实际权限端点：异常兜底（lines 853-855） ───────────────────────────


class TestUserEffectivePermissionsException:
    async def test_rbac_service_exception_raises_500(self, mock_db, admin_user):
        """rbac_service 查询抛异常 → 500（覆盖 853-855）。"""
        with patch.object(
            mc.rbac_service,
            "get_user_permissions_with_restrictions",
            new=AsyncMock(side_effect=RuntimeError("rbac down")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_user_effective_permissions(42, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 500
        assert "获取用户实际权限失败" in exc_info.value.detail
