"""TDD: AES-256-GCM 加密模块测试 — 100% 行覆盖."""
import os
import tempfile
import pytest


class TestAESGCMCipher:
    """验证 AES-256-GCM 加解密正确性 — 100% 覆盖率."""

    @pytest.fixture
    def cipher(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        return AESGCMCipher()

    @pytest.fixture
    def fixed_key_cipher(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        import secrets
        key = secrets.token_bytes(32)
        return AESGCMCipher(key=key)

    # ── __init__ ──

    def test_auto_generated_key(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        c = AESGCMCipher()
        assert len(c.key) == 32

    def test_custom_key_valid_uses_provided(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        key = b"A" * 32
        c = AESGCMCipher(key=key)
        assert c.key == key

    def test_custom_key_invalid_length_rejected(self):
        # 旧断言是「无效长度 -> 自动生成随机密钥」，即静默密钥替换：调用方以为在用自己的
        # 密钥，实际数据永远无法解密（且加解密都"成功"），属静默的数据不可恢复。
        # 按 CONTEXT.md 不变量 2（fail-closed）改为显式拒绝；未提供密钥（None）仍自动生成。
        from app.services.aes_gcm_cipher import AESGCMCipher
        with pytest.raises(ValueError, match="32 字节"):
            AESGCMCipher(key=b"short")
        with pytest.raises(ValueError, match="32 字节"):
            AESGCMCipher(key=b"")

    def test_custom_key_is_none_auto_generates(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        c = AESGCMCipher(key=None)
        assert len(c.key) == 32

    # ── key property ──

    def test_key_property(self, cipher):
        assert len(cipher.key) == 32

    # ── encrypt / decrypt roundtrip ──

    def test_encrypt_decrypt_roundtrip(self, cipher):
        plaintext = b"Hello AES-256-GCM!"
        ciphertext = cipher.encrypt(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > len(plaintext)
        decrypted = cipher.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_empty_data(self, cipher):
        ct = cipher.encrypt(b"")
        assert cipher.decrypt(ct) == b""

    def test_large_data(self, cipher):
        data = os.urandom(1024 * 1024)
        ct = cipher.encrypt(data)
        assert cipher.decrypt(ct) == data

    def test_different_encryptions_produce_different_outputs(self, cipher):
        ct1 = cipher.encrypt(b"test data")
        ct2 = cipher.encrypt(b"test data")
        assert ct1 != ct2

    # ── decrypt edge cases ──

    def test_decrypt_short_ciphertext_raises(self, cipher):
        with pytest.raises(ValueError, match="密文太短"):
            cipher.decrypt(b"too short")

    def test_tampered_data_rejected(self, fixed_key_cipher):
        ct = fixed_key_cipher.encrypt(b"important data")
        tampered = bytearray(ct)
        tampered[len(tampered) // 2] ^= 0xFF
        with pytest.raises(ValueError, match="解密|密钥|篡改|损坏"):
            fixed_key_cipher.decrypt(bytes(tampered))

    def test_wrong_key_cannot_decrypt(self):
        from app.services.aes_gcm_cipher import AESGCMCipher
        import secrets
        c1 = AESGCMCipher(key=secrets.token_bytes(32))
        c2 = AESGCMCipher(key=secrets.token_bytes(32))
        ct = c1.encrypt(b"secret")
        with pytest.raises(ValueError, match="解密|密钥|篡改|损坏"):
            c2.decrypt(ct)

    # ── encrypt_string / decrypt_string ──

    def test_encrypt_string_roundtrip(self, cipher):
        text = "帮扶管理信息系统测试数据"
        encrypted = cipher.encrypt_string(text)
        decrypted = cipher.decrypt_string(encrypted)
        assert decrypted == text

    # ── generate_key ──

    def test_generate_key_is_random(self, cipher):
        key1 = cipher.generate_key()
        key2 = cipher.generate_key()
        assert key1 != key2
        assert len(key1) == 32

    # ── encrypt_file / decrypt_file ──

    def test_encrypt_file_decrypt_file_roundtrip(self, cipher):
        original = b"file content for encryption test"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(original)
            input_path = f.name
        output_enc = input_path + ".enc"
        output_dec = input_path + ".dec"
        try:
            cipher.encrypt_file(input_path, output_enc)
            assert os.path.exists(output_enc)
            with open(output_enc, "rb") as f:
                encrypted_data = f.read()
            assert encrypted_data != original
            assert len(encrypted_data) > len(original)
            cipher.decrypt_file(output_enc, output_dec)
            assert os.path.exists(output_dec)
            with open(output_dec, "rb") as f:
                result = f.read()
            assert result == original
        finally:
            for p in [input_path, output_enc, output_dec]:
                if os.path.exists(p):
                    os.remove(p)

    def test_decrypt_file_tampered_raises(self, cipher):
        original = b"sensitive data"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(original)
            input_path = f.name
        output_enc = input_path + ".enc"
        try:
            cipher.encrypt_file(input_path, output_enc)
            with open(output_enc, "rb+") as f:
                data = bytearray(f.read())
                data[len(data) // 2] ^= 0xFF
                f.seek(0)
                f.write(data)
            output_dec = input_path + ".dec"
            with pytest.raises(ValueError, match="解密|密钥|篡改|损坏"):
                cipher.decrypt_file(output_enc, output_dec)
        finally:
            for p in [input_path, output_enc]:
                if os.path.exists(p):
                    os.remove(p)
