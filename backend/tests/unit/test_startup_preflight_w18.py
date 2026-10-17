"""W18 P2-3 回归：启动预检（磁盘/可写性/时钟/加密密钥）。

这些检查把"运行时才莫名报错"提前到启动时说清楚，且只报警不阻断启动。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.startup import preflight


def _patch_disk(monkeypatch, free_bytes):
    monkeypatch.setattr(
        preflight.shutil, "disk_usage",
        lambda _p: SimpleNamespace(total=10 ** 12, used=0, free=free_bytes),
    )


class TestDiskFree:
    def test_ok(self, monkeypatch):
        _patch_disk(monkeypatch, 5 * 1024 ** 3)
        assert preflight._check_disk_free()["status"] == "ok"

    def test_warning_when_low(self, monkeypatch):
        _patch_disk(monkeypatch, 100 * 1024 ** 2)  # 100MB < 1024MB
        result = preflight._check_disk_free()
        assert result["status"] == "warning"
        assert result["threshold_mb"] == preflight.DISK_FREE_WARN_MB

    def test_exception_is_unknown(self, monkeypatch):
        def _boom(_p):
            raise OSError("no volume")

        monkeypatch.setattr(preflight.shutil, "disk_usage", _boom)
        assert preflight._check_disk_free()["status"] == "unknown"


class TestDbWritable:
    def test_ok(self, monkeypatch, tmp_path):
        db = tmp_path / "app.db"
        db.write_bytes(b"x")
        monkeypatch.setattr("app.utils.paths.get_database_path", lambda: db)
        result = preflight._check_db_writable()
        assert result["status"] == "ok"
        assert result["writable"] is True

    def test_missing_db(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.utils.paths.get_database_path", lambda: tmp_path / "absent.db")
        result = preflight._check_db_writable()
        assert result["status"] == "unknown"
        assert result["exists"] is False

    def test_not_writable_warns(self, monkeypatch, tmp_path):
        db = tmp_path / "app.db"
        db.write_bytes(b"x")
        monkeypatch.setattr("app.utils.paths.get_database_path", lambda: db)
        monkeypatch.setattr(preflight.os, "access", lambda *a, **k: False)
        assert preflight._check_db_writable()["status"] == "warning"

    def test_exception_is_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "app.utils.paths.get_database_path",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert preflight._check_db_writable()["status"] == "unknown"


class TestClockDrift:
    def test_no_data_is_ok(self, monkeypatch):
        monkeypatch.setattr(preflight, "_latest_audit_time", lambda: None)
        assert preflight._check_clock_drift()["status"] == "ok"

    def test_system_clock_behind_warns(self, monkeypatch):
        future = datetime.now(timezone.utc) + timedelta(days=5)
        monkeypatch.setattr(preflight, "_latest_audit_time", lambda: future)
        result = preflight._check_clock_drift()
        assert result["status"] == "warning"
        assert result["reason"] == "system_clock_behind_data"

    def test_naive_timestamp_normalized(self, monkeypatch):
        recent = datetime.now(timezone.utc).replace(tzinfo=None)
        monkeypatch.setattr(preflight, "_latest_audit_time", lambda: recent)
        assert preflight._check_clock_drift()["status"] == "ok"

    def test_exception_is_unknown(self, monkeypatch):
        monkeypatch.setattr(
            preflight, "_latest_audit_time",
            lambda: (_ for _ in ()).throw(RuntimeError("db gone")),
        )
        assert preflight._check_clock_drift()["status"] == "unknown"


class TestEncryptionKey:
    def test_ok(self, monkeypatch):
        monkeypatch.setattr(preflight, "_sample_existing_ciphertext", lambda: None)
        assert preflight._check_encryption_key()["status"] == "ok"

    def test_token_none_is_unknown(self, monkeypatch):
        monkeypatch.setattr("app.core.pii_crypto.encrypt_pii", lambda _v: None)
        assert preflight._check_encryption_key()["status"] == "unknown"

    def test_mismatch_warns(self, monkeypatch):
        monkeypatch.setattr("app.core.pii_crypto.encrypt_pii", lambda _v: "cipher")
        monkeypatch.setattr("app.core.pii_crypto.decrypt_pii", lambda _v: "other")
        assert preflight._check_encryption_key()["status"] == "warning"

    def test_exception_warns(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.pii_crypto.encrypt_pii",
            lambda _v: (_ for _ in ()).throw(RuntimeError("key missing")),
        )
        result = preflight._check_encryption_key()
        assert result["status"] == "warning"
        assert result["error_type"] == "RuntimeError"


class TestExistingCiphertextProbe:
    """W18-B：自证式探针不能发现「密钥换了、存量密文解不开」。"""

    def test_no_existing_ciphertext_is_ok(self, monkeypatch):
        monkeypatch.setattr(preflight, "_sample_existing_ciphertext", lambda: None)
        result = preflight._check_encryption_key()
        assert result["status"] == "ok"
        assert result["existing_ciphertext"] is False

    def test_existing_ciphertext_decryptable_is_ok(self, monkeypatch):
        monkeypatch.setattr(preflight, "_sample_existing_ciphertext", lambda: "enc.v1:stale")
        monkeypatch.setattr("app.core.pii_crypto.encrypt_pii", lambda _v: "enc.v1:probe")
        monkeypatch.setattr(
            "app.core.pii_crypto.decrypt_pii",
            lambda v: "preflight-probe" if v == "enc.v1:probe" else "13800000000",
        )
        result = preflight._check_encryption_key()
        assert result["status"] == "ok"
        assert result["existing_ciphertext"] is True

    def test_existing_ciphertext_undecryptable_warns(self, monkeypatch):
        monkeypatch.setattr(preflight, "_sample_existing_ciphertext", lambda: "enc.v1:stale")
        monkeypatch.setattr("app.core.pii_crypto.encrypt_pii", lambda _v: "enc.v1:probe")
        # decrypt_pii 解密失败时的真实行为：原样返回密文，不抛异常
        monkeypatch.setattr(
            "app.core.pii_crypto.decrypt_pii",
            lambda v: "preflight-probe" if v == "enc.v1:probe" else v,
        )
        result = preflight._check_encryption_key()
        assert result["status"] == "warning"
        assert result["reason"] == "existing_ciphertext_undecryptable"

    def test_sampler_returns_row(self):
        """真实走 SessionLocal + 裸 SQL（覆盖取到行与关闭会话分支）。"""
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = ("enc.v1:abc",)
        with patch("app.core.database.SessionLocal", return_value=session):
            assert preflight._sample_existing_ciphertext() == "enc.v1:abc"
        session.close.assert_called_once()

    def test_sampler_returns_none_without_rows(self):
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        with patch("app.core.database.SessionLocal", return_value=session):
            assert preflight._sample_existing_ciphertext() is None

    def test_sampler_swallows_db_errors(self):
        with patch("app.core.database.SessionLocal", side_effect=RuntimeError("no db")):
            assert preflight._sample_existing_ciphertext() is None


class TestRunPreflightChecks:
    def test_aggregates_all_checks(self, monkeypatch):
        monkeypatch.setattr(preflight, "_check_disk_free", lambda: {"status": "ok"})
        monkeypatch.setattr(preflight, "_check_db_writable", lambda: {"status": "ok"})
        monkeypatch.setattr(preflight, "_check_clock_drift", lambda: {"status": "ok"})
        monkeypatch.setattr(preflight, "_check_encryption_key", lambda: {"status": "ok"})
        results = preflight.run_preflight_checks()
        assert set(results) == {"disk", "database_writable", "clock", "encryption_key"}

    def test_warning_is_logged(self, monkeypatch, caplog):
        import logging

        monkeypatch.setattr(preflight, "_check_disk_free", lambda: {"status": "warning", "free_mb": 1})
        monkeypatch.setattr(preflight, "_check_db_writable", lambda: {"status": "ok"})
        monkeypatch.setattr(preflight, "_check_clock_drift", lambda: {"status": "ok"})
        monkeypatch.setattr(preflight, "_check_encryption_key", lambda: {"status": "ok"})
        with caplog.at_level(logging.WARNING, logger="app.startup.preflight"):
            preflight.run_preflight_checks()
        assert any("启动预检告警 [disk]" in r.getMessage() for r in caplog.records)

    def test_latest_audit_time_queries_db(self):
        """真实走 SessionLocal 查询链（覆盖 finally 关闭分支）。"""
        session = MagicMock()
        session.query.return_value.order_by.return_value.limit.return_value.scalar.return_value = None
        with patch("app.core.database.SessionLocal", return_value=session):
            assert preflight._latest_audit_time() is None
        session.close.assert_called_once()
