"""R34-2（P1-2）：PII 密钥管理端点。

覆盖 GET /system/pii-key、/export、POST /import 的权限、来源分支与错误路径。
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.system import pii_key as api

ADMIN = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
VIEWER = SimpleNamespace(id=2, username="u", role="viewer", is_superuser=False)


@pytest.fixture
def env_mode(monkeypatch):
    """显式配置 ENCRYPTION_KEY（来源 = env）。"""
    monkeypatch.setattr(api, "settings",
                        SimpleNamespace(ENCRYPTION_KEY="e" * 40))
    monkeypatch.setattr(api, "_audit", lambda *a, **kw: None)
    monkeypatch.setattr(api, "_fingerprint", lambda: "fp-env")


@pytest.fixture
def runtime_mode(monkeypatch):
    """未配置 ENCRYPTION_KEY（来源 = runtime）。"""
    monkeypatch.setattr(api, "settings", SimpleNamespace(ENCRYPTION_KEY=""))
    monkeypatch.setattr(api, "_audit", lambda *a, **kw: None)
    monkeypatch.setattr(api, "_fingerprint", lambda: "fp-runtime")


class TestSource:
    def test_env_when_explicitly_configured(self, env_mode):
        assert api._source() == api.SOURCE_ENV

    def test_runtime_when_not_configured(self, runtime_mode):
        assert api._source() == api.SOURCE_RUNTIME


class TestFingerprintReal:
    def test_delegates_to_pii_crypto(self, monkeypatch):
        """真实实现：转发 core/pii_crypto.key_fingerprint。"""
        from app.core import pii_crypto

        monkeypatch.setattr(pii_crypto, "key_fingerprint", lambda: "deadbeefdeadbeef")
        assert api._fingerprint() == "deadbeefdeadbeef"


class TestAuditReal:
    def test_writes_work_log_metadata_only(self, monkeypatch):
        """真实实现：写审计日志，且只记元数据（不含密钥本体）。"""
        calls = []
        monkeypatch.setattr(api, "write_work_log",
                            lambda *a, **kw: calls.append((a, kw)))
        api._audit(None, ADMIN, "pii_key_export", "导出 PII 密钥（指纹 abc）")
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert (args[1], args[2]) == ("system_config", "pii_key_export")
        assert kwargs["username"] == "admin"
        assert kwargs["user_id"] == 1


class TestCurrentSecret:
    def test_env_returns_config_value(self, env_mode):
        assert api._current_secret() == "e" * 40

    def test_runtime_reads_store(self, runtime_mode, monkeypatch):
        from app.utils import runtime_secrets

        monkeypatch.setattr(runtime_secrets, "get_or_create_secret",
                            lambda *a, **kw: "runtime-secret-value" * 3)
        assert api._current_secret().startswith("runtime-secret-value")


class TestStatus:
    def test_ok(self, env_mode):
        data = api.get_pii_key_status(current_user=ADMIN)["data"]
        assert data == {"fingerprint": "fp-env", "source": "env", "available": True}

    def test_non_admin_denied(self, env_mode):
        with pytest.raises(HTTPException) as exc:
            api.get_pii_key_status(current_user=VIEWER)
        assert exc.value.status_code == 403


class TestExport:
    def test_ok_and_audited(self, env_mode, monkeypatch):
        calls = []
        monkeypatch.setattr(api, "_audit", lambda *a, **kw: calls.append((a, kw)))
        resp = api.export_pii_key(db=None, current_user=ADMIN)
        assert resp["data"]["key"] == "e" * 40
        assert resp["data"]["fingerprint"] == "fp-env"
        assert len(calls) == 1 and calls[0][0][2] == "pii_key_export"
        # 审计不得记录密钥本体
        assert "e" * 40 not in str(calls[0])

    def test_read_failure_returns_500(self, runtime_mode, monkeypatch):
        from app.utils import runtime_secrets

        def _boom(*a, **kw):
            raise RuntimeError("disk full")

        monkeypatch.setattr(runtime_secrets, "get_or_create_secret", _boom)
        with pytest.raises(HTTPException) as exc:
            api.export_pii_key(db=None, current_user=ADMIN)
        assert exc.value.status_code == 500

    def test_non_admin_denied(self, env_mode):
        with pytest.raises(HTTPException) as exc:
            api.export_pii_key(db=None, current_user=VIEWER)
        assert exc.value.status_code == 403


class TestImport:
    def test_ok_writes_store_and_resets_cache(self, runtime_mode, monkeypatch):
        from app.utils import runtime_secrets
        from app.core import pii_crypto

        written = {}
        monkeypatch.setattr(runtime_secrets, "set_secret",
                            lambda k, v: written.update({k: v}))
        reset_calls = []
        monkeypatch.setattr(pii_crypto, "reset_key_cache", lambda: reset_calls.append("cache"))
        monkeypatch.setattr(pii_crypto, "reset_decrypt_failure_stats",
                            lambda: reset_calls.append("stats"))

        resp = api.import_pii_key(
            api.PiiKeyImportRequest(key="k" * 40), db=None, current_user=ADMIN
        )
        assert written == {"PII_AESSIV_KEY": "k" * 40}
        assert reset_calls == ["cache", "stats"]
        assert resp["data"]["fingerprint"] == "fp-runtime"

    def test_short_key_rejected(self, runtime_mode):
        with pytest.raises(HTTPException) as exc:
            api.import_pii_key(api.PiiKeyImportRequest(key="short"), db=None,
                               current_user=ADMIN)
        assert exc.value.status_code == 400
        assert "长度不足" in exc.value.detail

    def test_env_configured_rejects_import(self, env_mode):
        """环境变量优先时导入无效，必须明确拒绝而非静默接受。"""
        with pytest.raises(HTTPException) as exc:
            api.import_pii_key(api.PiiKeyImportRequest(key="k" * 40), db=None,
                               current_user=ADMIN)
        assert exc.value.status_code == 400
        assert "ENCRYPTION_KEY" in exc.value.detail

    def test_write_failure_returns_500(self, runtime_mode, monkeypatch):
        from app.utils import runtime_secrets

        def _boom(k, v):
            raise RuntimeError("read-only fs")

        monkeypatch.setattr(runtime_secrets, "set_secret", _boom)
        with pytest.raises(HTTPException) as exc:
            api.import_pii_key(api.PiiKeyImportRequest(key="k" * 40), db=None,
                               current_user=ADMIN)
        assert exc.value.status_code == 500

    def test_non_admin_denied(self, runtime_mode):
        with pytest.raises(HTTPException) as exc:
            api.import_pii_key(api.PiiKeyImportRequest(key="k" * 40), db=None,
                               current_user=VIEWER)
        assert exc.value.status_code == 403
