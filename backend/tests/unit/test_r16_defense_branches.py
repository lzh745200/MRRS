"""R16 深审新增防御分支的回归锁定。

覆盖三处本轮新增/加固的分支（此前覆盖率未达 100 的缺口行）：
- app/utils/encryption.py:61 —— 部署盐值持久化失败必须 fail-closed（拒绝进程内临时盐）
- app/utils/input_validator.py:84 —— 非字符串输入先 str() 归一
- app/utils/package_crypto.py:95 —— 权限包迭代次数越界拒绝
"""

import struct

import pytest
from fastapi import HTTPException

from app.utils import package_crypto


# ==================== encryption.py: 部署盐值 fail-closed ====================


class TestDeploymentSaltFailClosed:
    def _reset_cache(self):
        from app.utils.encryption import DataPackageEncryption

        DataPackageEncryption._deployment_salt = None

    def test_unpersistable_salt_raises_and_does_not_cache(self, monkeypatch):
        """require_persisted 失败（文件不可写/损坏）→ 抛错，且不缓存临时盐值。

        历史缺陷：落盘失败时静默回退进程内随机盐，重启后历史密文永久不可解。
        """
        import app.utils.runtime_secrets as rs
        from app.utils.encryption import DataPackageEncryption

        self._reset_cache()
        monkeypatch.setattr(
            rs, "get_or_create_secret",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("无法持久化密钥")),
        )
        try:
            with pytest.raises(RuntimeError, match="部署盐值初始化失败"):
                DataPackageEncryption._load_deployment_salt()
            assert DataPackageEncryption._deployment_salt is None
        finally:
            self._reset_cache()

    def test_successful_salt_is_cached(self, monkeypatch):
        """成功路径：盐值缓存，二次调用不再读取密钥文件。"""
        import app.utils.runtime_secrets as rs
        from app.utils.encryption import DataPackageEncryption

        self._reset_cache()
        calls = []

        def _fake(key, **kw):
            calls.append(key)
            return "ab" * 32

        monkeypatch.setattr(rs, "get_or_create_secret", _fake)
        try:
            first = DataPackageEncryption._load_deployment_salt()
            second = DataPackageEncryption._load_deployment_salt()
            assert first == second == bytes.fromhex("ab" * 32)
            assert len(calls) == 1
        finally:
            self._reset_cache()


# ==================== input_validator.py: 非字符串归一 ====================


class TestInputValidatorNonStringCoercion:
    def test_non_string_converted_via_str(self):
        """非 str 输入（int/None/list）先 str() 归一，不抛 TypeError。"""
        from app.utils.input_validator import InputValidator

        assert InputValidator.validate_sql_safe(123) == "123"
        assert InputValidator.validate_sql_safe(None) == "None"
        assert InputValidator.validate_sql_safe(["a", "b"]) == "['a', 'b']"

    def test_overlong_input_rejected(self):
        from app.utils.input_validator import InputValidator

        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_sql_safe("x" * (InputValidator.MAX_SQL_CHECK_LENGTH + 1))
        assert exc.value.status_code == 400
        assert "输入过长" in exc.value.detail

    @pytest.mark.parametrize(
        "payload",
        [
            "1' OR '1'='1' OR '1'='1",       # 双 or
            "1 UNION SELECT password FROM users",
            "1; DROP TABLE users",
            "admin' --",
            "1 AND 1=1 AND 2=2",             # 双 and
        ],
    )
    def test_sql_injection_pattern_rejected(self, payload):
        from app.utils.input_validator import InputValidator

        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_sql_safe(payload)
        assert exc.value.status_code == 400
        assert "SQL注入" in exc.value.detail

    def test_benign_input_passes_through(self):
        from app.utils.input_validator import InputValidator

        assert InputValidator.validate_sql_safe("张三") == "张三"
        assert InputValidator.validate_sql_safe("village-001") == "village-001"


# ==================== package_crypto.py: 迭代次数边界 ====================


class TestPackageCryptoIterationBounds:
    def _header(self, iterations: int, salt: bytes = b"S" * package_crypto._SALT_LEN) -> bytes:
        body = package_crypto._MAGIC + struct.pack(">I", iterations) + salt
        pad = package_crypto._HEADER_LEN - len(body)
        return body + b"\x00" * pad + b"cipher"

    def test_iterations_below_min_rejected(self):
        with pytest.raises(package_crypto.InvalidToken, match="迭代次数超出允许范围"):
            package_crypto._parse_header(self._header(package_crypto._MIN_ITERATIONS - 1))

    def test_iterations_above_max_rejected(self):
        with pytest.raises(package_crypto.InvalidToken, match="迭代次数超出允许范围"):
            package_crypto._parse_header(self._header(package_crypto._MAX_ITERATIONS + 1))

    def test_truncated_header_rejected(self):
        with pytest.raises(package_crypto.InvalidToken, match="包头被截断"):
            package_crypto._parse_header(b"XX")

    def test_valid_iterations_parsed(self):
        iterations, salt, cipher = package_crypto._parse_header(
            self._header(package_crypto._MIN_ITERATIONS)
        )
        assert iterations == package_crypto._MIN_ITERATIONS
        assert len(salt) == package_crypto._SALT_LEN
        assert cipher == b"cipher"
