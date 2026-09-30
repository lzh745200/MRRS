"""OCR 深审第二轮：数据分级归档 / DB 维护 / WAL 告警的回归锁定。

1. data_tier_service.archive_records：默认截止日（now-365d）被 determine_tier 判为
   HOT，历史实现走 else 分支把 1~3 年前的记录当冷数据导出并删行。
2. data_tier_service._archive_to_warm_storage：全仓无 is_archived 列，历史实现无条件
   计数并上报"成功归档 N 条"（静默失效）。
3. data_tier_service._archive_to_cold_storage：归档文件直接写目标路径，中途失败留下
   半截 .gz（库中行未删）→ 恢复重复/损坏。
4. db_maintenance.stop_db_maintenance：未复位 _maintenance_thread → 同进程二次启动静默失效。
5. database_health_service.checkpoint_wal：用 TRUNCATE 之后的体积判告警 → 永不触发。
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tier_service():
    from app.services.data_tier_service import DataTierService

    DataTierService._instance = None
    svc = DataTierService()
    yield svc
    DataTierService._instance = None


class TestArchiveTierSelection:
    def _mock_db(self, count=1):
        db = MagicMock()
        query = MagicMock()
        query.count.return_value = count
        query.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value = query
        return db

    def test_hot_cutoff_routes_to_warm_not_cold(self, tier_service):
        """默认截止日（now-365d）属于温存期，绝不能走冷存删行分支。"""
        db = self._mock_db()

        class MockModel:
            created_at = datetime(2000, 1, 1)

        before_date = datetime.now(timezone.utc) - timedelta(days=365)
        with patch.object(tier_service, "_archive_to_warm_storage", return_value=0) as warm, \
             patch.object(tier_service, "_archive_to_cold_storage") as cold:
            count, message = tier_service.archive_records(
                db, MockModel, before_date=before_date, batch_size=10
            )

        assert count == 0
        warm.assert_called_once()
        cold.assert_not_called()
        assert "warm" in message

    def test_failure_rolls_back_session(self, tier_service):
        """归档异常必须回滚会话，避免会话停留在待回滚状态。"""
        db = self._mock_db()

        class MockModel:
            created_at = datetime(2000, 1, 1)

        before_date = datetime.now(timezone.utc) - timedelta(days=500)
        with patch.object(
            tier_service, "_archive_to_warm_storage", side_effect=Exception("boom")
        ):
            count, message = tier_service.archive_records(
                db, MockModel, before_date=before_date, batch_size=10
            )

        assert count == 0
        assert "归档失败" in message
        db.rollback.assert_called_once()


class TestWarmStorageHonestCounting:
    def test_model_without_flag_returns_zero_and_warns(self, tier_service):
        db = MagicMock()
        query = MagicMock()
        query.limit.return_value.all.return_value = [SimpleNamespace(id=1)]

        class MockModel:
            __name__ = "MockModel"

        with patch("app.services.data_tier_service.logger") as mock_logger:
            result = tier_service._archive_to_warm_storage(db, query, MockModel, 10)

        assert result == 0
        db.commit.assert_not_called()
        assert mock_logger.warning.called

    def test_record_with_flag_is_marked_and_counted(self, tier_service):
        db = MagicMock()
        record = SimpleNamespace(id=1, is_archived=False)
        query = MagicMock()
        query.limit.return_value.all.return_value = [record]

        class MockModel:
            __name__ = "MockModel"

        result = tier_service._archive_to_warm_storage(db, query, MockModel, 10)

        assert result == 1
        assert record.is_archived is True
        db.commit.assert_called_once()


class TestColdArchiveAtomicWrite:
    def _query_with_one_record(self):
        record = MagicMock()
        record.id = 1
        record.__table__ = MagicMock()
        col = MagicMock()
        col.name = "test_field"
        record.__table__.columns = [col]
        query = MagicMock()
        query.limit.return_value.all.return_value = [record]
        query.filter.return_value.delete.return_value = 1
        return query

    def test_failed_replace_leaves_no_tmp_file(self, tier_service, tmp_path):
        db = MagicMock()
        query = self._query_with_one_record()

        class MockModel:
            __name__ = "MockModel"

        MockModel.id = MagicMock()
        with patch.object(tier_service.config, "COLD_ARCHIVE_PATH", str(tmp_path)):
            with patch("app.services.data_tier_service.os.replace", side_effect=OSError("disk full")):
                with pytest.raises(OSError):
                    tier_service._archive_to_cold_storage(db, query, MockModel, 10)

        assert list(Path(tmp_path).iterdir()) == [], "写入失败必须清理临时归档文件"
        db.commit.assert_not_called()

    def test_success_leaves_single_final_file(self, tier_service, tmp_path):
        db = MagicMock()
        query = self._query_with_one_record()

        class MockModel:
            __name__ = "MockModel"

        MockModel.id = MagicMock()
        with patch.object(tier_service.config, "COLD_ARCHIVE_PATH", str(tmp_path)):
            count = tier_service._archive_to_cold_storage(db, query, MockModel, 10)

        files = sorted(p.name for p in Path(tmp_path).iterdir())
        assert count == 1
        assert len(files) == 1
        assert not files[0].endswith(".tmp")


class TestDbMaintenanceRestartable:
    def test_stop_resets_thread_reference_and_allows_restart(self):
        import app.services.db_maintenance as dm

        mock_thread = MagicMock()
        with patch.object(dm, "_maintenance_thread", mock_thread):
            with patch.object(dm, "_stop_event"):
                with patch.object(dm, "logger"):
                    dm.stop_db_maintenance()

            assert dm._maintenance_thread is None, "stop 必须复位线程引用"
            with patch("threading.Thread") as mock_thread_cls:
                dm.start_db_maintenance()
                mock_thread_cls.assert_called_once()


class TestWalWarningUsesPreCheckpointSize:
    def test_truncated_wal_still_warns_on_oversized_before(self, tmp_path, caplog):
        """TRUNCATE 后 -wal≈0，但 checkpoint 前超阈值必须告警（历史实现恒不触发）。"""
        from app.services.database_health_service import DatabaseHealthService

        db_file = tmp_path / "health.db"
        db_file.write_bytes(b"")
        wal = Path(str(db_file) + "-wal")
        wal.write_bytes(b"x" * 4096)

        service = DatabaseHealthService.__new__(DatabaseHealthService)
        service.db_path = db_file
        service.stats = {}
        service.wal_size_warning_bytes = 100

        def _truncate(*args, **kwargs):
            wal.write_bytes(b"")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = _truncate
        mock_cursor.fetchone.return_value = (0, 0, 0)
        mock_conn.cursor.return_value = mock_cursor

        with patch("app.services.database_health_service.sqlite3.connect", return_value=mock_conn):
            with caplog.at_level("WARNING"):
                result = service.checkpoint_wal()

        assert result["status"] == "ok"
        assert result["size_before"] == 4096
        assert result["size_after"] == 0
        assert "WAL 文件偏大" in caplog.text
