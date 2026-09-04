"""T044 验收：后端调度为备份唯一真相源。

- /system/backup/schedule GET 返回真实配置（auto_backup 默认 true，retention 默认 7）
- PUT 写入 SystemConfig 并热生效（GET 回读一致）
- BackupService.cleanup_by_retention_days 按保留天数清理过期备份（fake clock）
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

BASE = "/api/v1/system/backup"

SCHEDULE_KEYS = ["auto_backup", "backup_retention_days", "backup_schedule_cron"]


def _auth(client):
    from app.core.security import get_current_user

    u = MagicMock()
    u.role = "admin"
    u.is_superuser = True
    u.id = 1
    client.app.dependency_overrides[get_current_user] = lambda: u


def _clear_schedule_config():
    from app.core.database import SessionLocal
    from app.models.system_config import SystemConfig

    db = SessionLocal()
    try:
        db.query(SystemConfig).filter(SystemConfig.key.in_(SCHEDULE_KEYS)).delete()
        db.commit()
    finally:
        db.close()


class TestBackupScheduleUnify:
    def test_get_default_enabled_true(self, client_with_mocked_auth):
        from app.services.system_config_service import delete_config

        for k in SCHEDULE_KEYS:
            delete_config(k)
        _auth(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["enabled"] is True, data
        assert data["keepCount"] == 7, data
        assert data["nextRun"] is not None

    def test_put_then_get_hot_apply(self, client_with_mocked_auth):
        _auth(client_with_mocked_auth)
        resp = client_with_mocked_auth.put(
            f"{BASE}/schedule",
            json={"enabled": False, "keep_count": 3},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["enabled"] is False
        assert body["keepCount"] == 3

        # 热生效：GET 回读与 PUT 一致
        resp2 = client_with_mocked_auth.get(f"{BASE}/schedule")
        data2 = resp2.json()["data"]
        assert data2["enabled"] is False
        assert data2["keepCount"] == 3


class TestRetentionCleanup:
    def test_cleanup_by_retention_days(self, real_db_session, monkeypatch):
        from app.models.system_config import SystemConfig
        from app.services.backup_service import BackupService

        NOW = datetime(2026, 8, 1, 12, 0, 0)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW

        monkeypatch.setattr("app.services.backup_service.datetime", FakeDateTime)

        old = SystemConfig(key="backup_20260722_010000", value="/tmp/old.zip", description="b")
        old.created_at = NOW - timedelta(days=10)
        new = SystemConfig(key="backup_20260730_010000", value="/tmp/new.zip", description="b")
        new.created_at = NOW - timedelta(days=2)
        real_db_session.add_all([old, new])
        real_db_session.commit()

        svc = BackupService(real_db_session)
        deleted = svc.cleanup_by_retention_days(7)

        assert deleted == 1
        remaining = (
            real_db_session.query(SystemConfig)
            .filter(SystemConfig.key.like("backup_20%"))
            .all()
        )
        assert len(remaining) == 1
        assert remaining[0].key == "backup_20260730_010000"

    def test_cleanup_noop_when_days_non_positive(self, real_db_session):
        """days<=0 是「保留期未配置/不清理」守卫：必须直接返回 0 且不动任何记录。"""
        from app.models.system_config import SystemConfig
        from app.services.backup_service import BackupService

        rec = SystemConfig(key="backup_20200101_010000", value="/tmp/x.zip", description="b")
        real_db_session.add(rec)
        real_db_session.commit()

        svc = BackupService(real_db_session)
        assert svc.cleanup_by_retention_days(0) == 0
        assert svc.cleanup_by_retention_days(-5) == 0
        assert real_db_session.query(SystemConfig).count() == 1

    def test_cleanup_parses_iso_string_created_at(self, real_db_session, monkeypatch):
        """created_at 以 ISO 字符串返回时必须能解析并参与超期判定。

        SQLite 下 ORM 取回的时间可能是字符串，源码专门有 isinstance(rec_time, str)
        分支；此前无测试触达，一旦该分支被误删，字符串时间会导致比较抛 TypeError。
        """
        from app.models.system_config import SystemConfig
        from app.services.backup_service import BackupService

        NOW = datetime(2026, 8, 1, 12, 0, 0)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW

        monkeypatch.setattr("app.services.backup_service.datetime", FakeDateTime)

        rec = SystemConfig(key="backup_20260701_010000", value="/tmp/str.zip", description="b")
        real_db_session.add(rec)
        real_db_session.commit()
        # 强制字符串形态（早于 cutoff 30 天）
        rec.created_at = (NOW - timedelta(days=30)).isoformat()
        monkeypatch.setattr(
            BackupService, "_query_backup_records", lambda self: [rec]
        )

        assert BackupService(real_db_session).cleanup_by_retention_days(7) == 1

    def test_cleanup_skips_unparseable_created_at(self, real_db_session, monkeypatch):
        """created_at 无法解析时必须跳过该条，而不是让整批清理崩溃。"""
        from app.models.system_config import SystemConfig
        from app.services.backup_service import BackupService

        bad = SystemConfig(key="backup_20260701_010000", value="/tmp/bad.zip", description="b")
        real_db_session.add(bad)
        real_db_session.commit()
        bad.created_at = "not-a-timestamp"
        monkeypatch.setattr(
            BackupService, "_query_backup_records", lambda self: [bad]
        )

        assert BackupService(real_db_session).cleanup_by_retention_days(7) == 0
        # 记录未被删除（跳过而非误删）
        assert real_db_session.query(SystemConfig).count() == 1

    def test_cleanup_survives_undeletable_backup_file(
        self, real_db_session, monkeypatch, tmp_path
    ):
        """备份文件删不掉时仍须删除数据库记录，不得让清理中断。

        用真实目录冒充备份文件：os.unlink 对目录在 Windows 抛 PermissionError、
        Linux 抛 IsADirectoryError，两者都在源码捕获的异常元组内 —— 因此该用例
        在两个平台上走同一条容错路径。
        """
        from app.models.system_config import SystemConfig
        from app.services.backup_service import BackupService

        NOW = datetime(2026, 8, 1, 12, 0, 0)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW

        monkeypatch.setattr("app.services.backup_service.datetime", FakeDateTime)

        # 名字必须以 .zip 结尾：_query_backup_records 用 value.like("%.zip") 过滤，
        # 否则记录根本不会被查出来，测不到 unlink 的容错分支。
        a_dir = tmp_path / "backup_that_is_actually_a_dir.zip"
        a_dir.mkdir()
        rec = SystemConfig(
            key="backup_20260701_020000", value=str(a_dir), description="b"
        )
        rec.created_at = NOW - timedelta(days=30)
        real_db_session.add(rec)
        real_db_session.commit()

        deleted = BackupService(real_db_session).cleanup_by_retention_days(7)

        assert deleted == 1
        assert real_db_session.query(SystemConfig).count() == 0
        # 目录本身未被误删（unlink 失败后被吞掉），仍留在磁盘上
        assert a_dir.exists()
