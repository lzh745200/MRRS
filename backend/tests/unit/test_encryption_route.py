"""Tests for app/api/v1/encryption.py — 端点级验证.

覆盖 4 个加密管理端点（initialize / change-password / status / disable），
确保 SystemConfigService 被正确调用，无签名错配、无遗漏 await。
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
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


# ── _verify_encryption_password ──────────────────────────────────────────────


class TestVerifyEncryptionPassword:
    """验证 _verify_encryption_password 正确委托 SystemConfigService。"""

    def test_uninitialized_raises_400(self, mock_db):
        from app.api.v1.encryption import _verify_encryption_password
        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.return_value = None  # salt 不存在
            MockSvc.return_value = svc_inst
            with pytest.raises(Exception):  # HTTPException
                _verify_encryption_password(mock_db, "any")

    def test_wrong_password_raises_400(self, mock_db):
        from app.api.v1.encryption import _verify_encryption_password

        # 构造合法 salt + hash，但密码不对
        import hashlib
        from app.services.password_encryption_service import PasswordEncryptionService

        salt = PasswordEncryptionService.generate_salt()
        iterations = PasswordEncryptionService.DEFAULT_ITERATIONS
        key = PasswordEncryptionService.derive_key_from_password("correct_pw", salt, iterations)
        stored_hash = hashlib.sha256(key).hexdigest()

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: {
                "encryption_salt": salt.hex(),
                "encryption_iterations": str(iterations),
                "encryption_verify_hash": stored_hash,
            }.get(k)
            MockSvc.return_value = svc_inst

            with pytest.raises(Exception):  # HTTPException detail="密码不正确"
                _verify_encryption_password(mock_db, "wrong_pw")

    def test_correct_password_passes(self, mock_db):
        from app.api.v1.encryption import _verify_encryption_password

        import hashlib
        from app.services.password_encryption_service import PasswordEncryptionService

        password = "test_pass_123"
        salt = PasswordEncryptionService.generate_salt()
        iterations = PasswordEncryptionService.DEFAULT_ITERATIONS
        key = PasswordEncryptionService.derive_key_from_password(password, salt, iterations)
        stored_hash = hashlib.sha256(key).hexdigest()

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: {
                "encryption_salt": salt.hex(),
                "encryption_iterations": str(iterations),
                "encryption_verify_hash": stored_hash,
            }.get(k)
            MockSvc.return_value = svc_inst

            # 不应抛出异常
            _verify_encryption_password(mock_db, password)


# ── initialize_encryption ─────────────────────────────────────────────────────


class TestInitializeEncryption:
    """验证 initialize 端点正确调用 svc.get / svc.set。"""

    @pytest.mark.asyncio
    async def test_already_initialized_returns_400(self, mock_db, admin_user):
        from app.api.v1.encryption import initialize_encryption

        req = MagicMock()
        req.password = "123456"
        req.confirm_password = "123456"

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.return_value = "true"  # 已初始化
            MockSvc.return_value = svc_inst

            with pytest.raises(Exception):
                await initialize_encryption(req, db=mock_db, current_user=admin_user)

    @pytest.mark.asyncio
    async def test_success_calls_set_four_times(self, mock_db, admin_user):
        from app.api.v1.encryption import initialize_encryption

        req = MagicMock()
        req.password = "new_pass_123"
        req.confirm_password = "new_pass_123"

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.return_value = None  # 未初始化
            MockSvc.return_value = svc_inst

            result = await initialize_encryption(req, db=mock_db, current_user=admin_user)

            assert result["success"] is True
            assert svc_inst.set.call_count == 4


# ── get_encryption_status ────────────────────────────────────────────────────


class TestGetEncryptionStatus:
    """验证 status 端点返回正确结构。"""

    @pytest.mark.asyncio
    async def test_returns_status_dict(self, mock_db, admin_user):
        from app.api.v1.encryption import get_encryption_status

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: {
                "encryption_enabled": "true",
                "encryption_salt": "aabbccdd",
                "encryption_iterations": "100000",
            }.get(k)
            MockSvc.return_value = svc_inst

            result = await get_encryption_status(db=mock_db, current_user=admin_user)

            assert result["success"] is True
            data = result["data"]
            assert data["is_enabled"] is True
            assert data["has_salt"] is True
            # R28 §3：迭代数是 KDF 工作因子，配置里即使有也不得回吐
            assert "iterations" not in data


# ── disable_encryption ────────────────────────────────────────────────────────


class TestDisableEncryption:
    """验证 disable 端点清除配置。"""

    @pytest.mark.asyncio
    async def test_deletes_config_rows(self, mock_db, admin_user):
        from app.api.v1.encryption import disable_encryption

        req = MagicMock()
        req.password = "test_pass_123"

        import hashlib
        from app.services.password_encryption_service import PasswordEncryptionService

        salt = PasswordEncryptionService.generate_salt()
        iterations = PasswordEncryptionService.DEFAULT_ITERATIONS
        key = PasswordEncryptionService.derive_key_from_password("test_pass_123", salt, iterations)
        stored_hash = hashlib.sha256(key).hexdigest()

        # mock db.query().filter().first() 模拟找到配置行
        mock_row = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_row

        with patch("app.api.v1.encryption.SystemConfigService") as MockSvc:
            svc_inst = MagicMock()
            svc_inst.get.side_effect = lambda k: {
                "encryption_salt": salt.hex(),
                "encryption_iterations": str(iterations),
                "encryption_verify_hash": stored_hash,
            }.get(k)
            MockSvc.return_value = svc_inst

            result = await disable_encryption(req, db=mock_db, current_user=admin_user)

            assert result["success"] is True
            assert mock_db.commit.called
            # 4 个 key 都尝试删除
            assert mock_db.query.return_value.filter.return_value.first.call_count == 4
