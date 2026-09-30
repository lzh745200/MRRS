"""Tests for app/services/secrets_manager.py — 目标 100% 覆盖。

覆盖全部方法：
- _init_default_key: ENCRYPTION_KEY 已设 / 未设+Fernet / 未设+ImportError 兜底
- get_secret: 内部存储 / 环境变量 / 默认值 / 不存在
- set_secret: 设置密钥
- delete_secret: 存在 / 不存在
- list_key_versions: 按创建时间倒序 / 空
- rotate_key: version_id=None 停用所有其他 / version_id=指定 停用该版本
- create_key: fernet / 非 fernet / 带 expires_days / 不带 expires_days
- revoke_key: 存在 / 不存在
- cleanup_expired_keys: 有过期 / 无过期 / 活跃密钥保留
- 全局实例
"""
import time


from app.services.secrets_manager import SecretsManager, secrets_manager


# ---------------------------------------------------------------------------
# _init_default_key —— 三条分支
# ---------------------------------------------------------------------------


class TestInitDefaultKey:
    def test_with_encryption_key_env(self, monkeypatch):
        """ENCRYPTION_KEY 环境变量已设 → 直接使用。"""
        monkeypatch.setenv("ENCRYPTION_KEY", "my-env-key")
        mgr = SecretsManager()
        assert mgr._secrets["default"] == "my-env-key"
        assert mgr._key_versions[0]["is_active"] is True

    def test_default_key_is_valid_fernet_key(self, monkeypatch, tmp_path):
        """深审 #52：默认密钥必须能被 Fernet() 接受（key_type 声明为 fernet）。"""
        from cryptography.fernet import Fernet
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        mgr = SecretsManager()
        # 不抛 ValueError 即为合法 Fernet key（32 字节 url-safe base64）
        Fernet(mgr._secrets["default"].encode())
        # 往返加解密可正常工作
        f = Fernet(mgr._secrets["default"].encode())
        assert f.decrypt(f.encrypt(b"payload")) == b"payload"

    def test_fallback_on_unwritable_dir_is_valid_fernet(self, monkeypatch, tmp_path):
        """磁盘不可写触发兜底分支时，密钥仍须是合法 Fernet key（深审 #52）。"""
        from cryptography.fernet import Fernet
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

        def boom(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr("os.makedirs", boom)
        mgr = SecretsManager()
        Fernet(mgr._secrets["default"].encode())

    def test_without_env_uses_fernet(self, monkeypatch):
        """ENCRYPTION_KEY 未设 + cryptography 可用 → Fernet.generate_key。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        # 生成的 Fernet 密钥是 base64 编码的 44 字符串
        assert mgr._secrets["default"] is not None
        assert len(mgr._secrets["default"]) >= 32

    def test_without_env_fernet_import_error(self, monkeypatch):
        """ENCRYPTION_KEY 未设 + cryptography 不可用 → 退化为 base64 随机串兜底。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        # 让 `from cryptography.fernet import Fernet` 抛 ImportError
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "cryptography.fernet" or name.startswith("cryptography"):
                raise ImportError("no cryptography")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        mgr = SecretsManager()
        assert "default" in mgr._secrets
        assert mgr._secrets["default"] is not None
        # 退化为 32 字节 urlsafe base64（仍为 44 字符格式，长度与 Fernet key 一致）
        assert len(mgr._secrets["default"]) == 44

    def test_generate_fallback_key_directly(self, monkeypatch):
        """_generate_fallback_key 在 cryptography 可用时返回合法 Fernet key。"""
        from cryptography.fernet import Fernet
        key = SecretsManager._generate_fallback_key()
        Fernet(key.encode())


# ---------------------------------------------------------------------------
# rotate_key
# ---------------------------------------------------------------------------


class TestRotateKey:
    def test_without_version_id_deactivates_all_others(self, monkeypatch):
        """version_id=None → 停用所有其他版本，返回新版本 ID。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        # 初始有一个 v1 活跃版本
        assert len(mgr._key_versions) == 1
        old_version = mgr._key_versions[0]["version_id"]
        assert mgr._key_versions[0]["is_active"] is True

        new_id = mgr.rotate_key()

        # 新版本已添加
        assert new_id != old_version
        assert new_id in mgr._secrets
        assert len(mgr._key_versions) == 2
        # 旧版本被停用
        assert mgr._key_versions[0]["is_active"] is False
        # 新版本活跃
        assert mgr._key_versions[1]["is_active"] is True
        assert mgr._key_versions[1]["version_id"] == new_id

    def test_with_version_id_deactivates_only_that(self, monkeypatch):
        """version_id=指定 → 仅停用该版本，其他保持原状。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        # 先创建一个额外的活跃版本
        first_new = mgr.rotate_key()  # 此时 v1 被停用，first_new 活跃
        assert mgr._key_versions[0]["is_active"] is False  # v1 停用
        assert mgr._key_versions[1]["is_active"] is True  # first_new 活跃

        # 再轮换，指定停用 first_new
        second_new = mgr.rotate_key(version_id=first_new)

        # first_new 被停用
        first_entry = next(v for v in mgr._key_versions if v["version_id"] == first_new)
        assert first_entry["is_active"] is False
        # v1 仍然是停用状态（未被重新激活）
        assert mgr._key_versions[0]["is_active"] is False
        # 新版本活跃
        second_entry = next(v for v in mgr._key_versions if v["version_id"] == second_new)
        assert second_entry["is_active"] is True
        # second_new 密钥已保存
        assert second_new in mgr._secrets


# ---------------------------------------------------------------------------
# create_key —— fernet 分支 + expires_days 分支
# ---------------------------------------------------------------------------


class TestCreateKey:
    def test_fernet_type_generates_fernet_key(self, monkeypatch):
        """key_type='fernet' → 使用 Fernet.generate_key。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        version_id = mgr.create_key(key_type="fernet")
        # Fernet 密钥是 44 字符的 base64 字符串
        key = mgr._secrets[version_id]
        assert len(key) == 44
        assert version_id in [v["version_id"] for v in mgr._key_versions]
        entry = next(v for v in mgr._key_versions if v["version_id"] == version_id)
        assert entry["key_type"] == "fernet"
        assert entry["is_active"] is True
        assert "expires_at" not in entry  # 未设过期

    def test_with_expires_days_sets_expires_at(self, monkeypatch):
        """expires_days=7 → key_info 含 expires_at。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        before = time.time()
        version_id = mgr.create_key(key_type="aes", expires_days=7)
        after = time.time()
        entry = next(v for v in mgr._key_versions if v["version_id"] == version_id)
        assert "expires_at" in entry
        # expires_at ≈ now + 7*86400
        expected = before + 7 * 86400
        assert expected <= entry["expires_at"] <= after + 7 * 86400

    def test_non_fernet_type_generates_random_key(self, monkeypatch):
        """key_type='aes' → 使用 secrets.token_urlsafe。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        version_id = mgr.create_key(key_type="aes")
        key = mgr._secrets[version_id]
        # token_urlsafe(32) 生成 ~43 字符
        assert len(key) >= 40
        entry = next(v for v in mgr._key_versions if v["version_id"] == version_id)
        assert entry["key_type"] == "aes"


# ---------------------------------------------------------------------------
# get_secret / set_secret / delete_secret
# ---------------------------------------------------------------------------


class TestGetSecret:
    def test_from_internal_storage(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr._secrets["my_key"] = "my_value"
        assert mgr.get_secret("my_key") == "my_value"

    def test_fallback_to_env(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENV_KEY", "env_value")
        mgr = SecretsManager()
        assert mgr.get_secret("ENV_KEY") == "env_value"

    def test_returns_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("MISSING_KEY", raising=False)
        mgr = SecretsManager()
        assert mgr.get_secret("MISSING_KEY", default="fallback") == "fallback"

    def test_returns_none_when_missing(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("GONE", raising=False)
        mgr = SecretsManager()
        assert mgr.get_secret("GONE") is None


class TestSetSecret:
    def test_set_and_get(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr.set_secret("new_key", "new_value")
        assert mgr._secrets["new_key"] == "new_value"
        assert mgr.get_secret("new_key") == "new_value"


class TestDeleteSecret:
    def test_delete_existing(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr._secrets["tmp"] = "v"
        assert mgr.delete_secret("tmp") is True
        assert "tmp" not in mgr._secrets

    def test_delete_missing_returns_false(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        assert mgr.delete_secret("nope") is False


# ---------------------------------------------------------------------------
# list_key_versions
# ---------------------------------------------------------------------------


class TestListKeyVersions:
    def test_sorted_by_created_at_desc(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr._key_versions = [
            {"version_id": "v1", "created_at": 1000},
            {"version_id": "v2", "created_at": 2000},
        ]
        result = mgr.list_key_versions()
        assert [v["version_id"] for v in result] == ["v2", "v1"]

    def test_empty_list(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr._key_versions = []
        assert mgr.list_key_versions() == []


# ---------------------------------------------------------------------------
# revoke_key
# ---------------------------------------------------------------------------


class TestRevokeKey:
    def test_revoke_existing(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        mgr._key_versions = [{"version_id": "v1", "is_active": True}]
        assert mgr.revoke_key("v1") is True
        assert mgr._key_versions[0]["is_active"] is False
        assert "revoked_at" in mgr._key_versions[0]

    def test_revoke_missing_returns_false(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        assert mgr.revoke_key("nonexistent") is False


# ---------------------------------------------------------------------------
# cleanup_expired_keys
# ---------------------------------------------------------------------------


class TestCleanupExpiredKeys:
    def test_removes_expired_revoked_keys(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        now = time.time()
        old = now - 100 * 86400  # 100 天前
        mgr._key_versions = [
            {"version_id": "v1", "is_active": False, "revoked_at": old, "created_at": old},
            {"version_id": "v2", "is_active": True, "created_at": now},
        ]
        mgr._secrets = {"v1": "old", "v2": "new", "default": "d"}
        deleted = mgr.cleanup_expired_keys(keep_days=90)
        assert deleted == 1
        assert len(mgr._key_versions) == 1
        assert "v1" not in mgr._secrets

    def test_no_expired_keys(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        now = time.time()
        mgr._key_versions = [
            {"version_id": "v1", "is_active": True, "created_at": now},
        ]
        assert mgr.cleanup_expired_keys(keep_days=90) == 0

    def test_active_keys_preserved_even_if_old(self, monkeypatch):
        """活跃密钥即使创建时间久远也不被清理。"""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        mgr = SecretsManager()
        old = time.time() - 200 * 86400
        mgr._key_versions = [
            {"version_id": "v1", "is_active": True, "created_at": old},
        ]
        assert mgr.cleanup_expired_keys(keep_days=90) == 0
        assert len(mgr._key_versions) == 1


# ---------------------------------------------------------------------------
# 全局实例
# ---------------------------------------------------------------------------


class TestGlobalInstance:
    def test_global_instance_has_default_key(self):
        """全局实例初始化后含 default 密钥和 v1 版本。"""
        assert "default" in secrets_manager._secrets
        assert len(secrets_manager._key_versions) >= 1
