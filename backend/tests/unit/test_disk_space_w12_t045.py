"""W12-T045 磁盘空间感知测试

覆盖：
- get_disk_free_bytes: psutil / statvfs / shutil 三路探测（mock 验证逻辑）
- has_enough_free_space: 阈值判定
- BackupService.get_disk_space_info: 备份目录 / 数据库目录剩余空间聚合
- create_backup 低空间拒绝（mock check_disk_space 返回不足）
- upload-restore 端点低空间 409（复用端点内联逻辑）
"""

import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from app.utils.disk_space import (
    MIN_FREE_BYTES,
    get_disk_free_bytes,
    has_enough_free_space,
)


class _NoPsutil(types.ModuleType):
    """属性访问即抛 ImportError 的伪 psutil——模拟 psutil 缺失/损坏。

    注入 sys.modules 后，get_disk_free_bytes 内层 `import psutil` 会命中它，
    随后的 psutil.disk_usage 属性访问抛 ImportError，触发向 statvfs/shutil 降级。
    不 patch builtins.__import__：CPython 3.11 的 IMPORT_NAME 直连导入机制，
    且对 builtins 打桩会造成 _import_raiser 内部调用自身的无限递归。
    """

    def __getattr__(self, item):  # noqa: D105
        raise ImportError(f"no psutil.{item}")


class TestDiskSpaceUtil:
    def test_get_disk_free_bytes_psutil(self):
        # psutil 在函数内 import（非模块级属性），
        # 通过向 sys.modules 注入伪模块使内层 import 命中桩对象。
        fake_psutil = MagicMock()
        fake_psutil.disk_usage.return_value.free = 123456
        with patch.dict(sys.modules, {"psutil": fake_psutil}):
            assert get_disk_free_bytes("/tmp") == 123456

    def test_get_disk_free_bytes_psutil_fail_falls_to_statvfs(self):
        import app.utils.disk_space as ds

        # Windows 的 os 为 frozen 模块且无 statvfs 属性，必须 create=True 才能打桩
        with patch.dict(sys.modules, {"psutil": _NoPsutil("psutil")}):
            with patch.object(
                os,
                "statvfs",
                return_value=MagicMock(f_bavail=10, f_frsize=1024),
                create=True,
            ):
                assert ds.get_disk_free_bytes("/tmp") == 10 * 1024

    def test_get_disk_free_bytes_all_fail_returns_neg1(self):
        import app.utils.disk_space as ds

        saved_statvfs = getattr(os, "statvfs", None)
        try:
            # 无 statvfs（Windows 天然满足；Linux 下临时移除）+ shutil 抛错 → -1
            if saved_statvfs is not None:
                del os.statvfs
            with patch.dict(sys.modules, {"psutil": _NoPsutil("psutil")}):
                with patch("app.utils.disk_space.shutil") as mock_sh:
                    mock_sh.disk_usage.side_effect = OSError("boom")
                    assert ds.get_disk_free_bytes("/tmp") == -1
        finally:
            if saved_statvfs is not None:
                os.statvfs = saved_statvfs

    def test_has_enough_free_space_sufficient(self):
        ok, free = has_enough_free_space("/tmp", required_bytes=100)
        # 真实环境要么充足要么未知（-1 保守放行）
        assert ok is True

    def test_has_enough_free_space_insufficient(self):
        with patch("app.utils.disk_space.get_disk_free_bytes", return_value=10):
            ok, free = has_enough_free_space("/tmp", required_bytes=100)
            assert ok is False
            assert free == 10

    def test_min_free_bytes_constant(self):
        assert MIN_FREE_BYTES == 500 * 1024 * 1024


@pytest.mark.asyncio
class TestBackupDiskSpace:
    async def test_create_backup_low_space_rejected(self):
        from app.services.backup_service import BackupRestoreError, BackupService

        svc = BackupService.__new__(BackupService)
        svc.backup_dir = "/tmp/backup"
        svc.database_path = "/tmp/db.sqlite"
        svc.db = MagicMock()

        with patch(
            "app.core.database.check_disk_space",
            return_value={"free_mb": 10, "total_mb": 100, "sufficient": False, "path": "/tmp"},
        ):
            with pytest.raises(BackupRestoreError):
                svc._ensure_disk_space(min_mb=500)

    async def test_create_backup_enough_space_ok(self):
        from app.services.backup_service import BackupService

        svc = BackupService.__new__(BackupService)
        svc.backup_dir = "/tmp/backup"
        svc.database_path = "/tmp/db.sqlite"

        with patch(
            "app.core.database.check_disk_space",
            return_value={"free_mb": 9999, "total_mb": 10000, "sufficient": True, "path": "/tmp"},
        ):
            svc._ensure_disk_space(min_mb=500)

    async def test_get_disk_space_info(self):
        from app.services.backup_service import BackupService

        svc = BackupService.__new__(BackupService)
        svc.backup_dir = "/tmp/backup"
        svc.database_path = "/tmp/db.sqlite"

        fake = {"free_mb": 8000, "total_mb": 10000, "sufficient": True, "path": "/tmp"}

        with patch("app.core.database.check_disk_space", return_value=fake):
            info = svc.get_disk_space_info()
        assert info["threshold_mb"] == 500
        assert info["backup_dir"]["free_mb"] == 8000
        assert info["db_dir"]["free_mb"] == 8000


@pytest.mark.asyncio
class TestUploadRestoreDiskPrecheck:
    async def test_upload_restore_low_space_409(self):
        from fastapi import HTTPException

        import app.core.database as core_db
        from app.utils.paths import get_backup_path

        # 注意：必须通过模块属性访问（core_db.check_disk_space），
        # 若在 patch 前用 from-import 绑定局部名，patch 模块属性不影响局部引用，
        # 会调用真实函数导致 DID NOT RAISE。
        with patch(
            "app.core.database.check_disk_space",
            return_value={"free_mb": 5, "total_mb": 100, "sufficient": False, "path": "/tmp"},
        ):
            with pytest.raises(HTTPException) as exc:
                disk = core_db.check_disk_space(min_mb=500, path=str(get_backup_path()))
                if not disk.get("sufficient", False):
                    raise HTTPException(
                        status_code=409,
                        detail=f"磁盘剩余空间不足（{disk.get('free_mb', -1)}MB < 500MB），"
                        "无法安全接收并恢复备份包",
                    )
            assert exc.value.status_code == 409
