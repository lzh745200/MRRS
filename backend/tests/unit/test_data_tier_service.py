"""
测试 - app.services.data_tier_service
覆盖率目标: 100%
"""
import pytest
import json
import gzip
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import os

class TestDataTier:
    """测试 DataTier 枚举"""

    def test_data_tier_values(self):
        """测试数据分级值"""
        from app.services.data_tier_service import DataTier
        assert DataTier.HOT == "hot"
        assert DataTier.WARM == "warm"
        assert DataTier.COLD == "cold"

class TestDataTierConfig:
    """测试 DataTierConfig 配置"""

    def test_config_values(self):
        """测试配置值"""
        from app.services.data_tier_service import DataTierConfig
        assert DataTierConfig.HOT_THRESHOLD_DAYS == 365
        assert DataTierConfig.WARM_THRESHOLD_DAYS == 365 * 3
        assert DataTierConfig.COMPRESSION_ENABLED is True
        assert DataTierConfig.ARCHIVE_BATCH_SIZE == 1000

class TestDataTierService:
    """测试 DataTierService"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        from app.services.data_tier_service import DataTierService
        DataTierService._instance = None
        service = DataTierService()
        return service

    @pytest.fixture
    def temp_archive_dir(self):
        """创建临时归档目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_service_singleton(self):
        """测试服务单例模式"""
        from app.services.data_tier_service import DataTierService
        DataTierService._instance = None

        service1 = DataTierService()
        service2 = DataTierService()

        assert service1 is service2

    def test_service_initialization(self, service):
        """测试服务初始化"""
        assert service._initialized is True
        assert service.config is not None

    def test_determine_tier_hot(self, service):
        """测试确定热数据分级"""
        recent_date = datetime.utcnow() - timedelta(days=100)
        tier = service.determine_tier(recent_date)

        from app.services.data_tier_service import DataTier
        assert tier == DataTier.HOT

    def test_determine_tier_warm(self, service):
        """测试确定温数据分级"""
        warm_date = datetime.utcnow() - timedelta(days=500)
        tier = service.determine_tier(warm_date)

        from app.services.data_tier_service import DataTier
        assert tier == DataTier.WARM

    def test_determine_tier_cold(self, service):
        """测试确定冷数据分级"""
        cold_date = datetime.utcnow() - timedelta(days=1500)
        tier = service.determine_tier(cold_date)

        from app.services.data_tier_service import DataTier
        assert tier == DataTier.COLD

    def test_determine_tier_naive_datetime(self, service):
        """测试确定数据分级 - 无时区日期"""
        from app.services.data_tier_service import DataTier
        naive_date = datetime.utcnow() - timedelta(days=100)
        assert naive_date.tzinfo is None
        tier = service.determine_tier(naive_date)
        assert tier == DataTier.HOT

    def test_get_archive_stats(self, service, temp_archive_dir):
        """测试获取归档统计"""
        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            with patch.object(service.config, 'HOT_DATA_PATH', '/nonexistent.db'):
                with patch.object(service.config, 'WARM_DATA_PATH', '/nonexistent_warm.db'):
                    stats = service.get_archive_stats(MagicMock())

        assert "total_records" in stats
        assert "by_tier" in stats
        assert "storage" in stats

    def test_get_archive_stats_with_files(self, service, temp_archive_dir):
        """测试获取归档统计 - 有冷数据文件"""
        archive_file = Path(temp_archive_dir) / "test_archive.gz"
        with gzip.open(archive_file, 'wt') as f:
            f.write("test data")

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            with patch.object(service.config, 'HOT_DATA_PATH', '/nonexistent.db'):
                with patch.object(service.config, 'WARM_DATA_PATH', '/nonexistent_warm.db'):
                    stats = service.get_archive_stats(MagicMock())

        assert len(stats["by_tier"]["cold"]["files"]) == 1
        assert stats["storage"]["cold_archive_size"] > 0

    def test_get_archive_stats_hot_warm_exist(self, service, temp_archive_dir):
        """测试获取归档统计 - 热/温数据库文件存在"""
        hot_file = Path(temp_archive_dir) / "hot.db"
        hot_file.write_text("hot data")
        warm_file = Path(temp_archive_dir) / "warm.db"
        warm_file.write_text("warm data")

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            with patch.object(service.config, 'HOT_DATA_PATH', str(hot_file)):
                with patch.object(service.config, 'WARM_DATA_PATH', str(warm_file)):
                    stats = service.get_archive_stats(MagicMock())

        assert stats["storage"]["hot_db_size"] > 0
        assert stats["storage"]["warm_db_size"] > 0

    def test_archive_records_no_records(self, service):
        """测试归档记录 - 无记录"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 0

        class MockModel:
            created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value = mock_query

        count, message = service.archive_records(mock_db, MockModel)

        assert count == 0
        assert "没有需要归档的记录" in message

    def test_archive_records_without_before_date(self, service):
        """测试归档记录 - 未指定日期"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 0

        class MockModel:
            created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value = mock_query

        count, message = service.archive_records(mock_db, MockModel, before_date=None)

        assert count == 0
        assert "没有需要归档的记录" in message

    def test_archive_records_to_warm(self, service):
        """测试归档记录到温存储"""
        mock_db = MagicMock()
        mock_record = MagicMock()
        mock_record.is_archived = False
        mock_record.id = 1

        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.limit.return_value.all.return_value = [mock_record]
        mock_db.query.return_value.filter.return_value = mock_query

        class MockModel:
            created_at = datetime.utcnow() - timedelta(days=500)

        before_date = datetime.utcnow() - timedelta(days=500)

        count, message = service.archive_records(
            mock_db, MockModel, before_date=before_date, batch_size=1000
        )

        assert count == 1
        assert "warm" in message or "温" in message

    def test_archive_records_to_warm_no_is_archived(self, service):
        """模型无 is_archived 列时必须如实返回 0（2026-09-30 深审修复）。

        原用例用 MagicMock 记录（自动生成任意属性）并断言 count == 1，固化了
        "什么都没改也上报成功归档"这一静默失效行为；改用真实对象后断言诚实计数。
        """
        from types import SimpleNamespace

        mock_db = MagicMock()
        mock_record = SimpleNamespace(id=1)  # 无 is_archived 属性（全仓模型皆如此）

        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.limit.return_value.all.return_value = [mock_record]
        mock_db.query.return_value.filter.return_value = mock_query

        class MockModel:
            created_at = datetime.utcnow() - timedelta(days=500)

        before_date = datetime.utcnow() - timedelta(days=500)

        count, message = service.archive_records(
            mock_db, MockModel, before_date=before_date, batch_size=1000
        )

        assert count == 0, "没有真正迁移任何记录时不得上报成功归档"
        assert "warm" in message
        mock_db.commit.assert_not_called()

    def test_archive_records_exception(self, service):
        """测试归档记录 - 异常处理"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1

        class MockModel:
            created_at = datetime.utcnow() - timedelta(days=500)

        mock_db.query.return_value.filter.return_value = mock_query

        with patch.object(service, '_archive_to_warm_storage',
                          side_effect=Exception("Archive error")):
            count, message = service.archive_records(
                mock_db, MockModel, before_date=datetime.utcnow() - timedelta(days=500)
            )

        assert count == 0
        assert "归档失败" in message

    def test_archive_to_cold_full_flow(self, service, temp_archive_dir):
        """测试归档到冷存储 - 完整流程"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1

        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.test_field = "value1"
        mock_record.__table__ = MagicMock()
        col = MagicMock()
        col.name = "test_field"
        mock_record.__table__.columns = [col]

        mock_query.limit.return_value.all.return_value = [mock_record]
        mock_query.filter.return_value.delete.return_value = 1
        mock_db.query.return_value.filter.return_value = mock_query

        class MockModel:
            __name__ = "MockModel"

        MockModel.created_at = datetime(2000, 1, 1)
        MockModel.id = MagicMock()
        MockModel.id.in_.return_value = "mock_filter"

        before_date = datetime.utcnow() - timedelta(days=1500)

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.archive_records(
                mock_db, MockModel, before_date=before_date, batch_size=1000
            )

        assert count == 1
        assert "cold" in message or "冷" in message
        mock_db.commit.assert_called()
        mock_query.filter.assert_called_once()

    def test_archive_to_cold_compression_disabled(self, service, temp_archive_dir):
        """测试归档到冷存储 - 禁用压缩"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1

        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.test_field = "value1"
        mock_record.__table__ = MagicMock()
        col = MagicMock()
        col.name = "test_field"
        mock_record.__table__.columns = [col]

        mock_query.limit.return_value.all.return_value = [mock_record]
        mock_query.filter.return_value.delete.return_value = 1
        mock_db.query.return_value.filter.return_value = mock_query

        class MockModel:
            __name__ = "MockModel"

        MockModel.created_at = datetime(2000, 1, 1)
        MockModel.id = MagicMock()
        MockModel.id.in_.return_value = "mock_filter"

        before_date = datetime.utcnow() - timedelta(days=1500)

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            with patch.object(service.config, 'COMPRESSION_ENABLED', False):
                count, message = service.archive_records(
                    mock_db, MockModel, before_date=before_date, batch_size=1000
                )

        assert count == 1
        json_files = list(Path(temp_archive_dir).glob("*.json"))
        assert len(json_files) > 0

    def test_archive_to_cold_empty_records(self, service, temp_archive_dir):
        """测试归档到冷存储 - 无记录"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.limit.return_value.all.return_value = []

        mock_db.query.return_value.filter.return_value = mock_query

        class MockModel:
            created_at = datetime.utcnow() - timedelta(days=1500)

        before_date = datetime.utcnow() - timedelta(days=1500)

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.archive_records(
                mock_db, MockModel, before_date=before_date, batch_size=1000
            )

        assert count == 0
        assert "cold" in message or "冷" in message or "归档" in message

    def test_model_to_dict(self, service):
        """测试模型转字典"""
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock()
        mock_column = MagicMock()
        mock_column.name = "test_field"
        mock_model.__table__.columns = [mock_column]
        mock_model.test_field = "test_value"

        result = service._model_to_dict(mock_model)

        assert result["test_field"] == "test_value"

    def test_model_to_dict_datetime(self, service):
        """测试模型转字典 - datetime 字段"""
        mock_model = MagicMock()
        mock_model.__table__ = MagicMock()
        mock_column = MagicMock()
        mock_column.name = "created_at"
        mock_model.__table__.columns = [mock_column]

        test_datetime = datetime(2024, 1, 1, 12, 0, 0)
        mock_model.created_at = test_datetime

        result = service._model_to_dict(mock_model)

        assert result["created_at"] == test_datetime.isoformat()

    def test_restore_from_archive_file_not_exists(self, service):
        """测试从归档恢复 - 文件不存在"""
        mock_db = MagicMock()

        count, message = service.restore_from_archive(mock_db, MagicMock(), "nonexistent.gz")

        assert count == 0
        assert "不存在" in message

    def test_restore_from_archive_success(self, service, temp_archive_dir):
        """测试从归档恢复成功"""
        mock_db = MagicMock()

        test_data = [{"id": 1, "name": "Test", "created_at": "2024-01-01T00:00:00"}]
        archive_path = Path(temp_archive_dir) / "test_restore.gz"
        with gzip.open(archive_path, 'wt') as f:
            json.dump(test_data, f)

        mock_model_class = MagicMock()

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.restore_from_archive(
                mock_db, mock_model_class, "test_restore.gz"
            )

        assert count == 1
        assert "成功恢复" in message
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_restore_from_archive_with_record_ids(self, service, temp_archive_dir):
        """测试从归档恢复 - 指定记录ID"""
        mock_db = MagicMock()

        test_data = [
            {"id": 1, "name": "Test1"},
            {"id": 2, "name": "Test2"},
        ]
        archive_path = Path(temp_archive_dir) / "test_restore.gz"
        with gzip.open(archive_path, 'wt') as f:
            json.dump(test_data, f)

        mock_model_class = MagicMock()

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.restore_from_archive(
                mock_db, mock_model_class, "test_restore.gz", record_ids=[1]
            )

        assert count == 1

    def test_restore_from_archive_non_gz(self, service, temp_archive_dir):
        """测试从归档恢复 - 非压缩文件"""
        mock_db = MagicMock()

        test_data = [{"id": 1, "name": "Test", "created_at": "2024-01-01T00:00:00"}]
        archive_path = Path(temp_archive_dir) / "test_restore.json"
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        mock_model_class = MagicMock()

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.restore_from_archive(
                mock_db, mock_model_class, "test_restore.json"
            )

        assert count == 1
        assert "成功恢复" in message
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_restore_from_archive_record_exception(self, service, temp_archive_dir):
        """测试从归档恢复 - 单条记录恢复失败"""
        mock_db = MagicMock()

        test_data = [
            {"id": 1, "name": "Good"},
            {"id": 2, "name": "Bad"},
        ]
        archive_path = Path(temp_archive_dir) / "test_mixed.gz"
        with gzip.open(archive_path, 'wt') as f:
            json.dump(test_data, f)

        call_count = [0]

        def mock_constructor(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Insert failed")
            return MagicMock()

        mock_model_class = MagicMock()
        mock_model_class.side_effect = mock_constructor

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.restore_from_archive(
                mock_db, mock_model_class, "test_mixed.gz"
            )

        assert count == 1
        assert "成功恢复" in message

    def test_restore_from_archive_exception(self, service, temp_archive_dir):
        """测试从归档恢复异常处理"""
        mock_db = MagicMock()

        mock_db.commit.side_effect = Exception("DB Error")

        test_data = [{"id": 1, "name": "Test"}]
        archive_path = Path(temp_archive_dir) / "test_restore.gz"
        with gzip.open(archive_path, 'wt') as f:
            json.dump(test_data, f)

        mock_model_class = MagicMock()

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.restore_from_archive(
                mock_db, mock_model_class, "test_restore.gz"
            )

        assert count == 0
        assert "失败" in message or "error" in message.lower()
        # safe_commit 内部回滚 + 外层回滚
        assert mock_db.rollback.call_count >= 1

    def test_cleanup_old_archives_no_directory(self, service):
        """测试清理旧归档 - 目录不存在"""
        with patch.object(service.config, 'COLD_ARCHIVE_PATH', '/nonexistent'):
            count, message = service.cleanup_old_archives()

        assert count == 0
        assert "不存在" in message

    def test_cleanup_old_archives_with_files(self, service, temp_archive_dir):
        """测试清理旧归档 - 有过期文件"""
        old_file = Path(temp_archive_dir) / "old_archive.gz"
        with gzip.open(old_file, 'wt') as f:
            f.write("old data")

        old_time = (datetime.utcnow() - timedelta(days=1000)).timestamp()
        os.utime(old_file, (old_time, old_time))

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.cleanup_old_archives(max_age_days=365)

        assert count == 1
        assert old_file.exists() is False

    def test_cleanup_old_archives_no_old_files(self, service, temp_archive_dir):
        """测试清理旧归档 - 无过期文件"""
        new_file = Path(temp_archive_dir) / "new_archive.gz"
        with gzip.open(new_file, 'wt') as f:
            f.write("new data")

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            count, message = service.cleanup_old_archives(max_age_days=365)

        assert count == 0
        assert new_file.exists() is True

    def test_cleanup_old_archives_file_error(self, service, temp_archive_dir):
        """测试清理旧归档 - 文件删除异常"""
        archive_file = Path(temp_archive_dir) / "bad_archive.gz"
        with gzip.open(archive_file, 'wt') as f:
            f.write("data")

        old_time = (datetime.utcnow() - timedelta(days=1000)).timestamp()
        os.utime(archive_file, (old_time, old_time))

        with patch.object(service.config, 'COLD_ARCHIVE_PATH', temp_archive_dir):
            with patch.object(Path, 'unlink', side_effect=Exception("Permission denied")):
                count, message = service.cleanup_old_archives(max_age_days=365)

        assert count == 0

    def test_get_storage_summary(self, service):
        """测试获取存储摘要"""
        with patch.object(service, 'get_archive_stats') as mock_stats:
            mock_stats.return_value = {
                "storage": {
                    "hot_db_size": 1000,
                    "warm_db_size": 500,
                    "cold_archive_size": 200
                }
            }

            summary = service.get_storage_summary()

        assert "generated_at" in summary
        assert "tiers" in summary
        assert "storage_sizes" in summary
        assert "recommendations" in summary

    def test_get_storage_summary_high_hot_ratio(self, service):
        """测试获取存储摘要 - 高热数据比例"""
        with patch.object(service, 'get_archive_stats') as mock_stats:
            mock_stats.return_value = {
                "storage": {
                    "hot_db_size": 1000000,
                    "warm_db_size": 100,
                    "cold_archive_size": 100
                }
            }

            summary = service.get_storage_summary()

        assert len(summary["recommendations"]) > 0

    def test_get_storage_summary_large_cold(self, service):
        """测试获取存储摘要 - 大冷数据"""
        with patch.object(service, 'get_archive_stats') as mock_stats:
            mock_stats.return_value = {
                "storage": {
                    "hot_db_size": 100,
                    "warm_db_size": 100,
                    "cold_archive_size": 2 * 1024 * 1024 * 1024
                }
            }

            summary = service.get_storage_summary()

        assert len(summary["recommendations"]) > 0

    def test_get_storage_summary_zero_total(self, service):
        """测试获取存储摘要 - 总大小为零"""
        with patch.object(service, 'get_archive_stats') as mock_stats:
            mock_stats.return_value = {
                "storage": {
                    "hot_db_size": 0,
                    "warm_db_size": 0,
                    "cold_archive_size": 0
                }
            }

            summary = service.get_storage_summary()

        assert summary["storage_sizes"]["hot_db_size"] == 0
        assert len(summary["recommendations"]) == 0

class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from app.services.data_tier_service import data_tier_service
        assert data_tier_service is not None

    def test_global_instance_is_service(self):
        """测试全局实例是服务类型"""
        from app.services.data_tier_service import data_tier_service, DataTierService
        assert isinstance(data_tier_service, DataTierService)
