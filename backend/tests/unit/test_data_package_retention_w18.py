"""W18 P1-6 回归：数据包导出文件保留期清理。

背景：单机离线环境下用户频繁导出数据包（每个数十~数百 MB），原实现**没有
任何累计清理** —— 长期运行后磁盘被撑满，备份/导入连锁失败，且首页不会
提前预警。这里验证按天数清理与占用统计的行为契约。
"""
import os
import time
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def service(tmp_path):
    from app.services.data_package_service import DataPackageService

    return DataPackageService(db=MagicMock(), upload_dir=str(tmp_path))


def _mk_file(tmp_path, name, age_days):
    p = tmp_path / name
    p.write_bytes(b"x" * 16)
    old = time.time() - age_days * 86400
    os.utime(p, (old, old))
    return p


class TestCleanupExportedFiles:
    def test_deletes_files_older_than_retention(self, service, tmp_path):
        old1 = _mk_file(tmp_path, "old1.zip", 10)
        old2 = _mk_file(tmp_path, "old2.zip", 8)
        fresh = _mk_file(tmp_path, "fresh.zip", 1)

        deleted = service.cleanup_exported_files(7)

        assert deleted == 2
        assert not old1.exists()
        assert not old2.exists()
        assert fresh.exists()  # 保留期内的不动

    def test_non_positive_retention_is_noop(self, service, tmp_path):
        f = _mk_file(tmp_path, "old.zip", 100)
        assert service.cleanup_exported_files(0) == 0
        assert service.cleanup_exported_files(-1) == 0
        assert f.exists()

    def test_skips_subdirectories(self, service, tmp_path):
        (tmp_path / "sub").mkdir()
        old = _mk_file(tmp_path, "old.zip", 30)
        old_ts = time.time() - 40 * 86400
        os.utime(tmp_path / "sub", (old_ts, old_ts))
        assert service.cleanup_exported_files(7) == 1
        assert (tmp_path / "sub").is_dir()

    def test_missing_dir_does_not_raise(self, tmp_path):
        from app.services.data_package_service import DataPackageService

        svc = DataPackageService(db=MagicMock(), upload_dir=str(tmp_path / "absent"))
        assert svc.cleanup_exported_files(7) == 0

    def test_unlink_failure_keeps_going(self, service, tmp_path, monkeypatch):
        """单个文件删不掉（被占用）不应中断整轮清理。"""
        a = _mk_file(tmp_path, "a.zip", 10)
        b = _mk_file(tmp_path, "b.zip", 10)
        real_unlink = os.unlink

        def _flaky_unlink(path, *args, **kwargs):
            if str(path).endswith("a.zip"):
                raise PermissionError("locked")
            return real_unlink(path, *args, **kwargs)

        monkeypatch.setattr(os, "unlink", _flaky_unlink)
        assert service.cleanup_exported_files(7) == 1
        assert a.exists()
        assert not b.exists()


class TestUploadDirSize:
    def test_sums_file_sizes(self, service, tmp_path):
        (tmp_path / "a.zip").write_bytes(b"12345")
        (tmp_path / "b.zip").write_bytes(b"123")
        assert service.get_upload_dir_size() == 8

    def test_missing_dir_returns_zero(self, tmp_path):
        from app.services.data_package_service import DataPackageService

        svc = DataPackageService(db=MagicMock(), upload_dir=str(tmp_path / "absent"))
        assert svc.get_upload_dir_size() == 0

class TestDataPackageCleanupJob:
    """W18 P1-6：定时作业体（backup_scheduler.data_package_cleanup_job）。"""

    def test_job_calls_cleanup_with_configured_days(self, monkeypatch):
        import asyncio
        import contextlib
        from unittest.mock import MagicMock

        import app.services.backup_scheduler as sched
        from app.services.data_package_service import DataPackageService

        seen = {}

        def _clean(self, days):
            seen["days"] = days
            return 2

        monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(MagicMock()))
        monkeypatch.setattr(sched, "get_int_config", lambda *a, **k: 5)
        monkeypatch.setattr(DataPackageService, "cleanup_exported_files", _clean)

        asyncio.run(sched.data_package_cleanup_job())
        assert seen["days"] == 5

    def test_job_swallows_cleanup_errors(self, monkeypatch):
        """清理异常不得冒泡（否则拖垮整轮调度）。"""
        import asyncio
        import contextlib
        from unittest.mock import MagicMock

        import app.services.backup_scheduler as sched
        from app.services.data_package_service import DataPackageService

        monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(MagicMock()))
        monkeypatch.setattr(sched, "get_int_config", lambda *a, **k: 7)

        def _boom(self, days):
            raise RuntimeError("disk gone")

        monkeypatch.setattr(DataPackageService, "cleanup_exported_files", _boom)
        asyncio.run(sched.data_package_cleanup_job())  # 不应抛出


class TestRetentionEdgeCases:
    def test_cleanup_noop_when_dir_unreadable(self, service, monkeypatch):
        monkeypatch.setattr(
            "os.listdir", lambda _p: (_ for _ in ()).throw(OSError("denied"))
        )
        assert service.cleanup_exported_files(7) == 0

    def test_size_zero_when_dir_unreadable(self, service, monkeypatch):
        monkeypatch.setattr(
            "os.listdir", lambda _p: (_ for _ in ()).throw(OSError("denied"))
        )
        assert service.get_upload_dir_size() == 0

    def test_size_skips_subdirectory(self, service, tmp_path):
        """子目录不计入占用（覆盖 isfile=False 的跳过分支）。"""
        (tmp_path / "ok.zip").write_bytes(b"12345")
        (tmp_path / "nested").mkdir()
        assert service.get_upload_dir_size() == 5

    def test_size_skips_unstattable_entry(self, service, tmp_path, monkeypatch):
        (tmp_path / "ok.zip").write_bytes(b"123")
        (tmp_path / "bad.zip").write_bytes(b"456")
        real_getsize = os.path.getsize

        def _flaky_getsize(path):
            if str(path).endswith("bad.zip"):
                raise OSError("locked")
            return real_getsize(path)

        monkeypatch.setattr(os.path, "getsize", _flaky_getsize)
        assert service.get_upload_dir_size() == 3
