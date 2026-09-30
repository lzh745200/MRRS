"""app.utils.encryption 覆盖率攻坚测试

DataPackageEncryption 三种初始化、盐值加载三分支、密码派生、
数据/文件加解密回环、密钥串往返、校验和计算与验证全分支。
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

import app.utils.encryption as enc
from app.utils.encryption import (
    DataPackageEncryption,
    calculate_file_checksum,
    generate_encryption_key,
    verify_file_checksum,
)


# ==================== 初始化与盐值 ====================


class TestInit:
    def test_init_with_key(self):
        key = Fernet.generate_key()
        e = DataPackageEncryption(key=key)
        assert e.key == key

    def test_init_with_password(self):
        e = DataPackageEncryption(password="secret-pwd")
        assert e.cipher is not None

    def test_init_generates_key(self):
        e = DataPackageEncryption()
        assert isinstance(e.key, bytes)

    def test_key_precedence_over_password(self):
        key = Fernet.generate_key()
        e = DataPackageEncryption(password="pwd", key=key)
        assert e.key == key


class TestDeploymentSalt:
    def setup_method(self):
        DataPackageEncryption._deployment_salt = None

    def teardown_method(self):
        DataPackageEncryption._deployment_salt = None

    def test_load_success_and_cached(self):
        salt_hex = os.urandom(32).hex()
        with patch(
            "app.utils.runtime_secrets.get_or_create_secret", return_value=salt_hex
        ) as m:
            salt1 = DataPackageEncryption._load_deployment_salt()
            salt2 = DataPackageEncryption._load_deployment_salt()
        assert salt1 == bytes.fromhex(salt_hex)
        assert salt2 is salt1  # 缓存命中不再调用
        m.assert_called_once()

    def test_load_failure_fails_closed(self):
        """盐值不可持久化时必须直接失败，绝不用进程内随机盐顶替（深审 #85）。

        旧行为是 warning + 随机盐：本次运行写入的密文重启后永久不可解，
        且只有解密时才暴露。
        """
        with patch(
            "app.utils.runtime_secrets.get_or_create_secret", side_effect=Exception("io err")
        ):
            with pytest.raises(RuntimeError, match="部署盐值初始化失败"):
                DataPackageEncryption._load_deployment_salt()


# ==================== 派生与加解密 ====================


class TestDeriveAndCipher:
    def test_derive_deterministic_with_explicit_salt(self):
        e = DataPackageEncryption()
        k1 = e._derive_key_from_password("pwd", salt=b"0" * 32)
        k2 = e._derive_key_from_password("pwd", salt=b"0" * 32)
        assert k1 == k2
        # 是合法 Fernet key
        Fernet(k1)

    def test_derive_uses_deployment_salt(self):
        with patch.object(
            DataPackageEncryption, "_load_deployment_salt", return_value=b"1" * 32
        ):
            e = DataPackageEncryption()
            derived = e._derive_key_from_password("pwd")
        expected = e._derive_key_from_password("pwd", salt=b"1" * 32)
        assert derived == expected

    def test_encrypt_decrypt_roundtrip(self):
        e = DataPackageEncryption()
        data = b"sensitive data \xe4\xb8\xad\xe6\x96\x87"
        assert e.decrypt_data(e.encrypt_data(data)) == data

    def test_file_roundtrip_default_output(self, tmp_path):
        src = tmp_path / "plain.bin"
        src.write_bytes(b"file-content-123")
        e = DataPackageEncryption()
        enc_path = e.encrypt_file(str(src))
        assert enc_path.endswith(".enc")
        assert os.path.exists(enc_path)

        out = tmp_path / "restored.bin"
        e.decrypt_file(enc_path, str(out))
        assert out.read_bytes() == b"file-content-123"

    def test_file_encrypt_explicit_output(self, tmp_path):
        src = tmp_path / "a.bin"
        src.write_bytes(b"x")
        out = tmp_path / "b.enc"
        e = DataPackageEncryption()
        assert e.encrypt_file(str(src), str(out)) == str(out)
        assert out.exists()


# ==================== 密钥串往返 ====================


class TestKeyString:
    def test_roundtrip(self):
        e1 = DataPackageEncryption()
        key_str = e1.get_key_string()
        e2 = DataPackageEncryption.from_key_string(key_str)
        data = b"roundtrip"
        assert e2.decrypt_data(e1.encrypt_data(data)) == data


# ==================== 校验和 ====================


class TestChecksum:
    def test_sha256(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        result = calculate_file_checksum(str(f), "sha256")
        assert result.startswith("sha256:")

    def test_sha1(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        assert calculate_file_checksum(str(f), "sha1").startswith("sha1:")

    def test_md5(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        assert calculate_file_checksum(str(f), "md5").startswith("md5:")

    def test_unsupported_algorithm(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        with pytest.raises(ValueError, match="不支持的算法"):
            calculate_file_checksum(str(f), "blake2")

    def test_verify_match(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        checksum = calculate_file_checksum(str(f), "sha256")
        assert verify_file_checksum(str(f), checksum) is True

    def test_verify_mismatch(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        assert verify_file_checksum(str(f), "sha256:" + "0" * 64) is False

    def test_verify_bad_format(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        assert verify_file_checksum(str(f), "no-colon-here") is False

    def test_verify_missing_file(self):
        assert verify_file_checksum("/nonexistent/file.bin", "sha256:abc") is False

    def test_verify_unexpected_error(self, tmp_path):
        f = tmp_path / "f.bin"
        f.write_bytes(b"abc")
        with patch.object(enc, "calculate_file_checksum", side_effect=RuntimeError("x")):
            assert verify_file_checksum(str(f), "sha256:abc") is False


# ==================== generate_encryption_key ====================


class TestGenerateKey:
    def test_valid_fernet_key(self):
        key_str = generate_encryption_key()
        assert isinstance(key_str, str)
        Fernet(key_str.encode())  # 不抛异常即合法
