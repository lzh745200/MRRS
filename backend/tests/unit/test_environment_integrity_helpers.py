"""app.startup.environment 文件完整性辅助函数回归测试（深审 #79 / R16 重构）。

覆盖 `_load_integrity_manifest` / `_collect_integrity_mismatches` /
`_verify_file_integrity` 各分支：
- 清单缺失 / 解析失败 / 顶层非对象 → 按"未提供"处理（返回 None，不阻断启动）
- 有清单时严格比对：缺失、无法读取、未登记、哈希不符
- 无清单时仅记录，不产生 mismatches
- mismatches 非空时 fail-closed 抛 FileIntegrityError
"""

import json
import hashlib
from pathlib import Path

import pytest

from app.startup.environment import (
    FileIntegrityError,
    _collect_integrity_mismatches,
    _load_integrity_manifest,
    _verify_file_integrity,
)

_CRITICAL = ["app/main.py", "app/core/config.py"]


# ==================== _load_integrity_manifest ====================


class TestLoadIntegrityManifest:
    def test_absent_manifest_returns_none(self, tmp_path):
        assert _load_integrity_manifest(tmp_path) is None

    def test_valid_manifest_returns_dict(self, tmp_path):
        (tmp_path / "integrity_manifest.json").write_text(
            json.dumps({"app/main.py": "abc"}), encoding="utf-8"
        )
        assert _load_integrity_manifest(tmp_path) == {"app/main.py": "abc"}

    def test_unparsable_manifest_returns_none(self, tmp_path):
        (tmp_path / "integrity_manifest.json").write_text("{not json", encoding="utf-8")
        assert _load_integrity_manifest(tmp_path) is None

    def test_non_object_manifest_returns_none(self, tmp_path):
        (tmp_path / "integrity_manifest.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert _load_integrity_manifest(tmp_path) is None

    def test_manifest_read_failure_returns_none(self, tmp_path):
        """存在性检查通过但读取抛错（如权限）→ 同样按未提供处理。"""
        from unittest.mock import patch

        manifest_path = tmp_path / "integrity_manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            assert _load_integrity_manifest(tmp_path) is None


# ==================== _collect_integrity_mismatches ====================


class TestCollectIntegrityMismatches:
    def _write(self, base: Path, rel: str, content: bytes = b"data") -> str:
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def test_no_manifest_records_only(self, tmp_path):
        self._write(tmp_path, "app/main.py")
        assert _collect_integrity_mismatches(tmp_path, _CRITICAL, None) == []

    def test_missing_file_with_manifest_is_mismatch(self, tmp_path):
        self._write(tmp_path, "app/main.py")
        mismatches = _collect_integrity_mismatches(tmp_path, _CRITICAL, {})
        assert mismatches == ["app/core/config.py: 缺失"]

    def test_missing_file_without_manifest_is_warning_only(self, tmp_path):
        assert _collect_integrity_mismatches(tmp_path, _CRITICAL, None) == []

    def test_unreadable_file_with_manifest_is_mismatch(self, tmp_path):
        from unittest.mock import patch

        self._write(tmp_path, "app/main.py")
        self._write(tmp_path, "app/core/config.py")
        real_read = Path.read_bytes

        def flaky(self):
            if self.name == "config.py":
                raise OSError("locked")
            return real_read(self)

        with patch.object(Path, "read_bytes", flaky):
            mismatches = _collect_integrity_mismatches(tmp_path, _CRITICAL, {})

        assert len(mismatches) == 1
        assert mismatches[0].startswith("app/core/config.py: 无法读取")

    def test_unreadable_file_without_manifest_is_warning_only(self, tmp_path):
        from unittest.mock import patch

        self._write(tmp_path, "app/main.py")
        self._write(tmp_path, "app/core/config.py")

        def boom(self):
            raise OSError("locked")

        with patch.object(Path, "read_bytes", boom):
            assert _collect_integrity_mismatches(tmp_path, _CRITICAL, None) == []

    def test_unregistered_file_skipped(self, tmp_path):
        digest = self._write(tmp_path, "app/main.py")
        self._write(tmp_path, "app/core/config.py")
        # 清单只登记 main.py → config.py 未登记，跳过比对不算不符
        mismatches = _collect_integrity_mismatches(tmp_path, _CRITICAL, {"app/main.py": digest})
        assert mismatches == []

    def test_hash_mismatch_detected(self, tmp_path):
        self._write(tmp_path, "app/main.py")
        self._write(tmp_path, "app/core/config.py")
        mismatches = _collect_integrity_mismatches(
            tmp_path, _CRITICAL, {"app/main.py": "deadbeef", "app/core/config.py": "deadbeef"}
        )
        assert sorted(mismatches) == ["app/core/config.py: 哈希不符", "app/main.py: 哈希不符"]

    def test_hash_match_passes(self, tmp_path):
        digest = self._write(tmp_path, "app/main.py")
        self._write(tmp_path, "app/core/config.py", b"cfg")
        cfg_digest = hashlib.sha256(b"cfg").hexdigest()
        mismatches = _collect_integrity_mismatches(
            tmp_path, _CRITICAL, {"app/main.py": digest, "app/core/config.py": cfg_digest}
        )
        assert mismatches == []


# ==================== _verify_file_integrity ====================


class TestVerifyFileIntegrity:
    def test_no_manifest_does_not_raise(self, tmp_path):
        for rel in ["app/core/config.py", "app/core/security.py", "app/core/database.py", "app/main.py"]:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
        _verify_file_integrity(tmp_path)  # 不抛即通过

    def test_manifest_mismatch_raises(self, tmp_path):
        for rel in ["app/core/config.py", "app/core/security.py", "app/core/database.py", "app/main.py"]:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
        (tmp_path / "integrity_manifest.json").write_text(
            json.dumps({"app/main.py": "deadbeef"}), encoding="utf-8"
        )
        with pytest.raises(FileIntegrityError, match="完整性校验失败"):
            _verify_file_integrity(tmp_path)

    def test_manifest_all_match_passes(self, tmp_path):
        manifest = {}
        for rel in ["app/core/config.py", "app/core/security.py", "app/core/database.py", "app/main.py"]:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            content = rel.encode()
            p.write_bytes(content)
            manifest[rel] = hashlib.sha256(content).hexdigest()
        (tmp_path / "integrity_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        _verify_file_integrity(tmp_path)

    def test_default_base_dir_resolves_repo_root(self):
        """base_dir 缺省时上溯三级定位仓库根，不抛异常（仓库内文件真实存在）。"""
        _verify_file_integrity()
