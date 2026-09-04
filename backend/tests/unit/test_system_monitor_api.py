"""
Tests for app.api.v1.system.monitor — 100% coverage
"""

import builtins
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


def _make_psutil():
    import types
    psutil = types.ModuleType("psutil")

    def _vb():
        vm = MagicMock()
        vm.percent = 45.0
        vm.used = 8 * 1024 ** 3
        vm.total = 16 * 1024 ** 3
        vm.available = 8 * 1024 ** 3
        return vm

    def _du(path):
        d = MagicMock()
        d.percent = 60.0
        d.used = 100 * 1024 ** 3
        d.total = 250 * 1024 ** 3
        d.free = 150 * 1024 ** 3
        return d

    psutil.cpu_percent = MagicMock(return_value=35.0)
    psutil.cpu_count = MagicMock(return_value=4)
    psutil.virtual_memory = _vb
    psutil.swap_memory = MagicMock(return_value=MagicMock(percent=10.0, total=2 * 1024 ** 3))
    psutil.disk_usage = _du
    psutil.disk_partitions = MagicMock(return_value=[
        MagicMock(device="C:\\", mountpoint="C:\\", fstab="ntfs")])
    psutil.net_io_counters = MagicMock(return_value=MagicMock(
        bytes_sent=500 * 1024 ** 2, bytes_recv=300 * 1024 ** 2))
    psutil.Process = MagicMock(return_value=MagicMock(
        cpu_percent=MagicMock(return_value=12.5),
        memory_info=MagicMock(return_value=MagicMock(rss=200 * 1024 ** 2)),
        num_threads=MagicMock(return_value=8)))
    psutil.cpu_freq = MagicMock(return_value=MagicMock(current=2400.0))
    return psutil



class TestGetMonitorSnapshot:
    def test_success(self, client_with_mocked_auth):
        psutil = _make_psutil()
        with patch.dict("sys.modules", {"psutil": psutil, "platform": MagicMock()}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["status"] == "healthy"
            assert data["data"]["cpu_usage"] == 35.0

    def test_psutil_not_installed(self, client_with_mocked_auth):
        _original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("No module named psutil")
            return _original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["status"] == "limited"
            assert "psutil未安装" in data["data"]["message"]

    def test_psutil_exception(self, client_with_mocked_auth):
        psutil = _make_psutil()
        psutil.cpu_percent.side_effect = RuntimeError("access denied")
        with patch.dict("sys.modules", {"psutil": psutil, "platform": MagicMock()}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["status"] == "error"
            assert "获取监控数据失败" in data["data"]["message"]

    def test_disk_usage_failure_degrades_gracefully(self, client_with_mocked_auth):
        """磁盘读取失败（复现 Linux 上误用 'C:\\' 的 FileNotFoundError）不再拖垮整快照。

        旧行为：disk_usage 抛错被外层 except 吞成 status=error，丢失 CPU/内存/网络并刷 ERROR。
        新行为：磁盘单独 try/except 降级，其余指标照常上报，status 仍 healthy。
        """
        psutil = _make_psutil()

        def _boom(path):
            raise FileNotFoundError(2, "No such file or directory", path)

        psutil.disk_usage = _boom
        with patch.dict("sys.modules", {"psutil": psutil, "platform": MagicMock()}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["status"] == "healthy"
            assert data["cpu_usage"] == 35.0
            assert "disk_usage" not in data

    def test_disk_path_prefers_systemdrive(self, client_with_mocked_auth, monkeypatch):
        """Windows：磁盘路径取 SystemDrive 环境变量，而非硬编码 'C:\\'。"""
        monkeypatch.setenv("SystemDrive", "Z:")
        psutil = _make_psutil()
        seen = {}

        def _rec(path):
            seen["path"] = path
            d = MagicMock()
            d.percent = 60.0
            d.used = 100 * 1024 ** 3
            d.total = 250 * 1024 ** 3
            d.free = 150 * 1024 ** 3
            return d

        psutil.disk_usage = _rec
        with patch.dict("sys.modules", {"psutil": psutil, "platform": MagicMock()}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            assert seen["path"] == "Z:"

    def test_disk_path_falls_back_to_fs_root_without_systemdrive(
        self, client_with_mocked_auth, monkeypatch
    ):
        """非 Windows（SystemDrive 未设置）：回退到文件系统根，绝不硬编码 'C:\\'。

        在 Linux CI 上 os.path.abspath(os.sep) == "/"，可与旧硬编码 "C:\\" 区分。
        """
        monkeypatch.delenv("SystemDrive", raising=False)
        import os as _os

        psutil = _make_psutil()
        seen = {}

        def _rec(path):
            seen["path"] = path
            d = MagicMock()
            d.percent = 60.0
            d.used = 100 * 1024 ** 3
            d.total = 250 * 1024 ** 3
            d.free = 150 * 1024 ** 3
            return d

        psutil.disk_usage = _rec
        with patch.dict("sys.modules", {"psutil": psutil, "platform": MagicMock()}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/snapshot")
            assert resp.status_code == 200
            assert seen["path"] == _os.path.abspath(_os.sep)


class TestGetResourceUsage:
    def test_success(self, client_with_mocked_auth):
        psutil = _make_psutil()
        with patch.dict("sys.modules", {"psutil": psutil}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["health_status"] == "healthy"
            assert data["data"]["cpu"]["percent"] == 35.0

    def test_warnings_degraded(self, client_with_mocked_auth):
        psutil = _make_psutil()
        psutil.cpu_percent.return_value = 95.0
        psutil.virtual_memory = lambda: MagicMock(
            percent=92.0, used=14 * 1024 ** 3, total=16 * 1024 ** 3, available=2 * 1024 ** 3)
        psutil.disk_usage = lambda p: MagicMock(
            percent=30.0, used=50 * 1024 ** 3, total=250 * 1024 ** 3, free=200 * 1024 ** 3)
        with patch.dict("sys.modules", {"psutil": psutil}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["health_status"] == "degraded"
            assert len(data["data"]["health_issues"]) == 2

    def test_unhealthy(self, client_with_mocked_auth):
        psutil = _make_psutil()
        psutil.cpu_percent.return_value = 95.0
        psutil.virtual_memory = lambda: MagicMock(
            percent=95.0, used=15 * 1024 ** 3, total=16 * 1024 ** 3, available=1 * 1024 ** 3)
        psutil.disk_usage = lambda p: MagicMock(
            percent=96.0, used=200 * 1024 ** 3, total=210 * 1024 ** 3, free=10 * 1024 ** 3)
        with patch.dict("sys.modules", {"psutil": psutil}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["health_status"] == "unhealthy"

    def test_disk_partition_exception(self, client_with_mocked_auth):
        psutil = _make_psutil()
        good = MagicMock(mountpoint="D:\\", device="D:\\", fstab="ntfs")
        psutil.disk_partitions.return_value = [MagicMock(mountpoint="C:\\", device="C:\\", fstab="ntfs"), good]

        call_count = 0
        def _disk_usage(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PermissionError("no access")
            return MagicMock(percent=30, total=500**3, used=150**3, free=350**3)

        psutil.disk_usage = _disk_usage
        psutil.cpu_freq = MagicMock(return_value=None)

        with patch.dict("sys.modules", {"psutil": psutil}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            disks = data["data"]["disk"]
            assert len(disks) >= 1, f"Expected at least 1 disk, got {len(disks)}"
            # First partition should have error (PermissionError)
            assert disks[0]["available"] is False
            assert "error" in disks[0]
            # At least one healthy partition exists
            healthy = [d for d in disks if d.get("available", True)]
            assert len(healthy) >= 1, "Expected at least one healthy partition"
            # Healthy partition should have a filesystem string
            assert isinstance(healthy[0].get("filesystem"), str)

    def test_psutil_not_installed(self, client_with_mocked_auth):
        _original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("No module named psutil")
            return _original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["status"] == "limited"
            assert "psutil未安装" in data["data"]["message"]

    def test_psutil_exception(self, client_with_mocked_auth):
        psutil = _make_psutil()
        psutil.cpu_percent.side_effect = RuntimeError("fail")
        with patch.dict("sys.modules", {"psutil": psutil}):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/resources")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["status"] == "error"


class TestGetAlertRules:
    def test_db_rules(self, client_with_mocked_auth):
        from app.core.database import get_db
        from app.models.monitoring import AlertRule

        mock_db = MagicMock()
        q = MagicMock()
        rule = MagicMock(spec=AlertRule)
        rule.id = 1; rule.name = "CPU"; rule.metric_type = "cpu_usage"
        rule.threshold = 90.0; rule.duration_seconds = 60; rule.enabled = True
        rule.created_at = None
        q.all.return_value = [rule]
        mock_db.query = MagicMock(return_value=q)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        assert data["data"]["rules"][0]["name"] == "CPU"

    def test_db_rules_with_created_at(self, client_with_mocked_auth):
        from app.core.database import get_db
        from app.models.monitoring import AlertRule

        mock_db = MagicMock()
        q = MagicMock()
        rule = MagicMock(spec=AlertRule)
        rule.id = 2; rule.name = "MEM"; rule.metric_type = "memory_usage"
        rule.threshold = 85.0; rule.duration_seconds = 60; rule.enabled = True
        rule.created_at = datetime(2026, 1, 1, 12, 0, 0)
        q.all.return_value = [rule]
        mock_db.query = MagicMock(return_value=q)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["rules"][0]["created_at"] == "2026-01-01T12:00:00"

    def test_default_rules(self, client_with_mocked_auth):
        from app.core.database import get_db

        mock_db = MagicMock()
        q = MagicMock()
        q.all.return_value = []
        mock_db.query = MagicMock(return_value=q)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 4

    def test_db_exception(self, client_with_mocked_auth):
        from app.core.database import get_db

        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("db down")
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 4


class TestGetAlertHistory:
    def test_success(self, client_with_mocked_auth):
        from app.core.database import get_db
        from app.models.monitoring import AlertHistory
        from unittest.mock import patch as _patch

        # AlertHistory model lacks created_at column — patch it at class level
        with _patch.object(AlertHistory, "created_at", MagicMock(desc=MagicMock()), create=True):
            mock_db = MagicMock()
            q = MagicMock()
            h = MagicMock(spec=AlertHistory)
            h.id = 1; h.rule_id = 1; h.message = "CPU high"
            h.metric_value = 95.0; h.status = "triggered"
            q.count.return_value = 1
            q.all.return_value = [h]
            q.filter.return_value = q
            q.order_by.return_value = q
            q.offset.return_value = q
            q.limit.return_value = q
            mock_db.query = MagicMock(return_value=q)
            client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

            resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts/history")
            assert resp.status_code == 200
            assert resp.json()["data"]["total"] == 1
            assert resp.json()["data"]["items"][0]["message"] == "CPU high"

    def test_with_status_filter(self, client_with_mocked_auth):
        from app.core.database import get_db
        from app.models.monitoring import AlertHistory
        from unittest.mock import patch as _patch

        with _patch.object(AlertHistory, "created_at", MagicMock(desc=MagicMock()), create=True):
            mock_db = MagicMock()
            q = MagicMock()
            h = MagicMock(spec=AlertHistory)
            h.id = 2; h.rule_id = 1; h.message = "MEM high"
            h.metric_value = 90.0; h.status = "resolved"
            q.count.return_value = 1
            q.all.return_value = [h]
            q.filter.return_value = q
            q.order_by.return_value = q
            q.offset.return_value = q
            q.limit.return_value = q
            mock_db.query = MagicMock(return_value=q)
            client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

            resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts/history?status=resolved")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["items"][0]["message"] == "MEM high"

    def test_empty(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        q = MagicMock()
        q.count.return_value = 0
        q.all.return_value = []
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        mock_db.query = MagicMock(return_value=q)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts/history")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_db_exception(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("fail")
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        resp = client_with_mocked_auth.get("/api/v1/system/monitor/alerts/history")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


class TestGetApiStatistics:
    def test_success(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.middleware.metrics_middleware.metrics_store") as MockStore:
            MockStore.get_summary.return_value = {
                "request_count": 10,
                "error_count": 1,
                "error_rate": 0.1,
                "avg_duration": 0.5,
                "requests_per_second": 1.2,
                "uptime_seconds": 100,
                "top_endpoints": [{"path": "/api/test", "count": 5}],
                "by_method_status": {},
                "slow_requests": [],
                "slow_request_count": 0,
            }
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/api-stats?hours=48")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["request_count"] == 10
            assert data["data"]["period_hours"] == 48
            assert data["data"]["top_endpoints"][0]["path"] == "/api/test"

    def test_service_exception(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.middleware.metrics_middleware.metrics_store.get_summary",
                   side_effect=RuntimeError("no data")):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/api-stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["request_count"] == 0
            assert data["data"]["top_endpoints"] == []


class TestGetDatabaseSize:
    @pytest.fixture(autouse=True)
    def _save_settings(self):
        import app.core.config as cfg
        orig = cfg.settings.DATABASE_URL
        yield
        cfg.settings.DATABASE_URL = orig

    def test_sqlite_parsed_url(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///C:/data/test.db"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=2048):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["size_bytes"] == 2048

    def test_sqlite_simple_url(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///./test.db"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=512):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["data"]["size_bytes"] == 512

    def test_sqlite_url_no_netloc(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///relative/path.db"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=256):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["data"]["size_bytes"] == 256

    def test_sqlite_url_empty_path(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite://"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=128):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_non_sqlite(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "postgresql://localhost/mydb"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_file_not_found(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///C:/nope.db"
        with patch("os.path.exists", return_value=False):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["success"] is False
            assert "数据库文件不存在" in resp.json()["data"]["error"]

    def test_permission_error(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///C:/data/test.db"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", side_effect=PermissionError("denied")):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["success"] is False
            assert "无权限" in resp.json()["data"]["error"]

    def test_general_exception(self, client_with_mocked_auth):
        import app.core.config as cfg
        cfg.settings.DATABASE_URL = "sqlite:///C:/data/test.db"
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", side_effect=OSError("io error")):
            resp = client_with_mocked_auth.get("/api/v1/system/monitor/database-size")
            assert resp.status_code == 200
            assert resp.json()["success"] is False
