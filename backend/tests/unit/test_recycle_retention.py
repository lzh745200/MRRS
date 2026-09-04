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

    def test_days_omitted_falls_back_to_retention_config(self, mem_db, monkeypatch):
        """省略 days 时必须回落 RECYCLE_RETENTION_DAYS 并据此判定超期。

        生产调度器走的正是这条路径（不传 days），而此前所有用例都显式传 days，
        导致 `days = get_retention_days()` 分支从未被执行。这里把保留期设为 7 天：
        10 天前软删的应被清除，3 天前的应保留 —— 证明配置值真的生效，
        而不是退化成默认的 30 天（若退化为 30，两条都不会被清除）。
        """
        monkeypatch.setenv("RECYCLE_RETENTION_DAYS", "7")
        now = datetime.now(timezone.utc)

        expired = Fund(name="超期7天", amount=1)
        expired.is_active = False
        expired.deleted_at = now - timedelta(days=10)

        within = Fund(name="未超期", amount=2)
        within.is_active = False
        within.deleted_at = now - timedelta(days=3)

        mem_db.add_all([expired, within])
        mem_db.commit()

        with patch_backup():
            result = purge_expired_soft_deleted(mem_db)  # 刻意不传 days

        names = {r.name for r in mem_db.query(Fund).all()}
        assert "超期7天" not in names
        assert "未超期" in names
        assert result["total_records"] == 1

    def test_single_record_failure_does_not_block_others(self, mem_db, monkeypatch, caplog):
        """单条清除失败必须 rollback 并继续处理其余记录，不得中断整批。

        对应源码 `except Exception` 分支的注释「单条失败不阻断其余」——
        此前无任何测试锁定该容错保证。
        """
        now = datetime.now(timezone.utc)
        bad = Fund(name="会失败", amount=1)
        bad.is_active = False
        bad.deleted_at = now - timedelta(days=40)
        good = Fund(name="会成功", amount=2)
        good.is_active = False
        good.deleted_at = now - timedelta(days=40)
        mem_db.add_all([bad, good])
        mem_db.commit()
        bad_id, good_id = bad.id, good.id

        calls = {"n": 0}

        def flaky_purge(self, table, rid):
            calls["n"] += 1
            if rid == bad_id:
                raise RuntimeError("boom")
            mem_db.query(Fund).filter(Fund.id == rid).delete()
            mem_db.commit()
            return {"success": True, "deleted_records": 1}

        monkeypatch.setattr(
            "app.services.cascade_purge_service.CascadePurgeService.purge", flaky_purge
        )
        rollbacks = []
        original_rollback = mem_db.rollback
        monkeypatch.setattr(
            mem_db, "rollback", lambda: (rollbacks.append(1), original_rollback())[1]
        )

        with patch_backup():
            result = purge_expired_soft_deleted(mem_db, days=30)

        names = {r.name for r in mem_db.query(Fund).all()}
        # 失败的那条仍在（未被清除），成功的那条已清除 —— 批次未因单条失败中断
        assert "会失败" in names
        assert "会成功" not in names
        assert result["total_records"] == 1
        assert calls["n"] >= 2
        # 失败时确实回滚并留痕
        assert rollbacks, "单条失败后未调用 db.rollback()"
        assert any("回收站自动清除失败" in r.message for r in caplog.records)


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
