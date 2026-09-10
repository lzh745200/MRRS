"""
测试 - app.services.database_health_service
覆盖率目标: 100%
"""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

class TestDatabaseHealthService:
    """测试 DatabaseHealthService"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        from app.services.database_health_service import DatabaseHealthService
        return DatabaseHealthService()

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE INDEX idx_test ON test_table(name)")
        conn.commit()
        conn.close()

        yield db_path

        import os
        try:
            os.unlink(db_path)
        except:
            pass

    def test_service_creation(self, service):
        """测试服务创建"""
        assert service is not None
        assert service.monitoring is False
        assert service.stats is not None
        assert service.health_status is not None

    def test_get_db_path(self, service):
        """测试获取数据库路径"""
        path = service._get_db_path()
        assert isinstance(path, Path)

    def test_get_db_path_non_sqlite(self, service):
        """测试获取数据库路径 - 非SQLite数据库"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.DATABASE_URL = "postgresql://localhost:5432/db"
            path = service._get_db_path()
        assert "data" in str(path)
        assert "rural_revitalization" in str(path)

    def test_get_db_path_exception(self, service):
        """测试获取数据库路径 - 异常处理"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.DATABASE_URL = None
            path = service._get_db_path()
        assert "data" in str(path)
        assert "rural_revitalization" in str(path)

    def test_check_integrity_no_db(self, service):
        """测试完整性检查 - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.check_integrity()
            assert result["status"] == "error"
            assert "不存在" in result["message"]

    def test_check_integrity_with_db(self, service, temp_db):
        """测试完整性检查 - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.check_integrity()
            assert result["status"] == "healthy"

    def test_check_integrity_failure(self, service, temp_db):
        """测试完整性检查 - 数据库损坏"""
        with patch.object(service, 'db_path', Path(temp_db)):
            with patch('sqlite3.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = ("not ok", "database corruption detected")
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                result = service.check_integrity()

        assert result["status"] == "error"
        assert service.stats["integrity_errors"] > 0
        assert service.health_status["status"] == "error"

    def test_check_integrity_exception(self, service):
        """测试完整性检查异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.check_integrity()
                assert result["status"] == "error"
                assert service.stats["integrity_errors"] > 0

    def test_quick_check_no_db(self, service):
        """测试快速检查 - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.quick_check()
            assert result["status"] == "error"

    def test_quick_check_with_db(self, service, temp_db):
        """测试快速检查 - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.quick_check()
            assert result["status"] == "ok"
            assert "db_size" in result
            assert "table_count" in result

    def test_quick_check_exception(self, service):
        """测试快速检查异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.quick_check()
                assert result["status"] == "error"

    def test_vacuum_database_no_db(self, service):
        """测试 VACUUM - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.vacuum_database()
            assert result["status"] == "error"

    def test_vacuum_database_with_db(self, service, temp_db):
        """测试 VACUUM - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.vacuum_database()
            assert result["status"] == "ok"
            assert "size_before" in result
            assert "size_after" in result

    def test_vacuum_database_exception(self, service):
        """测试 VACUUM 异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.vacuum_database()
                assert result["status"] == "error"

    def test_check_indexes_no_db(self, service):
        """测试检查索引 - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.check_indexes()
            assert result["status"] == "error"

    def test_check_indexes_with_db(self, service, temp_db):
        """测试检查索引 - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.check_indexes()
            assert result["status"] == "ok"
            assert result["index_count"] == 1

    def test_check_indexes_with_issues(self, service, temp_db):
        """测试检查索引 - 索引异常"""
        with patch.object(service, 'db_path', Path(temp_db)):
            with patch('sqlite3.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.side_effect = [
                    [("idx_test",)],
                    None,
                ]
                execute_side_effect = [
                    None,
                    Exception("Index corruption"),
                ]
                mock_cursor.execute.side_effect = execute_side_effect
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn

                result = service.check_indexes()

        assert result["status"] == "warning"
        assert len(result["issues"]) > 0

    def test_check_indexes_exception(self, service):
        """测试检查索引异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.check_indexes()
                assert result["status"] == "error"

    def test_analyze_database_no_db(self, service):
        """测试分析数据库 - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.analyze_database()
            assert result["status"] == "error"

    def test_analyze_database_with_db(self, service, temp_db):
        """测试分析数据库 - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.analyze_database()
            assert result["status"] == "ok"

    def test_analyze_database_exception(self, service):
        """测试分析数据库异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.analyze_database()
                assert result["status"] == "error"

    def test_get_database_info_no_db(self, service):
        """测试获取数据库信息 - 数据库不存在"""
        with patch.object(service, 'db_path', Path('/nonexistent/db.db')):
            result = service.get_database_info()
            assert result["status"] == "error"

    def test_get_database_info_with_db(self, service, temp_db):
        """测试获取数据库信息 - 正常数据库"""
        with patch.object(service, 'db_path', Path(temp_db)):
            result = service.get_database_info()
            assert result["status"] == "ok"
            assert "db_size" in result
            assert "table_count" in result
            assert "index_count" in result
            assert result["fragmentation"] >= 0

    def test_get_database_info_exception(self, service):
        """测试获取数据库信息异常处理"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.get_database_info()
                assert result["status"] == "error"

    def test_get_health_status(self, service):
        """测试获取健康状态"""
        result = service.get_health_status()
        assert "status" in result
        assert "stats" in result
        assert "monitoring" in result

    def test_get_stats(self, service):
        """测试获取统计信息"""
        result = service.get_stats()
        assert isinstance(result, dict)
        assert "integrity_errors" in result

    def test_start_monitoring(self, service):
        """测试启动监控"""
        service._monitor_loop = MagicMock()
        service.start_monitoring()
        assert service.monitoring is True
        service.stop_monitoring()

    def test_start_monitoring_already_running(self, service):
        """测试启动监控 - 已在运行"""
        service.monitoring = True
        service.start_monitoring()
        assert service.monitoring is True

    def test_stop_monitoring(self, service):
        """测试停止监控"""
        service._monitor_loop = MagicMock()
        service.start_monitoring()
        service.stop_monitoring()
        assert service.monitoring is False

    def test_stop_monitoring_no_thread(self, service):
        """测试停止监控 - 无线程"""
        service.monitor_thread = None
        service.monitoring = True
        service.stop_monitoring()
        assert service.monitoring is False

    def test_monitor_loop_triggers_checks(self, service):
        """测试监控循环触发所有检查"""
        with patch.object(service, 'check_integrity') as mock_ci:
            with patch.object(service, 'quick_check') as mock_qc:
                with patch.object(service, 'vacuum_database') as mock_vd:
                    with patch.object(service, 'checkpoint_wal') as mock_wc:
                        service.integrity_check_interval = 0
                        service.quick_check_interval = 0
                        service.vacuum_interval = 0
                        service.wal_checkpoint_interval = 0

                        # 使用 Event.set() 终止循环（而非 monitoring=False）
                        service._stop_event.clear()

                        def stop_after_one(*args):
                            service._stop_event.set()

                        with patch.object(service._stop_event, 'wait',
                                          side_effect=stop_after_one) as mock_wait:
                            service._monitor_loop()

                        mock_ci.assert_called_once()
                        mock_qc.assert_called_once()
                        mock_vd.assert_called_once()
                        mock_wc.assert_called_once()
                        mock_wait.assert_called()

    def test_monitor_loop_exception_handling(self, service):
        """测试监控循环异常处理"""
        service.check_integrity = MagicMock(side_effect=Exception("DB Crash"))
        service.quick_check = MagicMock()
        service.vacuum_database = MagicMock()
        service.integrity_check_interval = 0

        service._stop_event.clear()

        def stop_after_one(*args):
            service._stop_event.set()

        with patch.object(service._stop_event, 'wait',
                          side_effect=stop_after_one) as mock_wait:
            service._monitor_loop()

        service.check_integrity.assert_called()
        mock_wait.assert_called()

    def test_monitor_loop_datetime_min_initial(self, service):
        """测试监控循环 - datetime.min初始值导致首次全触发

        datetime.min 距 now() 极远，三档检查（integrity / quick / vacuum）
        首次进入循环时条件全部成立，应当都被各调用一次。
        关键点：stop_event 必须在 *三个检查都跑完后* 才置位；
        通过让 Event.wait() 第一次返回后置位 stop_event 来终止循环，
        而非用 check_integrity 的 side_effect 提前置位（那样会令第 2、3 个
        if 中的 `not self._stop_event.is_set()` 为 False，跳过后续检查）。
        """
        with patch.object(service, 'check_integrity') as mock_ci:
            with patch.object(service, 'quick_check') as mock_qc:
                with patch.object(service, 'vacuum_database') as mock_vd:
                    with patch.object(service, 'checkpoint_wal') as mock_wc:
                        service.integrity_check_interval = 86400
                        service.quick_check_interval = 3600
                        service.vacuum_interval = 604800
                        service.wal_checkpoint_interval = 3600

                        service._stop_event.clear()

                        def stop_after_full_cycle(*args):
                            # 一轮检查全部跑完后才终止循环，保证三个检查都被触发
                            service._stop_event.set()

                        with patch.object(service._stop_event, 'wait',
                                          side_effect=stop_after_full_cycle):
                            service._monitor_loop()

                        mock_ci.assert_called_once()
                        mock_qc.assert_called_once()
                        mock_vd.assert_called_once()
                        mock_wc.assert_called_once()

class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from app.services.database_health_service import database_health_service
        assert database_health_service is not None

    def test_global_instance_is_service(self):
        """测试全局实例是服务类型"""
        from app.services.database_health_service import database_health_service, DatabaseHealthService
        assert isinstance(database_health_service, DatabaseHealthService)


class TestCheckpointWal:
    """WAL checkpoint 与体积告警（P1-3：防止 -wal 无限膨胀）"""

    @pytest.fixture
    def service(self):
        from app.services.database_health_service import DatabaseHealthService
        return DatabaseHealthService()

    @pytest.fixture
    def temp_db(self, tmp_path):
        db = tmp_path / "wal.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        return db

    def test_no_db(self, service):
        """数据库不存在 → error"""
        with patch.object(service, 'db_path', Path('/nonexistent/wal.db')):
            result = service.checkpoint_wal()
        assert result["status"] == "error"
        assert "不存在" in result["message"]

    def test_ok_without_wal_file(self, service, temp_db):
        """正常库、无 -wal 文件 → ok 且 size_before/after 均为 0，stats 更新"""
        with patch.object(service, 'db_path', temp_db):
            result = service.checkpoint_wal()
        assert result["status"] == "ok"
        assert result["size_before"] == 0
        assert result["size_after"] == 0
        assert service.stats["last_wal_checkpoint"] is not None

    def test_ok_with_wal_file(self, service, temp_db):
        """存在 -wal 文件 → ok 且返回前后体积"""
        wal = Path(str(temp_db) + "-wal")
        wal.write_bytes(b"x" * 512)
        with patch.object(service, 'db_path', temp_db):
            result = service.checkpoint_wal()
        assert result["status"] == "ok"
        assert "size_before" in result and "size_after" in result

    def test_warns_when_wal_oversized(self, service, temp_db, caplog):
        """-wal 超阈值 → 记录 WARNING（此处 mock connect 使 -wal 不被截断）"""
        wal = Path(str(temp_db) + "-wal")
        wal.write_bytes(b"x" * 2048)
        service.wal_size_warning_bytes = 100
        with patch.object(service, 'db_path', temp_db):
            with patch('sqlite3.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = (0, 0, 0)
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_conn
                with caplog.at_level("WARNING"):
                    result = service.checkpoint_wal()
        assert result["status"] == "ok"
        assert "WAL 文件偏大" in caplog.text

    def test_exception_returns_error(self, service):
        """底层异常 → 捕获并返回 error"""
        with patch.object(service, 'db_path', MagicMock(exists=MagicMock(return_value=True))):
            with patch('sqlite3.connect', side_effect=Exception("DB Error")):
                result = service.checkpoint_wal()
        assert result["status"] == "error"
        assert "失败" in result["message"]
