"""
完整测试 - app.services.secrets_manager
覆盖率目标: 100%
"""
import time
import os
from unittest.mock import patch

class TestSecretsManagerCreation:
    """测试 SecretsManager 创建"""

    def test_manager_creation(self):
        """测试创建密钥管理器"""
        from app.services.secrets_manager import SecretsManager

        with patch.object(SecretsManager, '_init_default_key'):
            manager = SecretsManager()
            assert manager._secrets == {}
            assert manager._key_versions == []

    def test_init_default_key_with_env(self):
        """测试初始化 - 从环境变量获取密钥"""
        from app.services.secrets_manager import SecretsManager

        with patch.dict(os.environ, {"ENCRYPTION_KEY": "env_key_value"}):
            manager = SecretsManager()
            manager._init_default_key()
            assert manager._secrets["default"] == "env_key_value"

    def test_init_default_key_reads_existing_key_file(self, tmp_path):
        """W27 补：已存在密钥文件时**复用**其中密钥（不得每次重新生成）。

        这是「重启后数据可恢复」的前提：重新生成会让历史密文全部解不开。
        """
        from cryptography.fernet import Fernet

        from app.services.secrets_manager import SecretsManager

        key_dir = tmp_path / "bumofu-assistance" / "data"
        key_dir.mkdir(parents=True)
        persisted = Fernet.generate_key().decode()
        (key_dir / ".secrets_manager_key").write_text(persisted, encoding="utf-8")

        env = {k: v for k, v in os.environ.items() if k != "ENCRYPTION_KEY"}
        env["LOCALAPPDATA"] = str(tmp_path)
        with patch.dict(os.environ, env, clear=True):
            manager = SecretsManager()

        assert manager._secrets["default"] == persisted

    def test_init_default_key_import_error(self):
        """测试初始化 - Fernet 导入失败时回退生成合法 key。

        W27 修正测试手法：原实现 patch `builtins.__import__` 让**所有** import
        抛 ImportError —— 这会把 except 分支里 `_generate_fallback_key()` 自身所需
        的导入也一并打断，ImportError 从 except 分支逃逸，用例恒红（既有失败，
        与被测行为无关）。改为只把 `cryptography` 从 sys.modules 抹掉，
        精确模拟"可选依赖未安装"。
        """
        import sys

        from app.services.secrets_manager import SecretsManager

        with patch.dict(os.environ, {}):
            with patch.dict(sys.modules, {"cryptography": None,
                                          "cryptography.fernet": None}):
                manager = SecretsManager()
                # 由于 ImportError，应走兜底生成
                assert "default" in manager._secrets

class TestGetSecret:
    """测试 get_secret 方法"""

    def test_get_secret_from_internal(self):
        """测试从内部存储获取密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        manager._secrets["test_key"] = "test_value"

        result = manager.get_secret("test_key")
        assert result == "test_value"

    def test_get_secret_from_env(self):
        """测试从环境变量获取密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()

        with patch.dict(os.environ, {"ENV_KEY": "env_value"}):
            result = manager.get_secret("ENV_KEY")
            assert result == "env_value"

    def test_get_secret_with_default(self):
        """测试获取密钥使用默认值"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        result = manager.get_secret("nonexistent", default="default_value")
        assert result == "default_value"

    def test_get_secret_not_found(self):
        """测试获取不存在的密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        result = manager.get_secret("nonexistent")
        assert result is None

class TestSetSecret:
    """测试 set_secret 方法"""

    def test_set_secret(self):
        """测试设置密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        manager.set_secret("new_key", "new_value")

        assert manager._secrets["new_key"] == "new_value"

class TestDeleteSecret:
    """测试 delete_secret 方法"""

    def test_delete_secret_success(self):
        """测试删除密钥成功"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        manager._secrets["test_key"] = "test_value"

        result = manager.delete_secret("test_key")

        assert result is True
        assert "test_key" not in manager._secrets

    def test_delete_secret_not_found(self):
        """测试删除不存在的密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        result = manager.delete_secret("nonexistent")

        assert result is False

class TestListKeyVersions:
    """测试 list_key_versions 方法"""

    def test_list_key_versions(self):
        """测试列出密钥版本"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        manager._key_versions = [
            {"version_id": "v1", "created_at": 1000},
            {"version_id": "v2", "created_at": 2000},
        ]

        result = manager.list_key_versions()

        assert len(result) == 2
        # 应该按创建时间倒序排列
        assert result[0]["version_id"] == "v2"

    def test_list_key_versions_empty(self):
        """测试列出空密钥版本"""
        from app.services.secrets_manager import SecretsManager

        with patch.object(SecretsManager, '_init_default_key'):
            manager = SecretsManager()
            manager._key_versions = []  # Reset to empty
            result = manager.list_key_versions()

        assert result == []

class TestCreateKey:
    """测试 create_key 方法"""

    def test_create_key_other_type(self):
        """测试创建其他类型密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()

        with patch('app.services.secrets_manager.secrets.token_urlsafe', return_value="random_key"):
            version_id = manager.create_key(key_type="aes")

        assert manager._secrets[version_id] == "random_key"

class TestRevokeKey:
    """测试 revoke_key 方法"""

    def test_revoke_key_success(self):
        """测试撤销密钥成功"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        manager._key_versions = [
            {"version_id": "v1", "is_active": True}
        ]

        result = manager.revoke_key("v1")

        assert result is True
        assert manager._key_versions[0]["is_active"] is False
        assert "revoked_at" in manager._key_versions[0]

    def test_revoke_key_not_found(self):
        """测试撤销不存在的密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        result = manager.revoke_key("nonexistent")

        assert result is False

class TestCleanupExpiredKeys:
    """测试 cleanup_expired_keys 方法"""

    def test_cleanup_expired_keys(self):
        """测试清理过期密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        current_time = time.time()
        old_time = current_time - (100 * 86400)  # 100天前

        manager._key_versions = [
            {"version_id": "v1", "is_active": False, "revoked_at": old_time, "created_at": old_time},
            {"version_id": "v2", "is_active": True, "created_at": current_time},
        ]
        manager._secrets["v1"] = "old_key"
        manager._secrets["v2"] = "new_key"

        deleted_count = manager.cleanup_expired_keys(keep_days=90)

        assert deleted_count == 1
        assert len(manager._key_versions) == 1
        assert "v1" not in manager._secrets

    def test_cleanup_no_expired_keys(self):
        """测试清理 - 无过期密钥"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        current_time = time.time()

        manager._key_versions = [
            {"version_id": "v1", "is_active": True, "created_at": current_time},
        ]

        deleted_count = manager.cleanup_expired_keys(keep_days=90)

        assert deleted_count == 0

    def test_cleanup_active_keys_preserved(self):
        """测试清理 - 活跃密钥被保留"""
        from app.services.secrets_manager import SecretsManager

        manager = SecretsManager()
        old_time = time.time() - (100 * 86400)

        manager._key_versions = [
            {"version_id": "v1", "is_active": True, "created_at": old_time},
        ]

        deleted_count = manager.cleanup_expired_keys(keep_days=90)

        assert deleted_count == 0
        assert len(manager._key_versions) == 1

class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from app.services.secrets_manager import secrets_manager, SecretsManager
        assert secrets_manager is not None
        assert isinstance(secrets_manager, SecretsManager)
