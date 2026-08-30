"""app/api/v1/encryption.py 覆盖率补缺测试

补缺行：62（验证哈希缺失）、75（两次密码不一致）、78（密码过短）、
111-136（change_encryption_password 全函数：校验失败与成功路径）。
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.encryption import (
    ChangePasswordRequest,
    InitializeEncryptionRequest,
    _verify_encryption_password,
    change_encryption_password,
    initialize_encryption,
)
from app.services.password_encryption_service import PasswordEncryptionService


@pytest.fixture
def mock_db():
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    db.query.return_value = q
    return db


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    return u


def _make_svc_config(password: str):
    """用真实派生算法构造一组合法的 salt/iterations/verify_hash 配置。"""
    salt = PasswordEncryptionService.generate_salt()
    iterations = PasswordEncryptionService.DEFAULT_ITERATIONS
    key = PasswordEncryptionService.derive_key_from_password(password, salt, iterations)
    verify_hash = hashlib.sha256(key).hexdigest()
    return {
        "encryption_salt": salt.hex(),
        "encryption_iterations": str(iterations),
        "encryption_verify_hash": verify_hash,
    }


# ── _verify_encryption_password：验证哈希缺失（line 62） ──────────────────


class TestVerifyPasswordIncompleteData:
    def test_missing_verify_hash_raises_400(self, mock_db):
        """有盐值但无验证哈希 → 400 加密验证数据不完整（覆盖 line 62）。"""
        config = _make_svc_config("any_password")
        config["encryption_verify_hash"] = None  # 验证数据不完整

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: config.get(k)
            MockSvc.return_value = svc_inst

            with pytest.raises(HTTPException) as exc_info:
                _verify_encryption_password(mock_db, "any_password")

        assert exc_info.value.status_code == 400
        assert "验证数据不完整" in exc_info.value.detail


# ── initialize_encryption：参数校验分支（lines 75, 78） ───────────────────


class TestInitializeValidation:
    async def test_password_mismatch_raises_400(self, mock_db, admin_user):
        """两次输入密码不一致 → 400（覆盖 line 75）。"""
        req = InitializeEncryptionRequest(password="abc12345", confirm_password="xyz98765")

        with pytest.raises(HTTPException) as exc_info:
            await initialize_encryption(req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "不一致" in exc_info.value.detail

    async def test_short_password_raises_400(self, mock_db, admin_user):
        """密码长度少于6位 → 400（覆盖 line 78）。"""
        req = InitializeEncryptionRequest(password="12345", confirm_password="12345")

        with pytest.raises(HTTPException) as exc_info:
            await initialize_encryption(req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "不能少于6位" in exc_info.value.detail


# ── change_encryption_password：全函数（lines 111-136） ──────────────────


class TestChangeEncryptionPassword:
    async def test_new_password_mismatch_raises_400(self, mock_db, admin_user):
        """新密码两次输入不一致 → 400（覆盖 113-114）。"""
        req = ChangePasswordRequest(
            old_password="old_pass_1", new_password="new_pass_1", confirm_password="different"
        )

        with pytest.raises(HTTPException) as exc_info:
            await change_encryption_password(req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "不一致" in exc_info.value.detail

    async def test_short_new_password_raises_400(self, mock_db, admin_user):
        """新密码长度少于6位 → 400（覆盖 116-117）。"""
        req = ChangePasswordRequest(
            old_password="old_pass_1", new_password="12345", confirm_password="12345"
        )

        with pytest.raises(HTTPException) as exc_info:
            await change_encryption_password(req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "不能少于6位" in exc_info.value.detail

    async def test_wrong_old_password_raises_400(self, mock_db, admin_user):
        """旧密码不正确 → 400（覆盖 120 调用 _verify_encryption_password 抛错）。"""
        config = _make_svc_config("correct_old")
        req = ChangePasswordRequest(
            old_password="wrong_old", new_password="new_pass_1", confirm_password="new_pass_1"
        )

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: config.get(k)
            MockSvc.return_value = svc_inst

            with pytest.raises(HTTPException) as exc_info:
                await change_encryption_password(req, db=mock_db, current_user=admin_user)

        assert exc_info.value.status_code == 400
        assert "密码不正确" in exc_info.value.detail

    async def test_success_updates_derived_params(self, mock_db, admin_user):
        """旧密码正确 → 重新生成盐值并写入 3 项配置（覆盖 120-136）。"""
        config = _make_svc_config("old_pass_1")
        req = ChangePasswordRequest(
            old_password="old_pass_1", new_password="new_pass_1", confirm_password="new_pass_1"
        )

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: config.get(k)
            MockSvc.return_value = svc_inst

            result = await change_encryption_password(req, db=mock_db, current_user=admin_user)

        assert result == {"code": 200, "success": True, "message": "加密密码已更新"}
        # 写入盐值、迭代次数、验证哈希 3 项配置
        assert svc_inst.set.call_count == 3
        set_keys = {call.args[0] for call in svc_inst.set.call_args_list}
        assert set_keys == {
            "encryption_salt",
            "encryption_iterations",
            "encryption_verify_hash",
        }
        # 新盐值应为 64 位十六进制（32 字节）
        salt_call = next(c for c in svc_inst.set.call_args_list if c.args[0] == "encryption_salt")
        new_salt_hex = salt_call.args[1]
        assert len(new_salt_hex) == 64
        bytes.fromhex(new_salt_hex)  # 合法 hex
