# -*- coding: utf-8 -*-
"""C1 备份存放可见化 + F1 单轨化可见性的回归（v1.12.4 后续）。

架构评估 C1 要求把"备份与数据库同盘"这件高风险事**变得可见**（配套约定建议
`backup_target_dir` 指向独立物理盘；同盘时断电/盘损会让数据与备份一起消失）。
F1 则要求"是否仍在跑已弃用的自动补列兜底"可被运维直接观测。

本文件锁定：
1. `backups_share_volume_with_database` 四种结论（同卷/异卷/未知/stat 失败兜底）
   在**两个平台**都可判定 —— 分支必须可达，否则本地（Windows）100% 覆盖率门禁
   与 CI（Linux）会分叉；
2. `/health` 暴露 `backup.same_volume_as_database` 与
   `migration.auto_migration_enabled` 两个信号，且**不泄露绝对路径**。
"""

from pathlib import Path
from unittest.mock import patch

from app.services.backup_service import backups_share_volume_with_database


class TestSameVolumeDetection:
    def test_missing_arguments_return_none(self):
        assert backups_share_volume_with_database("", "/backups") is None
        assert backups_share_volume_with_database("/data/db.sqlite", "") is None

    def test_existing_paths_compare_device_id(self, tmp_path):
        """两条路径都存在 → 走 st_dev 比较（最可靠）。本机同盘 ⇒ True。"""
        db = tmp_path / "data" / "rural_revitalization.db"
        db.parent.mkdir()
        db.write_bytes(b"x")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        assert backups_share_volume_with_database(str(db), str(backup_dir)) is True

    def test_stat_failure_falls_back_to_path_prefix(self, tmp_path):
        """stat 抛 OSError 时不得崩：退回路径前缀判定。"""
        db = tmp_path / "data" / "db.sqlite"
        db.parent.mkdir()
        db.write_bytes(b"x")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch("app.services.backup_service.os.stat", side_effect=OSError("boom")):
            result = backups_share_volume_with_database(str(db), str(backup_dir))
        # 同一盘符 ⇒ True（同卷）；关键是不抛异常且有确定结论
        assert result is True

    def test_missing_paths_fall_back_to_prefix(self):
        """路径不存在（stat 抛 FileNotFoundError，属 OSError）⇒ 前缀兜底仍给结论。

        用两个**不同首层挂载点**且必然不存在的路径，保证两平台结果一致。
        """
        assert (
            backups_share_volume_with_database(
                "/nonexistent_mount_a/db.sqlite", "/nonexistent_mount_b/backups"
            )
            is False
        )
        assert (
            backups_share_volume_with_database(
                "/nonexistent_mount_a/db.sqlite", "/nonexistent_mount_a/backups"
            )
            is True
        )

    def test_windows_different_drive_is_other_volume(self):
        """盘符不同 ⇒ 异卷（False）。用不存在的盘符，避免依赖真实磁盘布局。"""
        assert (
            backups_share_volume_with_database(
                "C:/app/data/rural_revitalization.db", "Z:/backups"
            )
            is False
        )

    def test_posix_mount_points_are_compared_when_no_drive(self):
        """/data 与 /mnt/usb 属不同挂载点 ⇒ False；同挂载点 ⇒ True。

        该分支在 Windows 上也必须可达（因此实现刻意不做 abspath）。
        """
        if Path("/data").exists() or Path("/mnt").exists():
            # 真机上存在同名目录时，用不存在的深层路径仍走前缀判定
            pass
        assert (
            backups_share_volume_with_database("/data/db.sqlite", "/mnt/usb/backups")
            is False
        )
        assert (
            backups_share_volume_with_database("/data/db.sqlite", "/data/backups")
            is True
        )

    def test_relative_paths_are_unknown(self):
        """相对路径既无盘符也非绝对路径 ⇒ None（不得猜测为安全）。"""
        assert backups_share_volume_with_database("data/db.sqlite", "backups") is None


class TestHealthExposesNewSignals:
    def test_health_reports_backup_volume_and_auto_migration(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()

        assert "backup" in body
        assert set(body["backup"]) == {"same_volume_as_database"}
        assert body["backup"]["same_volume_as_database"] in (True, False, None)

        assert "auto_migration_enabled" in body["migration"]
        assert isinstance(body["migration"]["auto_migration_enabled"], bool)

    def test_health_does_not_leak_absolute_paths(self, client):
        """本端点无认证：新信号只能出布尔值，不得带路径。"""
        raw = client.get("/health").text
        assert "rural_revitalization.db" not in raw
        assert "C:\\" not in raw and "C:/" not in raw
