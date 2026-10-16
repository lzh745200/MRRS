"""系统域端点门禁与信息泄露修复验证（R27：M4/M5/M6/M7/M8/M15）

覆盖六条缺陷的回归锁：
- M4 system_health.py：overview/disk-space/table-stats 管理员门禁；
  db_file 不回吐绝对路径；overview 异常不回显 str(e)。
- M5 system/system.py：/system/environment 管理员门禁。
- M6 system/tasks.py：cancel/delete「本人或管理员」；running/count 认证；
  create_task task_type 枚举校验。
- M7 system/metrics.py：database 指标不回吐路径/表名；异常固定文案；
  history 失败 success=False。
- M8 system/health.py：/health/full 不再是 async（重 I/O 卸载线程池）。
- M15 system/monitor.py：alerts/alerts/history 管理员门禁；异常 warning 级日志。
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, BackgroundTasks
from fastapi.testclient import TestClient


# ==================== 通用用户构造 ====================


def _make_user(role="user", is_superuser=False, username="bob"):
    """显式属性用户（SimpleNamespace，避免 MagicMock 自动属性干扰判权口径）。"""
    return SimpleNamespace(
        id=2,
        username=username,
        role=role,
        is_superuser=is_superuser,
        is_active=True,
    )


def _plain_user():
    return _make_user(role="user", is_superuser=False, username="bob")


def _admin_user():
    return _make_user(role="super_admin", is_superuser=True, username="root")


def _mock_db():
    db = MagicMock()
    db.execute.return_value = db
    return db


def _mini_client(router, user, mock_db=None):
    """按模块路由构建独立测试应用，按需覆盖认证/数据库依赖。"""
    from app.core.database import get_db
    from app.core.security import get_current_user

    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if mock_db is not None:
        app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


# ==================== M4: system_health ====================


class TestM4SystemHealthGates:
    @pytest.fixture
    def router(self):
        from app.api.v1.system_health import router

        return router

    def test_overview_requires_admin(self, router):
        client = _mini_client(router, _plain_user(), _mock_db())
        assert client.get("/system-health/overview").status_code == 403

    def test_disk_space_requires_admin(self, router):
        client = _mini_client(router, _plain_user(), _mock_db())
        assert client.get("/system-health/disk-space").status_code == 403

    def test_table_stats_requires_admin(self, router):
        client = _mini_client(router, _plain_user(), _mock_db())
        assert client.get("/system-health/table-stats").status_code == 403

    def test_admin_still_reads_overview(self, router):
        """超管不回归：门禁后管理员仍可读概览。"""
        db = _mock_db()
        db.fetchall.return_value = [(1,)]
        db.fetchone.return_value = ["wal"]
        client = _mini_client(router, _admin_user(), db)
        with patch("app.api.v1.system_health._check_disk_space", return_value={
            "status": "ok", "message": "ok", "free_gb": 50, "total_gb": 100, "used_percent": 50
        }), patch("app.api.v1.system_health._get_db_file_info", return_value={
            "status": "ok", "size_mb": 10, "message": "ok"
        }), patch("app.api.v1.system_health._check_wal_status", return_value={
            "status": "ok", "message": "ok"
        }):
            resp = client.get("/system-health/overview")
        assert resp.status_code == 200
        assert resp.json()["data"]["overall_status"] == "ok"

    def test_admin_still_reads_disk_space(self, router):
        client = _mini_client(router, _admin_user(), _mock_db())
        with patch("app.api.v1.system_health._check_disk_space", return_value={
            "status": "ok", "free_gb": 50, "total_gb": 200
        }):
            resp = client.get("/system-health/disk-space")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ok"

    def test_admin_still_reads_table_stats(self, router):
        db = _mock_db()
        db.fetchall.return_value = [("users",), ("villages",)]
        db.scalar.return_value = 100
        client = _mini_client(router, _admin_user(), db)
        resp = client.get("/system-health/table-stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_tables"] == 2

    def test_db_file_info_no_path_leak(self):
        """_get_db_file_info 不再回吐数据库绝对路径（保留 size 等聚合字段）。"""
        from app.api.v1.system_health import _get_db_file_info

        db = _mock_db()
        db.fetchone.return_value = ["main", "/", "C:/data/secret_rural.db"]
        with patch("os.path.exists", return_value=True), patch(
            "os.path.getsize", return_value=10485760
        ), patch("os.path.getmtime", return_value=1700000000):
            result = _get_db_file_info(db)
        assert "path" not in result
        assert "secret_rural.db" not in str(result)
        assert result["status"] == "ok"
        assert result["size_mb"] == 10.0

    def test_overview_db_error_no_str_leak(self, router):
        """overview 数据库异常不再把 str(e) 原文回显给客户端。"""
        db = _mock_db()
        db.execute.side_effect = Exception("secret-dialect-error /hidden/path.db")
        client = _mini_client(router, _admin_user(), db)
        with patch("app.api.v1.system_health._check_disk_space", return_value={
            "status": "ok", "message": "ok"
        }), patch("app.api.v1.system_health._get_db_file_info", return_value={
            "status": "ok", "size_mb": 0, "message": "ok"
        }), patch("app.api.v1.system_health._check_wal_status", return_value={
            "status": "ok", "message": "ok"
        }):
            resp = client.get("/system-health/overview")
        assert resp.status_code == 200
        msg = resp.json()["data"]["checks"]["database"]["message"]
        assert "secret-dialect-error" not in msg
        assert "/hidden/path.db" not in msg


# ==================== M5: system/environment ====================


class TestM5EnvironmentGate:
    @pytest.fixture
    def router(self):
        from app.api.v1.system.system import router

        return router

    def test_environment_requires_admin(self, router):
        client = _mini_client(router, _plain_user())
        assert client.get("/system/environment").status_code == 403

    def test_environment_requires_auth(self, router):
        client = _mini_client(router, None)
        assert client.get("/system/environment").status_code == 401

    def test_admin_still_reads_environment(self, router):
        """超管不回归：管理员仍可读运行环境详情。"""
        client = _mini_client(router, _admin_user())
        resp = client.get("/system/environment")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "python_version" in data
        assert "packages" in data


# ==================== M6: system/tasks ====================


class TestM6TasksOwnershipAndAuth:
    BASE = "/api/v1/system/tasks"

    @pytest.fixture(autouse=True)
    def _clean_tasks(self):
        import app.api.v1.system.tasks as tasks_mod

        tasks_mod._tasks.clear()
        yield
        tasks_mod._tasks.clear()

    @pytest.fixture
    def app_overrides(self):
        from app.main import app
        from app.core.security import get_current_user

        original = app.dependency_overrides.copy()
        yield app, get_current_user
        app.dependency_overrides = original

    def _client(self, app_overrides, user):
        app, get_current_user = app_overrides
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app, raise_server_exceptions=False)

    def _seed(self, task_id="t1", status="completed", created_by="alice"):
        import app.api.v1.system.tasks as tasks_mod
        from datetime import datetime, timezone

        rec = {
            "task_id": task_id,
            "task_type": "backup",
            "task_name": f"任务{task_id}",
            "status": status,
            "progress": 100.0,
            "message": "m",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "created_by": created_by,
            "params": {},
            "result": None,
        }
        tasks_mod._tasks[task_id] = rec
        return rec

    def test_running_count_requires_auth(self, app_overrides):
        """running/count 此前完全无认证依赖，修复后未登录必须 401。"""
        client = self._client(app_overrides, None)
        assert client.get(f"{self.BASE}/running/count").status_code == 401

    def test_running_count_logged_in_ok(self, app_overrides):
        self._seed("e1", status="running")
        client = self._client(app_overrides, _plain_user())
        resp = client.get(f"{self.BASE}/running/count")
        assert resp.status_code == 200
        assert resp.json()["data"]["running"] == 1

    def test_cancel_other_user_task_forbidden(self, app_overrides):
        """非本人非管理员取消他人任务必须 403（修复前仅登录即可操作）。"""
        self._seed("c1", status="running", created_by="alice")
        client = self._client(app_overrides, _plain_user())
        resp = client.post(f"{self.BASE}/c1/cancel")
        assert resp.status_code == 403

    def test_cancel_own_task_ok(self, app_overrides):
        self._seed("c2", status="running", created_by="bob")
        client = self._client(app_overrides, _plain_user())
        resp = client.post(f"{self.BASE}/c2/cancel")
        assert resp.status_code == 200

    def test_admin_can_cancel_any_task(self, app_overrides):
        """超管不回归：管理员可取消任意用户的任务。"""
        self._seed("c3", status="running", created_by="alice")
        client = self._client(app_overrides, _admin_user())
        resp = client.post(f"{self.BASE}/c3/cancel")
        assert resp.status_code == 200

    def test_delete_other_user_task_forbidden(self, app_overrides):
        self._seed("d1", status="completed", created_by="alice")
        client = self._client(app_overrides, _plain_user())
        resp = client.delete(f"{self.BASE}/d1")
        assert resp.status_code == 403

    def test_delete_own_task_ok(self, app_overrides):
        self._seed("d2", status="completed", created_by="bob")
        client = self._client(app_overrides, _plain_user())
        resp = client.delete(f"{self.BASE}/d2")
        assert resp.status_code == 200

    def test_admin_can_delete_any_task(self, app_overrides):
        self._seed("d3", status="completed", created_by="alice")
        client = self._client(app_overrides, _admin_user())
        resp = client.delete(f"{self.BASE}/d3")
        assert resp.status_code == 200

    def test_create_task_rejects_unknown_type(self, app_overrides):
        """task_type 必须落在 TaskType 枚举内（修复前任意字符串可建任务）。"""
        client = self._client(app_overrides, _plain_user())
        with patch.object(BackgroundTasks, "add_task", MagicMock()):
            resp = client.post(
                self.BASE,
                json={"task_type": "demo", "task_name": "非法类型"},
            )
        assert resp.status_code == 400

    def test_create_task_accepts_enum_type(self, app_overrides):
        client = self._client(app_overrides, _plain_user())
        with patch.object(BackgroundTasks, "add_task", MagicMock()):
            resp = client.post(
                self.BASE,
                json={"task_type": "backup", "task_name": "合法类型"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["task_id"]


# ==================== M7: system/metrics ====================


class TestM7MetricsNoLeak:
    @pytest.fixture
    def router(self):
        from app.api.v1.system.metrics import router

        return router

    def test_database_metrics_no_path_leak(self, router):
        db = _mock_db()
        db.get_bind = MagicMock(return_value=MagicMock())
        db.execute.return_value.scalar.return_value = 0
        client = _mini_client(router, _admin_user(), db)
        with patch("app.utils.paths.get_database_path") as gdp:
            p = MagicMock()
            p.exists.return_value = True
            p.stat.return_value.st_size = 1024
            p.__str__ = lambda s: "C:/secret/hidden_rural.db"
            gdp.return_value = p
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = ["users"]
                resp = client.get("/metrics/database")
        assert resp.status_code == 200
        body = resp.text
        metrics = resp.json()["data"]["metrics"]
        assert "database_file_path" not in metrics
        assert "table_names" not in metrics
        assert "table_names_truncated" not in metrics
        assert "C:/secret/hidden_rural.db" not in body
        # 聚合值保留
        assert "database_file_size_mb" in metrics
        assert metrics["table_count"] == 1

    def test_database_metrics_error_fixed_message(self, router):
        db = _mock_db()
        db.get_bind = MagicMock(return_value=MagicMock())
        db.execute.return_value.scalar.return_value = 0
        client = _mini_client(router, _admin_user(), db)
        with patch("app.utils.paths.get_database_path", side_effect=Exception("secret-conn-err")):
            with patch("sqlalchemy.inspect") as mi:
                mi.return_value.get_table_names.return_value = []
                resp = client.get("/metrics/database")
        metrics = resp.json()["data"]["metrics"]
        assert "database_file_error" in metrics
        assert "secret-conn-err" not in resp.text

    def test_history_failure_marks_success_false(self, router):
        db = _mock_db()
        db.query = MagicMock(side_effect=Exception("history-db-err"))
        client = _mini_client(router, _admin_user(), db)
        resp = client.get("/metrics/history")
        body = resp.json()
        assert body["success"] is False
        assert "history-db-err" not in resp.text
        assert "message" in body["data"]


# ==================== M8: system/health /full ====================


class TestM8HealthFullOffEventLoop:
    def test_health_full_is_sync_def(self):
        """/health/full 内含 sqlite3+PRAGMA 重 I/O，必须是同步 def（线程池执行）。"""
        from app.api.v1.system.health import health_full

        assert not asyncio.iscoroutinefunction(health_full)

    def test_health_full_admin_still_ok(self):
        """超管不回归：登录管理员仍可取完整健康报告。"""
        from app.api.v1.system.health import router

        client = _mini_client(router, _admin_user())
        with patch("app.utils.paths.get_database_path") as gdp, patch(
            "app.utils.paths.get_backup_path"
        ) as gbp:
            p = MagicMock()
            p.absolute.return_value = "/nonexistent/db.sqlite"
            gdp.return_value = p
            gbp.return_value = "/nonexistent/backup"
            resp = client.get("/health/full")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200


# ==================== M15: system/monitor alerts ====================


class TestM15MonitorAlerts:
    @pytest.fixture
    def router(self):
        from app.api.v1.system.monitor import router

        return router

    def test_alert_rules_requires_admin(self, router):
        db = _mock_db()
        client = _mini_client(router, _plain_user(), db)
        assert client.get("/monitor/alerts").status_code == 403

    def test_alert_history_requires_admin(self, router):
        db = _mock_db()
        client = _mini_client(router, _plain_user(), db)
        assert client.get("/monitor/alerts/history").status_code == 403

    def test_admin_still_reads_alert_rules(self, router):
        """超管不回归：管理员仍可读告警规则。"""
        from app.models.monitoring import AlertRule

        db = _mock_db()
        q = MagicMock()
        rule = MagicMock(spec=AlertRule)
        rule.id = 1
        rule.name = "CPU"
        rule.metric_type = "cpu_usage"
        rule.threshold = 90.0
        rule.duration_seconds = 60
        rule.enabled = True
        rule.created_at = None
        q.all.return_value = [rule]
        db.query = MagicMock(return_value=q)
        client = _mini_client(router, _admin_user(), db)
        resp = client.get("/monitor/alerts")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_alert_rules_exception_logs_warning(self, router, caplog):
        """规则查询异常必须以 WARNING 级（含堆栈）记录，而非静默 debug。"""
        db = _mock_db()
        db.query = MagicMock(side_effect=Exception("rules-query-err"))
        client = _mini_client(router, _admin_user(), db)
        with caplog.at_level(logging.WARNING, logger="app.api.v1.system.monitor"):
            resp = client.get("/monitor/alerts")
        assert resp.status_code == 200
        warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "rules-query-err" in r.getMessage()
        ]
        assert warnings, "告警规则查询异常应以 WARNING 级别记录"
        assert any(r.exc_info for r in warnings)

    def test_admin_still_reads_alert_history(self, router):
        from app.models.monitoring import AlertHistory

        db = _mock_db()
        q = MagicMock()
        q.count.return_value = 1
        rec = MagicMock(spec=AlertHistory)
        rec.id = 1
        rec.rule_id = 1
        rec.message = "m"
        rec.metric_value = 1.0
        rec.status = "triggered"
        rec.created_at = None
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [rec]
        db.query = MagicMock(return_value=q)
        client = _mini_client(router, _admin_user(), db)
        resp = client.get("/monitor/alerts/history")
        assert resp.status_code == 200

    def test_alert_history_exception_logs_warning(self, router, caplog):
        db = _mock_db()
        db.query = MagicMock(side_effect=Exception("history-query-err"))
        client = _mini_client(router, _admin_user(), db)
        with caplog.at_level(logging.WARNING, logger="app.api.v1.system.monitor"):
            resp = client.get("/monitor/alerts/history")
        assert resp.status_code == 200
        warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "history-query-err" in r.getMessage()
        ]
        assert warnings, "告警历史查询异常应以 WARNING 级别记录"
        assert any(r.exc_info for r in warnings)
