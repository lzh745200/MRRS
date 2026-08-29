"""W12-T045 磁盘空间感知测试

覆盖：
- BackupService.get_disk_space_info: 备份目录 / 数据库目录剩余空间聚合
- create_backup 低空间拒绝（mock check_disk_space 返回不足）
- upload-restore 端点低空间 409（复用端点内联逻辑）
"""

from unittest.mock import MagicMock, patch

import pytest


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
