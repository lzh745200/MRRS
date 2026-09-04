"""
Tests for app.api.v1.system.metrics — 100% coverage
"""

import sys
from unittest.mock import patch, MagicMock

import pytest

import builtins

_original_import = builtins.__import__


@pytest.fixture
def auth_client(client):
    from app.core.security import get_current_user
    user = MagicMock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "Admin"
    user.permissions_list = ["*"]
    user.allowed_permissions_list = []
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides.pop(get_current_user, None)


def _make_chain_mock(return_val=None):
    """Make a chainable mock for query().filter().order_by().limit().all()"""
    m = MagicMock()
    m.filter.return_value = m
    m.order_by.return_value = m
    m.limit.return_value = m
    m.offset.return_value = m
    m.all.return_value = return_val or []
    m.count.return_value = len(return_val) if return_val else 0
    m.first.return_value = return_val[0] if return_val else None
    return m


class TestGetSystemMetrics:
    def test_success(self, auth_client):
        resp = auth_client.get("/api/v1/system/metrics")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_psutil_not_installed(self, auth_client):
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("psutil")}
        with patch("builtins.__import__") as mock_imp:
            def side_effect(name, *args, **kwargs):
                if name.startswith("psutil"):
                    raise ImportError(f"No module named '{name}'")
                return _original_import(name, *args, **kwargs)
            mock_imp.side_effect = side_effect
            resp = auth_client.get("/api/v1/system/metrics")
            assert resp.status_code == 200
            assert resp.json()["data"]["resources"]["status"] == "unavailable"
        for k, v in saved.items():
            sys.modules[k] = v

    def test_psutil_error(self, auth_client):
        saved = sys.modules.get("psutil")
        mock_ps = MagicMock()
        mock_ps.cpu_percent.side_effect = Exception("err")
        mock_ps.cpu_count.side_effect = Exception("err")
        sys.modules["psutil"] = mock_ps
        try:
            resp = auth_client.get("/api/v1/system/metrics")
            assert resp.status_code == 200
            assert resp.json()["data"]["resources"]["status"] == "error"
        finally:
            if saved:
                sys.modules["psutil"] = saved

    def test_psutil_error_message_is_generic(self, auth_client):
        """资源采集异常时 message 必须泛化，绝不内插 str(e)（W1 不变量 #6）。

        旧实现 f"获取资源指标失败: {str(e)}" 会把异常原文（可含数据库/服务器路径）
        经响应 message 出站；此测试用含敏感路径的异常消息锁定其不再泄露。
        """
        saved = sys.modules.get("psutil")
        mock_ps = MagicMock()
        mock_ps.cpu_percent.side_effect = Exception("敏感原文 C:\\secret\\rural_revitalization.db")
        sys.modules["psutil"] = mock_ps
        try:
            resp = auth_client.get("/api/v1/system/metrics")
            msg = resp.json()["data"]["resources"]["message"]
            assert msg == "获取资源指标失败，请查看日志"
            assert "敏感原文" not in msg
            assert "rural_revitalization.db" not in msg
        finally:
            if saved:
                sys.modules["psutil"] = saved

    def test_uptime_and_process_error(self, auth_client):
        import psutil as real_psutil
        saved = sys.modules["psutil"]
        mock_ps = MagicMock()
        mock_ps.cpu_percent.return_value = 45
        mock_ps.cpu_count.return_value = 4
        mock_ps.virtual_memory.return_value = real_psutil.virtual_memory()
        mock_ps.disk_usage.return_value = real_psutil.disk_usage("/")
        mock_ps.boot_time.side_effect = Exception("no boot")
        mock_ps.Process.side_effect = Exception("no proc")
        sys.modules["psutil"] = mock_ps
        try:
            resp = auth_client.get("/api/v1/system/metrics")
            assert resp.status_code == 200
            d = resp.json()["data"]
            assert d.get("uptime") == {}
            assert d.get("process") == {}
        finally:
            sys.modules["psutil"] = saved


class TestGetPerformanceMetrics:
    def test_success(self, auth_client):
        resp = auth_client.get("/api/v1/system/metrics/performance")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_warning(self, auth_client):
        saved = sys.modules["psutil"]
        class M:
            @staticmethod
            def cpu_percent(*a, **kw): return 85.0
            @staticmethod
            def virtual_memory(): m = MagicMock(); m.percent = 90.0; return m
            @staticmethod
            def disk_usage(_): d = MagicMock(); d.percent = 85.0; return d
        sys.modules["psutil"] = M
        try:
            resp = auth_client.get("/api/v1/system/metrics/performance")
            assert all(i["status"] == "warning" for i in resp.json()["data"]["indicators"])
        finally:
            sys.modules["psutil"] = saved

    def test_normal(self, auth_client):
        saved = sys.modules["psutil"]
        class M:
            @staticmethod
            def cpu_percent(*a, **kw): return 30.0
            @staticmethod
            def virtual_memory(): m = MagicMock(); m.percent = 30.0; return m
            @staticmethod
            def disk_usage(_): d = MagicMock(); d.percent = 30.0; return d
        sys.modules["psutil"] = M
        try:
            resp = auth_client.get("/api/v1/system/metrics/performance")
            assert all(i["status"] == "normal" for i in resp.json()["data"]["indicators"])
        finally:
            sys.modules["psutil"] = saved

    def test_no_psutil(self, auth_client):
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("psutil")}
        with patch("builtins.__import__") as mock_imp:
            def side_effect(name, *a, **kw):
                if name.startswith("psutil"):
                    raise ImportError
                return _original_import(name, *a, **kw)
            mock_imp.side_effect = side_effect
            resp = auth_client.get("/api/v1/system/metrics/performance")
            assert resp.status_code == 200
            assert resp.json()["data"]["indicators"] == []
        for k, v in saved.items():
            sys.modules[k] = v


class TestGetDatabaseMetrics:
    def _override_db(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        mock_db.get_bind = MagicMock(return_value=MagicMock())
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 0

    def test_success(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = True
            p.stat.return_value.st_size = 1024
            gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = ["users"]
                r = auth_client.get("/api/v1/system/metrics/database")
                assert r.status_code == 200

    def test_no_db_file(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = False; gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = []
                assert auth_client.get("/api/v1/system/metrics/database").status_code == 200

    def test_db_path_error(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path", side_effect=Exception("path")):
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = []
                r = auth_client.get("/api/v1/system/metrics/database")
                assert "database_file_error" in r.json()["data"]["metrics"]

    def test_inspect_error(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = True; p.__str__ = lambda s: "/x"
            p.stat.return_value.st_size = 1024; gdp.return_value = p
            with patch("sqlalchemy.inspect", side_effect=Exception("inspect")):
                r = auth_client.get("/api/v1/system/metrics/database")
                assert "table_count_error" in r.json()["data"]["metrics"]

    def test_row_count_execute_error(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = False; gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = []
                mock_db.execute.side_effect = None
                mock_db.execute.return_value.scalar.return_value = 0
                r = auth_client.get("/api/v1/system/metrics/database")
                assert "key_table_row_counts" in r.json()["data"]["metrics"]

    def test_row_count_table_error(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = False; gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = ["users"]
                mock_db.execute.side_effect = Exception("exec err")
                r = auth_client.get("/api/v1/system/metrics/database")
                assert r.json()["data"]["metrics"]["key_table_row_counts"]["users"] == "N/A"

    def test_row_counts_ok(self, auth_client, mock_db):
        self._override_db(auth_client, mock_db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock(); p.exists.return_value = False; gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = ["users"]
                mock_db.execute = lambda text: MagicMock(scalar=lambda: 5)
                r = auth_client.get("/api/v1/system/metrics/database")
                assert r.json()["data"]["metrics"]["key_table_row_counts"]["users"] == 5


class TestGetMetricsHistory:
    def test_all(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        r = MagicMock()
        r.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        r.host = "h"; r.cpu_usage = 1.0; r.memory_usage = 2.0; r.disk_usage = 3.0
        mock_db.query = MagicMock(return_value=_make_chain_mock([r]))
        resp = auth_client.get("/api/v1/system/metrics/history")
        assert resp.json()["data"]["record_count"] == 1

    def test_filter_types(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        r = MagicMock()
        r.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        r.host = "h"; r.cpu_usage = 1.0; r.memory_usage = 2.0; r.disk_usage = 3.0
        mock_db.query = MagicMock(return_value=_make_chain_mock([r]))

        for mt, key in [("cpu", "cpu_usage"), ("memory", "memory_usage"), ("disk", "disk_usage")]:
            resp = auth_client.get(f"/api/v1/system/metrics/history?metric_type={mt}")
            assert key in resp.json()["data"]["history"][0]

    def test_no_records(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        mock_db.query = MagicMock(return_value=_make_chain_mock([]))
        resp = auth_client.get("/api/v1/system/metrics/history")
        assert resp.json()["data"]["record_count"] == 0

    def test_exception(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        mock_db.query = MagicMock(side_effect=Exception("db err"))
        resp = auth_client.get("/api/v1/system/metrics/history")
        assert "message" in resp.json()["data"]
