"""R32 覆盖率攻坚 —— app/services/secrets_manager.py 语句缺口补全。

覆盖：
- _load_key_store: 62（JSON 顶层不是 dict → None）、66（versions/default_key 形态非法 → None）
- _persist_key_store: 92-93（原子替换 OSError → 仅告警，保持内存态）
- _init_default_key: 139（密钥库 versions 里混入非 dict 条目 → 跳过）

隔离前提（与 tests/unit/test_secrets_manager_full.py 一致，必须保留）：
autouse fixture 把 LOCALAPPDATA 指向 tmp_path，否则本文件写下的假密钥会落进真实
用户密钥库 %LOCALAPPDATA%\\bumofu-assistance\\data\\.secrets_manager_keys.json，
导致真实加密数据永久无法解密（数据损坏级缺陷）。
"""

import json
import os
import time
from pathlib import Path

import pytest

from app.services.secrets_manager import KEYS_FILE_NAME, SecretsManager


@pytest.fixture(autouse=True)
def _isolate_key_store(monkeypatch, tmp_path):
    """把密钥库目录隔离到 tmp_path，绝不触碰真实用户密钥库。"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)


def _keys_path(tmp_path: Path) -> Path:
    return tmp_path / "bumofu-assistance" / "data" / KEYS_FILE_NAME


class TestLoadKeyStoreRejectsMalformed:
    def test_top_level_not_dict_returns_none(self, tmp_path):
        """JSON 顶层是 list → 视为损坏，退回内存态（61-62）。"""
        mgr = SecretsManager()
        path = _keys_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[1, 2, 3]", encoding="utf-8")

        assert mgr._load_key_store() is None

    def test_bad_versions_or_default_key_returns_none(self, tmp_path):
        """versions 非 list / default_key 为空串 → 均返回 None（65-66）。"""
        mgr = SecretsManager()
        path = _keys_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(json.dumps({"versions": "not-a-list", "default_key": "k"}), encoding="utf-8")
        assert mgr._load_key_store() is None

        path.write_text(json.dumps({"versions": [], "default_key": ""}), encoding="utf-8")
        assert mgr._load_key_store() is None


class TestPersistKeyStoreFailure:
    def test_os_replace_failure_only_warns(self, monkeypatch, tmp_path):
        """原子替换抛 OSError → 记 warning，不向上抛（92-93）。"""
        mgr = SecretsManager()

        def _boom(src, dst):
            raise OSError("atomic replace failed")

        monkeypatch.setattr(os, "replace", _boom)

        # 不抛异常即通过（失败仅告警，保持内存态不中断业务）
        mgr._persist_key_store()


class TestInitDefaultKeySkipsBadVersionEntries:
    def test_non_dict_version_entry_is_skipped(self, tmp_path):
        """密钥库 versions 中混入非 dict 条目 → 跳过该条，其余版本仍加载（138-139）。"""
        path = _keys_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "default_key": "dk-material",
                    "versions": ["not-a-dict", {"version_id": "v9", "key": "v9-material"}],
                }
            ),
            encoding="utf-8",
        )

        mgr = SecretsManager()

        assert mgr._secrets["default"] == "dk-material"
        assert mgr._secrets["v9"] == "v9-material"
        assert any(v.get("version_id") == "v9" for v in mgr._key_versions)

    def test_version_metadata_extras_are_restored(self, tmp_path):
        """密钥库版本条目里的 expires_at / revoked_at 一并还原（146-148）。"""
        path = _keys_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "default_key": "dk-material",
                    "versions": [
                        {
                            "version_id": "v1",
                            "key": "k1",
                            "created_at": 1.0,
                            "is_active": False,
                            "key_type": "fernet",
                            "expires_at": 2.0,
                            "revoked_at": 3.0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        mgr = SecretsManager()

        entry = next(v for v in mgr._key_versions if v.get("version_id") == "v1")
        assert entry["expires_at"] == 2.0
        assert entry["revoked_at"] == 3.0


class TestCleanupKeepsRecentRevokedKey:
    def test_recently_revoked_key_is_kept(self):
        """已撤销但未超保留期的版本 → 不移除，循环回退（310->304）。"""
        mgr = SecretsManager()
        now = time.time()
        mgr._key_versions = [
            {
                "version_id": "vx",
                "created_at": now,
                "is_active": False,
                "revoked_at": now,
                "key_type": "fernet",
            }
        ]
        mgr._secrets["vx"] = "k-material"

        assert mgr.cleanup_expired_keys(keep_days=90) == 0
        assert mgr._secrets["vx"] == "k-material"
