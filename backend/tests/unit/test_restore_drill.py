# -*- coding: utf-8 -*-
"""恢复演练服务测试（架构评估 C1 · 2026-09-12）。

覆盖：ok / no_backup / fail（坏 zip / 非 SQLite 载荷）/ skipped_encrypted /
状态持久化与回填 / 调度任务到期判定。
"""

import json
import os
import sqlite3
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from app.services import restore_drill_service
from app.services.restore_drill_service import (
    RESTORE_DRILL_STATUS,
    _latest_backup_file,
    is_drill_due,
    run_restore_drill,
)


def _make_real_sqlite_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users (name) VALUES ('seed')")
        # 核心抽查表之一存在即可验证抽查路径
        conn.execute("CREATE TABLE IF NOT EXISTS supported_villages (id INTEGER PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()


def _make_backup_zip(zip_path, db_payload=None, encrypted=False):
    if db_payload is None:
        tmp_db = zip_path + ".tmpdb"
        _make_real_sqlite_db(tmp_db)
        with open(tmp_db, "rb") as f:
            db_payload = f.read()
        os.remove(tmp_db)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/rural_revitalization.db", db_payload)


@pytest.fixture(autouse=True)
def _reset_status():
    RESTORE_DRILL_STATUS.update({
        "status": "never", "checked_at": None, "backup_file": None,
        "error_type": None, "tables_checked": 0,
    })
    yield
    RESTORE_DRILL_STATUS.update({
        "status": "never", "checked_at": None, "backup_file": None,
        "error_type": None, "tables_checked": 0,
    })


class TestLatestBackupFile:
    def test_picks_newest_backup_zip(self, tmp_path):
        old = tmp_path / "backup_100.zip"
        new = tmp_path / "backup_200.zip"
        old.write_bytes(b"x")
        new.write_bytes(b"y")
        os.utime(old, (1, 1))
        assert _latest_backup_file(str(tmp_path)) == str(new)

    def test_ignores_non_backup_files(self, tmp_path):
        (tmp_path / "other.zip").write_bytes(b"x")
        assert _latest_backup_file(str(tmp_path)) is None

    def test_missing_dir_returns_none(self, tmp_path):
        assert _latest_backup_file(str(tmp_path / "nope")) is None


class TestRunRestoreDrill:
    def test_ok_on_valid_backup(self, tmp_path):
        _make_backup_zip(str(tmp_path / "backup_a.zip"))
        result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "ok"
        assert result["backup_file"] == "backup_a.zip"
        assert result["tables_checked"] >= 2
        assert result["error_type"] is None

    def test_no_backup(self, tmp_path):
        result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "no_backup"

    def test_fail_on_corrupt_zip(self, tmp_path):
        (tmp_path / "backup_bad.zip").write_bytes(b"\x00\x01not a zip")
        result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "fail"
        assert result["error_type"] == "BadZipFile"

    def test_fail_on_non_sqlite_payload(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "backup_fake.zip", "w") as zf:
            zf.writestr("data/rural_revitalization.db", "this is text not sqlite")
        result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "fail"
        assert result["error_type"] == "DatabaseError"

    def test_fail_on_missing_db_member(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "backup_empty.zip", "w") as zf:
            zf.writestr("other/file.txt", "x")
        result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "fail"
        assert result["error_type"] == "FileNotFoundError"

    def test_skip_encrypted_backup(self, tmp_path):
        # Python zipfile 对 AES/加密成员在 extract 时抛 RuntimeError("File ... is encrypted")
        _make_backup_zip(str(tmp_path / "backup_enc.zip"))
        real_extract = zipfile.ZipFile.extract

        def fake_extract(self, member, path=None, pwd=None):
            raise RuntimeError(f"File {member} is encrypted, password required")

        with patch.object(zipfile.ZipFile, "extract", fake_extract):
            result = run_restore_drill(backup_dir=str(tmp_path))
        assert result["status"] == "skipped_encrypted"
        assert real_extract is not None

    def test_persists_result(self, tmp_path):
        _make_backup_zip(str(tmp_path / "backup_p.zip"))
        with patch.object(restore_drill_service, "_persist_result", wraps=restore_drill_service._persist_result) as spy:
            run_restore_drill(backup_dir=str(tmp_path))
        assert spy.called

    def test_backup_dir_default_from_config(self, tmp_path):
        _make_backup_zip(str(tmp_path / "backup_cfg.zip"))
        with patch("app.services.system_config_service.get_config", return_value=str(tmp_path)):
            result = run_restore_drill(db=MagicMock())
        assert result["status"] == "ok"
        assert result["backup_file"] == "backup_cfg.zip"


class TestPersistAndLoad:
    def test_persist_writes_config(self):
        with patch("app.services.system_config_service.set_config") as mock_set:
            restore_drill_service._update_status("ok", "/x/backup_1.zip", None, 3)
            restore_drill_service._persist_result()
        assert mock_set.call_count == 2

    def test_persist_failure_is_swallowed(self):
        with patch("app.services.system_config_service.set_config", side_effect=RuntimeError("db down")):
            restore_drill_service._persist_result()  # 不应抛出

    def test_load_persisted_status(self):
        payload = json.dumps({
            "status": "ok", "checked_at": "2026-09-01T05:45:00",
            "backup_file": "backup_old.zip", "error_type": None, "tables_checked": 4,
        })
        db = MagicMock()
        db.close = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), \
             patch("app.services.system_config_service.get_config", return_value=payload):
            restore_drill_service._load_persisted_status()
        assert RESTORE_DRILL_STATUS["status"] == "ok"
        assert RESTORE_DRILL_STATUS["tables_checked"] == 4

    def test_load_persisted_status_empty(self):
        db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), \
             patch("app.services.system_config_service.get_config", return_value=""):
            restore_drill_service._load_persisted_status()  # 不应抛出

    def test_load_persisted_status_bad_json(self):
        db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), \
             patch("app.services.system_config_service.get_config", return_value="{bad"):
            restore_drill_service._load_persisted_status()  # 不应抛出


class TestIsDrillDue:
    def test_never_persisted_is_due(self):
        RESTORE_DRILL_STATUS.update({"status": "never", "checked_at": None})
        db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), \
             patch("app.services.system_config_service.get_config", return_value=""):
            assert is_drill_due() is True

    def test_recent_run_not_due(self):
        from datetime import datetime, timedelta

        RESTORE_DRILL_STATUS["checked_at"] = (datetime.now() - timedelta(days=1)).isoformat()
        assert is_drill_due(30) is False

    def test_old_run_is_due(self):
        from datetime import datetime, timedelta

        RESTORE_DRILL_STATUS["checked_at"] = (datetime.now() - timedelta(days=40)).isoformat()
        assert is_drill_due(30) is True

    def test_unparseable_is_due(self):
        RESTORE_DRILL_STATUS["checked_at"] = "not-a-date"
        assert is_drill_due() is True

    def test_never_with_db_error_is_due(self):
        RESTORE_DRILL_STATUS.update({"status": "never", "checked_at": None})
        with patch("app.core.database.SessionLocal", side_effect=RuntimeError("no db")):
            assert is_drill_due() is True


class TestSchedulerJob:
    # 注意 patch 目标：backup_scheduler 在模块级 `from ... import` 绑定了
    # get_config / get_db_context，必须 patch **绑定处**
    # （app.services.backup_scheduler.*）；patch 源模块属性不会生效，
    # 会让异常注入变成空操作、测试形同虚设（2026-09-12 实测 99.98% 时发现）。
    @pytest.mark.asyncio
    async def test_job_skips_when_not_due(self):
        from app.services.backup_scheduler import restore_drill_job

        with patch("app.services.backup_scheduler.get_config", return_value="30"), \
             patch("app.services.restore_drill_service.is_drill_due", return_value=False):
            await restore_drill_job()  # 应直接返回，不执行演练

    @pytest.mark.asyncio
    async def test_job_runs_drill_on_due(self):
        from app.services.backup_scheduler import restore_drill_job

        with patch("app.services.backup_scheduler.get_config", return_value="30"), \
             patch("app.services.restore_drill_service.is_drill_due", return_value=True), \
             patch("app.services.backup_scheduler.get_db_context"), \
             patch("app.services.restore_drill_service.run_restore_drill",
                   return_value={"status": "ok", "backup_file": "b.zip", "tables_checked": 3}) as mock_run:
            await restore_drill_job()
        assert mock_run.called

    @pytest.mark.asyncio
    async def test_job_failure_sends_reminder(self):
        from app.services.backup_scheduler import restore_drill_job

        db = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("app.services.backup_scheduler.get_config", return_value="30"), \
             patch("app.services.restore_drill_service.is_drill_due", return_value=True), \
             patch("app.services.backup_scheduler.get_db_context", return_value=ctx), \
             patch("app.services.restore_drill_service.run_restore_drill",
                   return_value={"status": "fail", "backup_file": "b.zip", "error_type": "BadZipFile"}), \
             patch("app.services.backup_scheduler._send_backup_reminder") as mock_send:
            await restore_drill_job()
        assert mock_send.called

    @pytest.mark.asyncio
    async def test_job_exception_is_swallowed(self):
        from app.services.backup_scheduler import restore_drill_job

        with patch("app.services.backup_scheduler.get_config", side_effect=RuntimeError("boom")):
            await restore_drill_job()  # 不应抛出
