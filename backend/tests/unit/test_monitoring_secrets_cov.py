"""app.api.v1.monitoring.secrets 覆盖率攻坚测试

直接 async 调用端点函数，覆盖密钥版本/轮换/创建/撤销/清理/状态六个端点。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.monitoring.secrets as m


@pytest.fixture()
def svc():
    mock = MagicMock()
    with patch.object(m, "secrets_manager", mock):
        yield mock


class TestListKeyVersions:
    async def test_lists_versions(self, svc):
        svc.list_key_versions.return_value = [{"version_id": "v1"}, {"version_id": "v2"}]
        result = await m.list_key_versions(current_user=MagicMock())
        assert result["count"] == 2
        assert [v["version_id"] for v in result["versions"]] == ["v1", "v2"]


class TestRotateKey:
    async def test_success(self, svc):
        svc.rotate_key.return_value = "v-new"
        result = await m.rotate_key(version_id="v-old", current_user=MagicMock())
        assert result["message"] == "密钥轮换成功"
        assert result["new_version"] == "v-new"
        svc.rotate_key.assert_called_once_with("v-old")

    async def test_value_error_becomes_400(self, svc):
        svc.rotate_key.side_effect = ValueError("版本不存在")
        with pytest.raises(HTTPException) as exc_info:
            await m.rotate_key(version_id="bad", current_user=MagicMock())
        assert exc_info.value.status_code == 400
        assert "版本不存在" in exc_info.value.detail


class TestCreateKey:
    async def test_creates_key(self, svc):
        svc.create_key.return_value = "v-1"
        result = await m.create_key(key_type="fernet", expires_days=30, current_user=MagicMock())
        assert result == {"message": "密钥创建成功", "version_id": "v-1"}
        svc.create_key.assert_called_once_with(key_type="fernet", expires_days=30)


class TestRevokeKey:
    async def test_success(self, svc):
        svc.revoke_key.return_value = True
        result = await m.revoke_key(version_id="v-1", current_user=MagicMock())
        assert result == {"message": "密钥已撤销", "version_id": "v-1"}

    async def test_missing_version_404(self, svc):
        svc.revoke_key.return_value = False
        with pytest.raises(HTTPException) as exc_info:
            await m.revoke_key(version_id="nope", current_user=MagicMock())
        assert exc_info.value.status_code == 404
        assert "nope" in exc_info.value.detail


class TestCleanupExpiredKeys:
    async def test_reports_deleted_count(self, svc):
        svc.cleanup_expired_keys.return_value = 3
        result = await m.cleanup_expired_keys(keep_days=60, current_user=MagicMock())
        assert result["deleted_count"] == 3
        assert "3" in result["message"]
        svc.cleanup_expired_keys.assert_called_once_with(60)


class TestGetSecretsStatus:
    async def test_with_active_versions(self, svc):
        svc.list_key_versions.return_value = [
            {"version_id": "v2", "is_active": True},
            {"version_id": "v1", "is_active": False},
        ]
        result = await m.get_secrets_status(current_user=MagicMock())
        assert result["total_versions"] == 2
        assert result["active_versions"] == 1
        assert result["latest_version"]["version_id"] == "v2"
        assert result["requires_rotation"] is False

    async def test_empty_requires_rotation(self, svc):
        svc.list_key_versions.return_value = []
        result = await m.get_secrets_status(current_user=MagicMock())
        assert result["total_versions"] == 0
        assert result["active_versions"] == 0
        assert result["latest_version"] is None
        assert result["requires_rotation"] is True
