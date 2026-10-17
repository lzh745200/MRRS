# -*- coding: utf-8 -*-
"""诊断包导出（P0-7）的回归测试 —— `app/api/v1/system/diagnostics.py`。

锁定三件事：

1. **脱敏**：手机号 / 身份证号 / 口令类键值对出站前打码（诊断包要外发，
   日志里出现过 SQL 原文与用户输入）；
2. **降级**：路径解析失败、构建信息缺失、日志缺失/不可读、psutil 失败、
   审计写入失败 —— 任何一环坏掉都只能降级，不能拖垮整份诊断；
3. **权限**：两个端点都是管理员专属（403），导出动作写审计。
"""

import hashlib
import io
import json
import sys
import types
import zipfile
from unittest.mock import Mock

import pytest

from app.api.v1.system import diagnostics as diag

# ==================== 脱敏 ====================


class TestRedaction:
    def test_phone_number_masked(self):
        assert diag.redact_text("联系电话 13812345678") == "联系电话 138********"
        assert diag.redact_text("另一个 19900001111") == "另一个 199********"

    def test_short_number_not_masked(self):
        # 10 位/12 位不构成手机号，不得误伤（诊断里有大量 id/行号）
        assert diag.redact_text("id=1234567890") == "id=1234567890"

    def test_id_card_masked(self):
        assert diag.redact_text("身份证 11010119900307123X") == "身份证 ******************"

    def test_secret_key_values_masked(self):
        assert "abc" not in diag.redact_text("password=abc")
        assert diag.redact_text("password=abc") == "password=***"
        assert diag.redact_text('"token": "xyz"') == '"token": "***"'
        assert diag.redact_text("Authorization: Bearer abc.def") == "Authorization: ***"

    def test_plain_text_untouched(self):
        text = "SELECT COUNT(*) FROM users WHERE is_active = 1"
        assert diag.redact_text(text) == text


# ==================== 基础工具 ====================


class TestHelpers:
    def test_safe_size_none_and_missing(self, tmp_path):
        assert diag._safe_size(None) is None
        assert diag._safe_size(tmp_path / "nope.bin") is None

    def test_safe_size_existing(self, tmp_path):
        target = tmp_path / "a.bin"
        target.write_bytes(b"12345")
        assert diag._safe_size(target) == 5

    def test_resolve_log_prefers_settings(self, tmp_path, monkeypatch):
        log = tmp_path / "app.log"
        log.write_text("x\n", encoding="utf-8")
        monkeypatch.setattr(diag.settings, "LOG_FILE", str(log))
        assert diag._resolve_log_file() == log

    def test_resolve_log_falls_back_to_runtime_dir(self, tmp_path, monkeypatch):
        fallback = tmp_path / "runtime-app.log"
        fallback.write_text("x\n", encoding="utf-8")
        monkeypatch.setattr(diag.settings, "LOG_FILE", str(tmp_path / "missing.log"))
        monkeypatch.setattr(diag.paths, "get_log_path", lambda sub="": fallback)
        assert diag._resolve_log_file() == fallback

    def test_resolve_log_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(diag.settings, "LOG_FILE", str(tmp_path / "missing.log"))
        monkeypatch.setattr(diag.paths, "get_log_path", lambda sub="": tmp_path / "nope.log")
        assert diag._resolve_log_file() is None

    def test_tail_lines_limits(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("".join("line-%d\n" % i for i in range(10)), encoding="utf-8")
        assert diag._tail_lines(log, 3) == ["line-7\n", "line-8\n", "line-9\n"]
        assert len(diag._tail_lines(log, 100)) == 10

    def test_runtime_db_path_failure_degrades(self, monkeypatch):
        def boom():
            raise RuntimeError("no path")

        monkeypatch.setattr(diag.paths, "get_database_path", boom)
        assert diag._runtime_db_path() is None

    def test_build_snapshot_failure_degrades(self, monkeypatch):
        import app.core.build_info as build_info

        def boom():
            raise RuntimeError("no build info")

        monkeypatch.setattr(build_info, "get_build_info", boom)
        assert diag._build_snapshot() == {"error_type": "RuntimeError"}

    def test_migration_snapshot_has_keys(self):
        snap = diag._migration_snapshot()
        assert set(snap) == {"at_head", "head", "error_type"}

    def test_migration_snapshot_failure_degrades(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "app.main", types.ModuleType("app.main"))
        assert diag._migration_snapshot() == {"error_type": "ImportError"}

    def test_platform_snapshot_excludes_hostname(self):
        snap = diag._platform_snapshot()
        assert "hostname" not in snap
        assert "python_version" in snap and "frozen" in snap


class _FakeBrokenDb:
    """integrity PRAGMA 与表清单都失败的会话替身。"""

    def execute(self, *_args, **_kwargs):
        raise RuntimeError("db broken")

    def get_bind(self):
        raise RuntimeError("bind broken")


class TestDatabaseSnapshot:
    def test_broken_db_degrades_with_error_types(self, tmp_path):
        snap = diag._database_snapshot(_FakeBrokenDb(), tmp_path / "missing.db")
        assert snap["exists"] is False
        assert snap["size_bytes"] is None
        assert snap["integrity_check"] is None
        assert snap["integrity_error_type"] == "RuntimeError"
        assert snap["tables"] == {}
        assert snap["tables_error_type"] == "RuntimeError"

    def test_path_none_degrades(self):
        snap = diag._database_snapshot(_FakeBrokenDb(), None)
        assert snap["path"] is None
        assert snap["exists"] is False

    def test_real_session_counts_tables(self, real_db_session):
        snap = diag._database_snapshot(real_db_session, None)
        assert snap["integrity_check"] == "ok"
        assert snap["tables_truncated"] is False
        assert snap["table_count"] == len(snap["tables"])
        assert snap["table_count"] > 0

    def test_tables_truncated_flag(self, real_db_session, monkeypatch):
        monkeypatch.setattr(diag, "MAX_TABLES", 1)
        snap = diag._database_snapshot(real_db_session, None)
        assert snap["tables_truncated"] is True
        assert len(snap["tables"]) == 1


class TestLogSnapshot:
    def test_missing_log_file(self):
        assert diag._log_snapshot(None) == {"available": False}

    def test_unreadable_log_degrades(self, tmp_path):
        snap = diag._log_snapshot(tmp_path / "gone.log")
        assert snap["available"] is True
        assert snap["size_bytes"] is None
        assert snap["modified_at"] is None

    def test_existing_log(self, tmp_path):
        log = tmp_path / "app.log"
        # 用 write_bytes 避免 Windows 文本模式把 \n 变 \r\n 影响字节数断言
        log.write_bytes(b"hello\n")
        snap = diag._log_snapshot(log)
        assert snap["size_bytes"] == 6
        assert snap["modified_at"] is not None


class TestResourceSnapshot:
    def test_normal_or_degraded_never_raises(self):
        snap = diag._resource_snapshot()
        assert set(snap) >= {"cpu_percent", "memory_percent", "disk_percent"}

    def test_psutil_failure_degrades(self, monkeypatch):
        import psutil

        def boom(*_args, **_kwargs):
            raise RuntimeError("no psutil")

        monkeypatch.setattr(psutil, "cpu_percent", boom)
        assert diag._resource_snapshot() == {
            "cpu_percent": None,
            "memory_percent": None,
            "disk_percent": None,
            "error_type": "RuntimeError",
        }


# ==================== ZIP 组装 ====================


def _read_zip(payload: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class TestBundleZip:
    def test_bundle_contains_summary_log_and_checksums(self, tmp_path, monkeypatch):
        log = tmp_path / "app.log"
        log.write_bytes("user 13812345678 password=secret\n".encode("utf-8"))
        monkeypatch.setattr(diag, "_resolve_log_file", lambda: log)
        members = _read_zip(diag._build_bundle_zip({"version": "1.2.3"}))
        assert set(members) == {"summary.json", "app.log.tail", "checksums.txt"}
        assert json.loads(members["summary.json"].decode("utf-8")) == {"version": "1.2.3"}
        assert members["app.log.tail"] == b"user 138******** password=***\n"
        # 校验单兼容 `sha256sum -c`
        lines = members["checksums.txt"].decode("utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            digest, name = line.split("  ", 1)
            assert digest == hashlib.sha256(members[name]).hexdigest()

    def test_bundle_without_log_marks_missing(self, monkeypatch):
        monkeypatch.setattr(diag, "_resolve_log_file", lambda: None)
        members = _read_zip(diag._build_bundle_zip({}))
        assert "app.log.tail.missing" in members

    def test_bundle_unreadable_log_degrades(self, tmp_path, monkeypatch):
        log = tmp_path / "app.log"
        log.write_text("x\n", encoding="utf-8")

        def boom(*_args, **_kwargs):
            raise OSError("locked")

        monkeypatch.setattr(diag, "_resolve_log_file", lambda: log)
        monkeypatch.setattr(diag, "_tail_lines", boom)
        members = _read_zip(diag._build_bundle_zip({}))
        assert members["app.log.tail.unreadable"] == b"OSError"


# ==================== 端点（权限 / 审计） ====================


def _override_user(client, user):
    from app.core.security import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: user
    return client


@pytest.fixture
def admin_user():
    return Mock(id=1, username="admin", role="admin", is_superuser=True, is_active=True)


class TestEndpoints:
    def test_summary_requires_admin(self, client):
        user = Mock(id=2, username="u", role="user", is_superuser=False, is_active=True)
        resp = _override_user(client, user).get("/api/v1/system/diagnostics/summary")
        assert resp.status_code == 403

    def test_summary_returns_diagnostics(self, client, admin_user):
        _override_user(client, admin_user)
        resp = client.get("/api/v1/system/diagnostics/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data) == {
            "generated_at", "version", "build", "platform", "database", "migration", "logs", "resources",
            # W18 P1-3：业务运行状态（备份/调度器/失败任务/数据包占用）
            "business",
        }
        assert data["database"]["integrity_check"] == "ok"
        # 业务段必须能答出"昨晚备份成功了吗 / 调度器在跑吗 / 有失败任务吗"
        business = data["business"]
        assert set(business) == {"backup", "scheduler", "tasks", "data_packages", "pii_encryption"}
        assert "count" in business["backup"]
        assert "started" in business["scheduler"]
        assert "failed" in business["tasks"]
        assert "export_dir_size_mb" in business["data_packages"]
        # W18-B：密钥指纹（不泄露密钥）+ 存量密文可解性
        assert len(business["pii_encryption"]["key_fingerprint"]) == 16
        assert business["pii_encryption"]["status"] in {"ok", "warning", "unknown"}

    def test_bundle_requires_admin(self, client):
        user = Mock(id=2, username="u", role="user", is_superuser=False, is_active=True)
        resp = _override_user(client, user).get("/api/v1/system/diagnostics/bundle")
        assert resp.status_code == 403

    def test_bundle_unauthenticated_rejected(self, client):
        resp = client.get("/api/v1/system/diagnostics/bundle")
        assert resp.status_code in (401, 403)

    def test_bundle_downloads_zip_and_writes_audit(self, client, admin_user):
        _override_user(client, admin_user)
        resp = client.get("/api/v1/system/diagnostics/bundle")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="diagnostics-')
        assert disposition.endswith('.zip"')
        members = _read_zip(resp.content)
        assert "summary.json" in members
        assert "checksums.txt" in members

        from app.core.database import SessionLocal
        from app.models.work_log import WorkLog

        db = SessionLocal()
        try:
            rows = db.query(WorkLog).filter(WorkLog.category == "system").all()
        finally:
            db.close()
        assert any("diagnostics-bundle" in (row.content or "") for row in rows)

    def test_bundle_survives_audit_failure(self, client, admin_user, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("audit down")

        monkeypatch.setattr(diag, "write_work_log", boom)
        _override_user(client, admin_user)
        resp = client.get("/api/v1/system/diagnostics/bundle")
        assert resp.status_code == 200


# ==================== 业务段降级（W18-B） ====================


class TestBusinessSnapshotDegrades:
    """业务段任何一块坏掉都只能降级为 error_type，不能拖垮整份诊断。

    此前这些 ``except`` 分支没有任何用例覆盖（覆盖率门禁会因此变红）：
    真实故障恰恰发生在这里 —— 库半损坏、备份目录不可读时，
    诊断包必须仍然出得来。
    """

    def test_every_section_degrades_independently(self, monkeypatch):
        class Boom:
            def __init__(self, *_a, **_k):
                raise RuntimeError("boom")

        def _raise():
            raise RuntimeError("boom")

        monkeypatch.setattr("app.services.backup_service.BackupService", Boom)
        # 调度器段用 `getattr(sched, "_timers", [])` 读取：换成属性访问即抛的对象

        class BoomSched:
            def __getattr__(self, _name):
                raise RuntimeError("boom")

        monkeypatch.setattr("app.services.backup_scheduler", BoomSched(), raising=False)
        monkeypatch.setattr("app.api.v1.system.tasks.get_tasks_diagnostics", _raise)
        monkeypatch.setattr("app.services.data_package_service.DataPackageService", Boom)
        monkeypatch.setattr("app.core.pii_crypto.key_fingerprint", _raise)

        biz = diag._business_snapshot(Mock())
        for key in ("backup", "scheduler", "tasks", "data_packages", "pii_encryption"):
            assert biz[key] == {"error_type": "RuntimeError"}, key
