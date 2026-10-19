"""v1.15.10 补充测试 2：secrets_manager 密钥库加载的无效条目/额外字段/回退分支。

背景：v1.15.7/1.15.8 的 8 段 CI 合并覆盖率 99.99%，missing 包含
`app/services/secrets_manager.py` 行 143（无效版本条目 continue）、148（expires_at/revoked_at 写入）、
分支 151->155（全部条目无效时回退默认版本）。本文件以 monkeypatch `_load_key_store` 精确覆盖。
"""
import pytest

from app.services import secrets_manager as sm_module
from app.services.secrets_manager import SecretsManager


@pytest.fixture(autouse=True)
def _isolate_key_store(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)


class TestLoadKeyStoreBranches:
    def test_invalid_entries_skipped_and_extras_written(self, monkeypatch):
        """含无效条目（缺 version_id / 缺 key）→ continue；含 expires_at/revoked_at → 写入 entry。"""
        store = {
            "default_key": "default-key-material",
            "versions": [
                {"version_id": None, "key": "k"},  # 缺 version_id → line 143 continue
                {"version_id": "v2"},  # 缺 key → line 143 continue
                {
                    "version_id": "v3",
                    "key": "k3",
                    "expires_at": 123.0,
                    "revoked_at": 456.0,
                    "created_at": 1.0,
                },
            ],
        }
        monkeypatch.setattr(SecretsManager, "_load_key_store", lambda self: store)

        mgr = SecretsManager()

        assert mgr._secrets["default"] == "default-key-material"
        assert mgr._secrets["v3"] == "k3"
        # 无效的 v2 不应进入密钥表
        assert "v2" not in mgr._secrets
        # v3 的额外字段被写入 key_versions
        v3 = [e for e in mgr._key_versions if e.get("version_id") == "v3"]
        assert v3 and v3[0].get("expires_at") == 123.0 and v3[0].get("revoked_at") == 456.0

    def test_all_entries_invalid_falls_back_to_default_version(self, monkeypatch):
        """所有条目无效（loaded=0）→ 不 return，追加默认 v1 版本（分支 151->155）。"""
        store = {
            "default_key": "default-key-material",
            "versions": [
                {"version_id": None, "key": "k"},
                {"version_id": "v2"},
                "not-a-dict",  # line 138 continue
            ],
        }
        monkeypatch.setattr(SecretsManager, "_load_key_store", lambda self: store)

        mgr = SecretsManager()

        # 没有有效版本时回退到内存态默认版本
        assert any(e.get("version_id") == "v1" for e in mgr._key_versions)
        # 且未加载任何历史版本
        assert "v2" not in mgr._secrets
