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
