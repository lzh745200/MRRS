"""W18-offline P1-1 回归：PII 解密失败必须可观测（不再静默）。

缺陷：换机/重装后密钥漂移，decrypt_pii 解密失败只写日志就原样返回密文 ——
用户在 UI 看到 enc.v1:... 却不知所以，继续编辑保存会把密文固化成永久损坏。
修复：失败计数/首末时间累计 + 诊断包暴露 decrypt_failures。
"""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _reset_stats():
    from app.core.pii_crypto import reset_decrypt_failure_stats

    reset_decrypt_failure_stats()
    yield
    reset_decrypt_failure_stats()


@pytest.fixture
def _isolated_key(monkeypatch):
    """隔离密钥缓存：测试先加密（密钥 A），再强制换缓存密钥（密钥 B）。"""
    import app.core.pii_crypto as pc

    pc.reset_key_cache()
    yield pc
    pc.reset_key_cache()


class TestDecryptFailureObservability:
    def test_failed_decrypt_increments_counter(self, _isolated_key):
        """解密失败必须累计到 decrypt_failure_stats（不再只写日志）。"""
        from app.core import pii_crypto as pc

        ciphertext = pc.encrypt_pii("13800138000")
        assert pc.is_encrypted(ciphertext)

        # 模拟密钥漂移：清掉缓存并 patch 掉真实密钥加载，返回另一把钥匙
        pc.reset_key_cache()
        with patch.object(
            pc, "_load_key",
            side_effect=lambda: b"\\x01" * 64,
        ):
            result = pc.decrypt_pii(ciphertext)
        assert result == ciphertext             # 原样返回（不抛异常）
        stats = pc.decrypt_failure_stats()
        assert stats["count"] == 1
        assert stats["first_seen"] is not None
        assert stats["last_seen"] is not None

    def test_repeated_failure_keeps_first_seen(self, _isolated_key):
        """第二次失败不改写 first_seen（114->116 假弧：仅首次记录）。"""
        from app.core import pii_crypto as pc

        ciphertext = pc.encrypt_pii("13700137000")
        pc.reset_key_cache()
        with patch.object(pc, "_load_key", side_effect=lambda: b"\x02" * 64):
            pc.decrypt_pii(ciphertext)
            first_seen = pc.decrypt_failure_stats()["first_seen"]
            pc.decrypt_pii(ciphertext)
            stats = pc.decrypt_failure_stats()

        assert first_seen is not None
        assert stats["count"] == 2
        assert stats["first_seen"] == first_seen   # 首次时间不被后续失败覆盖
        assert stats["last_seen"] is not None

    def test_success_does_not_increment(self, _isolated_key):
        """解密成功不得计数。"""
        from app.core import pii_crypto as pc

        ct = pc.encrypt_pii("13900139000")
        assert pc.decrypt_pii(ct) == "13900139000"
        assert pc.decrypt_failure_stats()["count"] == 0

    def test_plain_value_bypasses_counter(self, _isolated_key):
        """历史明文（无标记）原样返回，不进解密路径也不计数。"""
        from app.core import pii_crypto as pc

        assert pc.decrypt_pii("13800138000") == "13800138000"
        assert pc.decrypt_failure_stats()["count"] == 0

    def test_diagnostics_exposes_decrypt_failures(self, db_session=None):
        """诊断包必须暴露 decrypt_failures（P1-1 的消费面）。"""
        import inspect

        import app.api.v1.system.diagnostics as diag

        src = inspect.getsource(diag)
        assert "decrypt_failures" in src
        assert "decrypt_failure_stats" in src
