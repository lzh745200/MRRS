"""回收站保留期策略测试 (Phase D)"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models.fund import Fund
from app.services.retention_service import get_retention_days, purge_expired_soft_deleted


class TestGetRetentionDays:
    def test_default_30(self, monkeypatch):
        monkeypatch.delenv("RECYCLE_RETENTION_DAYS", raising=False)
        assert get_retention_days() == 30

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RECYCLE_RETENTION_DAYS", "7")
        assert get_retention_days() == 7

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv("RECYCLE_RETENTION_DAYS", "0")
        assert get_retention_days() == 0

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("RECYCLE_RETENTION_DAYS", "abc")
        assert get_retention_days() == 30


@pytest.fixture
def mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    db = S()
    yield db
    db.close()
    engine.dispose()


class TestPurgeExpired:
    def test_disabled_when_days_zero(self, mem_db, monkeypatch):
        monkeypatch.setattr(
            "app.services.retention_service.get_retention_days", lambda: 0
        )
        result = purge_expired_soft_deleted(mem_db, days=0)
        assert result == {"disabled": True}

    def test_purges_only_expired_soft_deleted(self, mem_db):
        now = datetime.now(timezone.utc)
        old_del = Fund(name="老软删", amount=1)
        old_del.is_active = False
        old_del.deleted_at = now - timedelta(days=40)

        fresh_del = Fund(name="新软删", amount=2)
        fresh_del.is_active = False
        fresh_del.deleted_at = now - timedelta(days=3)

        active = Fund(name="活跃", amount=3)
        legacy = Fund(name="无时间戳软删", amount=4)  # deleted_at 为空 → 不清
        legacy.is_active = False

        mem_db.add_all([old_del, fresh_del, active, legacy])
        mem_db.commit()

        with patch_backup():
            result = purge_expired_soft_deleted(mem_db, days=30)

        names = {r.name for r in mem_db.query(Fund).all()}
        assert "老软删" not in names
        assert {"新软删", "活跃", "无时间戳软删"} <= names
        assert result["total_records"] >= 1


class patch_backup:
    """屏蔽即时备份触发，避免测试环境副作用。"""

    def __enter__(self):
        self.patches = [
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "app.services.immediate_backup.trigger_immediate_backup",
            ),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self.patches:
            p.stop()
