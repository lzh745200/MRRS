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
