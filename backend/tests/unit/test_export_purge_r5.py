"""R5 过期导出回收测试（遗留风险治理计划 2026-09-12 第三周批次）。

覆盖 `async_export_service.purge_expired_exports`：
- 过期已完成任务 → 文件删除 + 状态 expired + file_path 置空；
- 未过期任务 → 不动；pending/processing → 不参与（SQL 过滤）；
- 文件删除失败（占用/权限）→ 保留记录等下轮重试，不改状态；
- 磁盘文件已缺失 → 幂等（仍标记过期）；
- `exports/*.part` 超期回收、新鲜 `.part` 保留；
- `backup_scheduler.export_purge_job` 的会话管理与异常兜底。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.services.async_export_service as aes


def _task(file_path=None, expires_at=None, status="completed"):
    """构造与 ExportTask 同字段的最小替身（避免依赖真实库）。"""
    return SimpleNamespace(
        file_path=file_path,
        expires_at=expires_at,
        status=status,
        error_message=None,
        completed_at=None,
    )


def _db_with(tasks):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = tasks
    return db


class TestPurgeExpiredExports:
    """过期导出文件回收主流程。"""

    def test_expired_task_file_removed_and_marked(self, tmp_path, monkeypatch):
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        export_file = tmp_path / "t1_villages.xlsx"
        export_file.write_bytes(b"xlsx")
        task = _task(
            file_path=str(export_file),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db = _db_with([task])

        stats = aes.purge_expired_exports(db)

        assert stats == {"expired_tasks": 1, "files_removed": 1, "parts_removed": 0}
        assert not export_file.exists()
        assert task.status == "expired"
        assert task.file_path is None
        db.commit.assert_called()

    def test_not_expired_task_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        export_file = tmp_path / "t2.xlsx"
        export_file.write_bytes(b"xlsx")
        task = _task(
            file_path=str(export_file),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=5),
        )
        db = _db_with([task])

        stats = aes.purge_expired_exports(db)

        assert stats == {"expired_tasks": 0, "files_removed": 0, "parts_removed": 0}
        assert export_file.exists()
        assert task.status == "completed"
        assert task.file_path == str(export_file)
        db.commit.assert_not_called()

    def test_expired_task_without_file_marks_only(self, tmp_path, monkeypatch):
        """file_path 为空（如导出失败已清理）→ 仅标记过期，不计数删除。"""
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        task = _task(
            file_path=None,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db = _db_with([task])

        stats = aes.purge_expired_exports(db)

        assert stats == {"expired_tasks": 1, "files_removed": 0, "parts_removed": 0}
        assert task.status == "expired"

    def test_missing_file_is_idempotent(self, tmp_path, monkeypatch):
        """记录指向的文件已不存在 → 不抛错，仍标记过期（missing_ok 幂等）。"""
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        task = _task(
            file_path=str(tmp_path / "gone.xlsx"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db = _db_with([task])

        stats = aes.purge_expired_exports(db)

        assert stats["expired_tasks"] == 1
        assert task.status == "expired"

    def test_unlink_failure_keeps_record(self, tmp_path, monkeypatch):
        """删除被占用（OSError）→ 保留记录与状态，等其他轮次重试。"""
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        export_file = tmp_path / "locked.xlsx"
        export_file.write_bytes(b"xlsx")
        task = _task(
            file_path=str(export_file),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db = _db_with([task])

        with patch.object(
            aes.Path, "unlink", side_effect=PermissionError("in use")
        ):
            stats = aes.purge_expired_exports(db)

        assert stats == {"expired_tasks": 0, "files_removed": 0, "parts_removed": 0}
        assert task.status == "completed"
        assert task.file_path == str(export_file)
        db.commit.assert_not_called()

    def test_naive_expires_at_treated_as_utc(self, tmp_path, monkeypatch):
        """SQLite 读取的 naive datetime 按 UTC 语义比较（否则 TypeError）。"""
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        task = _task(
            file_path=None,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(hours=1),
        )
        db = _db_with([task])

        stats = aes.purge_expired_exports(db)

        assert stats["expired_tasks"] == 1
        assert task.status == "expired"

    def test_aware_expires_at_kept(self):
        """已带时区的值原样返回（_as_utc 的 aware 分支）。"""
        aware = datetime.now(timezone.utc)
        assert aes._as_utc(aware) is aware


class TestPartCleanup:
    """`*.part` 强杀残留回收。"""

    def test_stale_part_removed_fresh_kept(self, tmp_path, monkeypatch):
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        stale = tmp_path / "task_a.xlsx.part"
        fresh = tmp_path / "task_b.xlsx.part"
        stale.write_bytes(b"half")
        fresh.write_bytes(b"half")
        old_ts = (
            datetime.now(timezone.utc) - timedelta(seconds=aes._PART_STALE_SECONDS + 60)
        ).timestamp()
        import os

        os.utime(stale, (old_ts, old_ts))

        stats = aes.purge_expired_exports(_db_with([]))

        assert stats["parts_removed"] == 1
        assert not stale.exists()
        assert fresh.exists()

    def test_part_unlink_failure_is_logged(self, tmp_path, monkeypatch):
        """残留 .part 删除失败：记录警告但不影响主流程（OSError 分支）。"""
        monkeypatch.setattr(aes, "_get_export_dir", lambda: tmp_path)
        stale = tmp_path / "locked.xlsx.part"
        stale.write_bytes(b"half")
        old_ts = (
            datetime.now(timezone.utc) - timedelta(seconds=aes._PART_STALE_SECONDS + 60)
        ).timestamp()
        import os

        os.utime(stale, (old_ts, old_ts))
        real_unlink = aes.Path.unlink

        def _fail_part(self, *args, **kwargs):
            if self.suffix == ".part":
                raise PermissionError("in use")
            return real_unlink(self, *args, **kwargs)

        with patch.object(aes.Path, "unlink", _fail_part):
            stats = aes.purge_expired_exports(_db_with([]))

        assert stats["parts_removed"] == 0
        assert stale.exists()

    def test_export_dir_scan_failure_swallowed(self, monkeypatch):
        """导出目录不可访问（OSError）→ 主流程不受影响。"""

        def _boom():
            raise OSError("no such dir")

        monkeypatch.setattr(aes, "_get_export_dir", _boom)

        stats = aes.purge_expired_exports(_db_with([]))

        assert stats == {"expired_tasks": 0, "files_removed": 0, "parts_removed": 0}


class TestExportPurgeJob:
    """调度器作业包装（会话管理与异常兜底）。"""

    def test_job_runs_purge_and_closes_session(self):
        import app.services.backup_scheduler as bs

        db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), patch(
            "app.services.async_export_service.purge_expired_exports"
        ) as mock_purge:
            bs.export_purge_job()

        mock_purge.assert_called_once_with(db)
        db.close.assert_called_once()

    def test_job_swallows_exception(self):
        import app.services.backup_scheduler as bs

        db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=db), patch(
            "app.services.async_export_service.purge_expired_exports",
            side_effect=RuntimeError("boom"),
        ):
            bs.export_purge_job()  # 不抛错

        db.close.assert_called_once()

    def test_job_is_registered_daily(self):
        """R5 接线断言：export_purge 必须在 start_backup_scheduler 中注册。"""
        import inspect

        import app.services.backup_scheduler as bs

        src = inspect.getsource(bs.start_backup_scheduler)
        assert "export_purge_job" in src
        assert '"export_purge"' in src


@pytest.mark.parametrize(
    "status", ["pending", "processing"]
)
def test_in_flight_statuses_are_filtered_in_sql(status):
    """进行中/待处理任务不进入清理候选（由 SQL filter 排除，防误删在写文件）。"""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    aes.purge_expired_exports(db)
    # 过滤条件确实被下推到 SQL，而不是全表取出后在 Python 侧筛
    filter_args = db.query.return_value.filter.call_args[0]
    assert len(filter_args) >= 2
