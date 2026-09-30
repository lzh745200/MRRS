"""app.utils.runtime_secrets 缺口补口（.coveragerc fail_under=100）。

缺失行：
- 132：require_persisted=True 且密钥文件存在却读不出来（JSON 损坏 / 无读取权限）
  → 必须 raise RuntimeError。若就此重新生成，会把既有密钥覆盖掉，历史密文永久
  不可解（深审 critical）；
- 145：require_persisted=True 且落盘失败 → 必须 raise RuntimeError，绝不用
  "进程内一次性密钥"顶替。
默认 require_persisted=False 的 fail-soft 语义保持（对照组）。
"""

import builtins
import json
import os
from unittest.mock import patch

import pytest

from app.utils.runtime_secrets import ensure_runtime_secrets, get_or_create_secret


def _selective_open(target_path, exc):
    """只对 target_path 抛 exc，其余委托真实 open（不全局破坏 pytest 内部 IO）。"""
    real_open = builtins.open
    target = str(target_path)

    def _open(file, *args, **kwargs):
        if str(file) == target:
            raise exc
        return real_open(file, *args, **kwargs)

    return _open


class TestRequirePersistedReadFailure:
    def test_corrupt_json_raises_and_leaves_file_untouched(self, tmp_path):
        """132 行：文件存在但 JSON 损坏 → RuntimeError（不得覆盖既有密钥）。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text("{bad json", encoding="utf-8")

        with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
            with pytest.raises(RuntimeError) as exc:
                get_or_create_secret("ENCRYPTION_FERNET_KEY", require_persisted=True)

        assert "无法读取运行时密钥文件" in str(exc.value)
        assert str(secrets_file) in str(exc.value)
        assert isinstance(exc.value.__cause__, json.JSONDecodeError)
        assert secrets_file.read_text(encoding="utf-8") == "{bad json"

    def test_permission_error_raises(self, tmp_path):
        """132 行：文件无读取权限 → RuntimeError。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text(json.dumps({"K": "v"}), encoding="utf-8")

        with patch("builtins.open", _selective_open(secrets_file, PermissionError("denied"))):
            with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
                with pytest.raises(RuntimeError, match="无法读取运行时密钥文件"):
                    get_or_create_secret("K", require_persisted=True)

        assert secrets_file.read_text(encoding="utf-8") == json.dumps({"K": "v"})

    def test_read_failure_without_require_persisted_still_regenerates(self, tmp_path):
        """对照组：默认 require_persisted=False 时读失败仍降级生成（既有语义）。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text("{bad json", encoding="utf-8")

        with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
            value = get_or_create_secret("SOFT_KEY")

        assert value


class TestEnsureRuntimeSecretsWeakKeys:
    """弱密钥（非空但 < 32 字符）必须被忽略并重新生成，不得注入环境变量。"""

    def test_short_csrf_key_is_regenerated(self, tmp_path):
        secrets_file = tmp_path / "runtime_secrets.json"
        env = {
            "SECRET_KEY": "s" * 40,
            "CSRF_SECRET_KEY": "short",
            "RUNTIME_SECRETS_FILE": str(secrets_file),
        }
        with patch.dict(os.environ, env):
            ensure_runtime_secrets()
            assert os.environ["CSRF_SECRET_KEY"] != "short"
            assert len(os.environ["CSRF_SECRET_KEY"]) >= 32
            assert os.environ["SECRET_KEY"] == "s" * 40   # 足够强的密钥保持不变
            assert json.loads(secrets_file.read_text(encoding="utf-8"))["CSRF_SECRET_KEY"]

    def test_short_secret_key_is_regenerated(self, tmp_path):
        secrets_file = tmp_path / "runtime_secrets.json"
        env = {
            "SECRET_KEY": "tiny",
            "CSRF_SECRET_KEY": "c" * 40,
            "RUNTIME_SECRETS_FILE": str(secrets_file),
        }
        with patch.dict(os.environ, env):
            ensure_runtime_secrets()
            assert os.environ["SECRET_KEY"] != "tiny"
            assert len(os.environ["SECRET_KEY"]) >= 32


class TestRequirePersistedWriteFailure:
    def test_write_failure_raises(self, tmp_path):
        """145 行：落盘失败 → RuntimeError（加密静态数据的密钥绝不用进程内值顶替）。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text("{}", encoding="utf-8")

        with patch(
            "app.utils.runtime_secrets._atomic_write_json",
            side_effect=OSError("disk full"),
        ):
            with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
                with pytest.raises(RuntimeError) as exc:
                    get_or_create_secret("ENCRYPTION_FERNET_KEY", require_persisted=True)

        assert "无法持久化密钥" in str(exc.value)
        assert "ENCRYPTION_FERNET_KEY" in str(exc.value)
        assert isinstance(exc.value.__cause__, OSError)
        assert secrets_file.read_text(encoding="utf-8") == "{}"   # 无半成品写入

    def test_write_failure_without_require_persisted_returns_in_process_value(self, tmp_path):
        """对照组：默认 fail-soft —— 仍返回进程内值（既有调用方语义不变）。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text("{}", encoding="utf-8")

        with patch(
            "app.utils.runtime_secrets._atomic_write_json",
            side_effect=OSError("disk full"),
        ):
            with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
                value = get_or_create_secret("SOFT_KEY")

        assert value
        assert secrets_file.read_text(encoding="utf-8") == "{}"

    def test_existing_key_needs_no_write(self, tmp_path):
        """对照组：密钥已存在 → 直接返回，不触发落盘（require_persisted 亦不抛）。"""
        secrets_file = tmp_path / "runtime_secrets.json"
        secrets_file.write_text(json.dumps({"K": "existing"}), encoding="utf-8")

        with patch("app.utils.runtime_secrets._atomic_write_json") as mock_write:
            with patch.dict(os.environ, {"RUNTIME_SECRETS_FILE": str(secrets_file)}):
                assert get_or_create_secret("K", require_persisted=True) == "existing"

        mock_write.assert_not_called()
