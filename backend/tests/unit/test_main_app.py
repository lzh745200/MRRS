import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.main import (
    CachedStaticFiles,
    _check_and_record_version_change,
    _check_required_packages,
    _init_database_tables,
    _load_token_blacklist,
    _migrate_missing_columns,
    _seed_default_admin,
    _sqlite_col_spec,
    _start_approval_reminder,
    _start_database_health_monitoring,
    _start_db_maintenance,
    _start_resource_monitoring,
    _stop_approval_reminder,
    _stop_database_health_monitoring,
    _stop_db_maintenance,
    _stop_resource_monitoring,
    _verify_file_integrity,
    app,
    lifespan,
)


class TestAppCreation:
    def test_app_exists(self):
        assert app.title is not None

    def test_health_route_exists(self):
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_shutdown_route_exists(self):
        routes = [r.path for r in app.routes]
        assert "/api/v1/shutdown" in routes


class TestHealthRoute:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_exposes_migration_state(self, client):
        """迁移未达 head 必须对监控可见（任务#6 风险6：不再静默吞掉）。"""
        with patch.dict(
            "app.main._migration_status",
            {"at_head": False, "head": "rev_head", "error_type": "OperationalError"},
        ):
            resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        # 顶层 status 仍为 ok（迁移失败不致命，自动补列兜底）
        assert body["status"] == "ok"
        assert body["migration"] == {
            "at_head": False,
            "head": "rev_head",
            "error_type": "OperationalError",
        }

    def test_migration_failure_records_only_exception_class_name(self):
        """/health 无需认证，故迁移失败只记异常类名，不得记异常原文。

        原文可能含数据库绝对路径与 SQL 片段；完整细节由 logger.error(exc_info=True)
        留在服务端日志。
        """
        from app.main import _migration_status, _run_alembic_upgrade

        sensitive = "unable to open database file: C:/secret/rural_revitalization.db"
        with patch.dict(
            _migration_status, {"at_head": None, "head": None, "error_type": None}
        ), patch("alembic.command.upgrade", side_effect=RuntimeError(sensitive)), \
                patch("alembic.command.stamp", side_effect=RuntimeError(sensitive)):
            _run_alembic_upgrade()

            # 断言必须在 with 块内：patch.dict 退出时会还原字典内容
            assert _migration_status["at_head"] is False
            assert _migration_status["error_type"] == "RuntimeError"
            # 异常原文与其中的敏感路径均不得进入可出站的状态字典
            assert sensitive not in _migration_status["error_type"]
            assert "secret" not in str(_migration_status)


class TestShutdownRoute:
    def test_from_non_local_forbidden(self, client):
        resp = client.post("/api/v1/shutdown")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_from_local_no_key(self):
        """未配置 INTERNAL_SHUTDOWN_KEY 时应拒绝关闭请求（返回 403）"""
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 8000))
        async with httpx.AsyncClient(transport=transport) as hclient:
            resp = await hclient.post(
                "http://test/api/v1/shutdown",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_from_local_correct_key(self):
        """配置了正确的 INTERNAL_SHUTDOWN_KEY 时应允许关闭"""
        import app.main as main_mod
        original_getenv = os.getenv

        def _mock_getenv(key, default=""):
            if key == "INTERNAL_SHUTDOWN_KEY":
                return "secret"
            return original_getenv(key, default)

        with patch.object(main_mod.os, "getenv", side_effect=_mock_getenv):
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 8000))
            async with httpx.AsyncClient(transport=transport) as hclient:
                with patch("threading.Timer") as mock_timer:
                    resp = await hclient.post(
                        "http://test/api/v1/shutdown",
                        headers={
                            "Content-Type": "application/json",
                            "X-Internal-Shutdown": "secret",
                        },
                    )
                    assert resp.status_code == 200
                    assert resp.json()["status"] == "shutting_down"
                    mock_timer.assert_called_once()

    @pytest.mark.asyncio
    async def test_from_local_wrong_key(self):
        """配置了错误的 INTERNAL_SHUTDOWN_KEY 时应返回 403"""
        import app.main as main_mod
        original_getenv = os.getenv

        def _mock_getenv(key, default=""):
            if key == "INTERNAL_SHUTDOWN_KEY":
                return "secret"
            return original_getenv(key, default)

        with patch.object(main_mod.os, "getenv", side_effect=_mock_getenv):
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 8000))
            async with httpx.AsyncClient(transport=transport) as hclient:
                resp = await hclient.post(
                    "http://test/api/v1/shutdown",
                    headers={
                        "Content-Type": "application/json",
                        "X-Internal-Shutdown": "wrong",
                    },
                )
                assert resp.status_code == 403
                assert "内部密钥验证失败" in resp.json()["detail"]


class TestTrailingSlashRedirect:
    def test_trailing_slash_get(self, client):
        resp = client.get("/health/", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/health"

    def test_trailing_slash_with_query(self, client):
        resp = client.get("/health/?q=1", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/health?q=1"

    def test_root_slash_not_redirected(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (200, 404, 307)


class TestCharsetMiddleware:
    def test_text_content_type_gets_charset(self, client):
        resp = client.get("/health")
        ct = resp.headers.get("content-type", "")
        if ct.startswith(("text/", "application/json")):
            assert "charset=utf-8" in ct


class TestCachedStaticFiles:
    @pytest.mark.asyncio
    async def test_get_response_adds_cache_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("hello")
            csf = CachedStaticFiles(directory=tmp, cache_max_age=999)
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.txt",
                "headers": [],
                "query_string": b"",
            }
            from starlette.routing import NoMatchFound
            try:
                resp = await csf.get_response("test.txt", scope)
                assert resp.headers.get("cache-control") == "public, max-age=999, immutable"
            except NoMatchFound:
                pass


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_enter_and_exit(self):
        import app.main as m
        start_funcs = [
            "_init_database_tables", "_load_token_blacklist",
            "_check_and_record_version_change", "_seed_default_admin",
            "_check_required_packages", "_verify_file_integrity",
            "_start_resource_monitoring", "_start_database_health_monitoring",
            "_start_approval_reminder",
        ]
        stop_funcs = [
            "_stop_approval_reminder",
            "_stop_resource_monitoring", "_stop_database_health_monitoring",
        ]
        mocks = {k: MagicMock() for k in start_funcs + stop_funcs}
        patchers = [patch.object(m, name, mocks[name]) for name in mocks]
        for p in patchers:
            p.start()
        async with lifespan(app):
            pass
        for p in patchers:
            p.stop()
        for name in start_funcs + stop_funcs:
            mocks[name].assert_called_once()


class TestLoadTokenBlacklist:
    def test_success_with_records(self):
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
            patch("app.core.token_blacklist.load_from_db", return_value=5),
            patch("app.main.logger.info") as mock_info,
        ):
            _load_token_blacklist()
            mock_info.assert_called_once()

    def test_success_no_records(self):
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
            patch("app.core.token_blacklist.load_from_db", return_value=0),
        ):
            _load_token_blacklist()

    def test_exception_handled(self):
        with (
            patch("app.core.database.SessionLocal", side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _load_token_blacklist()
            mock_warn.assert_called_once()


class TestInitDatabaseTables:
    def test_create_tables_and_indexes(self):
        with (
            patch("app.core.database.engine") as mock_engine,
            patch("app.models.base.Base") as mock_base,
            patch("app.core.database_indexes.create_indexes") as mock_idx,
            patch("app.main._run_alembic_upgrade"),  # 单测不跑真实迁移（避免副作用+alembic fileConfig 污染 logging）
            patch("app.main.logger.info"),
        ):
            _init_database_tables()
            mock_idx.assert_called_once()

    def test_auto_migration_enabled(self):
        with (
            patch("app.core.database.engine"),
            patch("app.models.base.Base"),
            patch("app.main.settings.ENABLE_AUTO_MIGRATION", True),
            patch("app.main._migrate_missing_columns") as mock_migrate,
            patch("app.core.database_indexes.create_indexes"),
            patch("app.main._run_alembic_upgrade"),  # 单测不跑真实迁移
        ):
            _init_database_tables()
            mock_migrate.assert_called_once()

    def test_auto_migration_disabled(self):
        with (
            patch("app.core.database.engine"),
            patch("app.models.base.Base"),
            patch("app.main.settings.ENABLE_AUTO_MIGRATION", False),
            patch("app.main._migrate_missing_columns") as mock_migrate,
            patch("app.core.database_indexes.create_indexes"),
            patch("app.main._run_alembic_upgrade"),  # 单测不跑真实迁移
            patch("app.main.logger.info") as mock_info,
        ):
            _init_database_tables()
            mock_migrate.assert_not_called()
            info_msgs = [c[0][0] for c in mock_info.call_args_list]
            assert any("disabled" in m for m in info_msgs)


class TestFaviconAndVersionJson:
    def test_favicon_not_found(self, client):
        resp = client.get("/favicon.ico")
        assert resp.status_code == 404
        assert resp.json()["message"] == "Favicon not found"

    def test_favicon_with_file(self):
        import app.main as m
        from pathlib import Path
        import tempfile
        orig = m._favicon_path
        try:
            with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as f:
                f.write(b"fake_icon")
                tmp = Path(f.name)
            m._favicon_path = tmp
            from app.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
            resp = client.get("/favicon.ico")
            assert resp.status_code == 200
        finally:
            m._favicon_path = orig
            if tmp.exists():
                tmp.unlink()

    def test_version_json_exists(self, client):
        import app.main as m
        orig = m._version_json_path
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                f.write(b'{"version": "test"}')
                tmp = Path(f.name)
            m._version_json_path = tmp
            from app.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
            resp = client.get("/version.json")
            assert resp.status_code == 200
            assert resp.headers.get("cache-control") == "no-cache"
        finally:
            m._version_json_path = orig
            if tmp is not None and tmp.exists():
                tmp.unlink()

    def test_version_json_not_found(self):
        import app.main as m
        orig = m._version_json_path
        try:
            m._version_json_path = None
            from app.main import app
            from fastapi.testclient import TestClient
            client = TestClient(app)
            resp = client.get("/version.json")
            assert resp.status_code == 404
            assert resp.json()["version"] == "unknown"
        finally:
            m._version_json_path = orig


class TestSpaFallbackReservedPath:
    def test_reserved_path_returns_404(self, client):
        resp = client.get("/docs/anything")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Not Found"

    def test_non_reserved_path_returns_html(self, client):
        resp = client.get("/some-random-non-existent-path")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


class TestMigrateMissingColumns:
    def test_disabled_by_env_var(self):
        with (
            patch.dict(os.environ, {"DISABLE_AUTO_MIGRATION": "1"}),
            patch("app.main.logger.info") as mock_info,
        ):
            _migrate_missing_columns(None, None)
            info_msgs = [c[0][0] for c in mock_info.call_args_list]
            assert any("DISABLE_AUTO_MIGRATION=1" in m for m in info_msgs)

    def test_inspector_creation_failure(self):
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect", side_effect=Exception("no insp")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _migrate_missing_columns(MagicMock(), MagicMock())
            # 弃用警告与 inspector 失败警告均会触发；仅断言 inspector 失败警告存在
            assert any(
                "failed to create inspector" in str(c) for c in mock_warn.call_args_list
            )

    def test_no_tables_in_model(self):
        mock_base = MagicMock()
        mock_base.metadata.tables = {}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect"),
        ):
            _migrate_missing_columns(MagicMock(), mock_base)

    def test_table_not_in_db_skipped(self):
        mock_base = MagicMock()
        mock_table = MagicMock()
        mock_table.name = "test_table"
        mock_base.metadata.tables = {"test_table": mock_table}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = False
            mock_insp.return_value = inspector
            _migrate_missing_columns(MagicMock(), mock_base)

    def test_no_missing_columns(self):
        mock_table = MagicMock()
        mock_table.name = "test_table"
        mock_col = MagicMock()
        mock_col.name = "id"
        mock_table.columns = [mock_col]
        mock_base = MagicMock()
        mock_base.metadata.tables = {"test_table": mock_table}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = True
            inspector.get_columns.return_value = [{"name": "id"}]
            mock_insp.return_value = inspector
            _migrate_missing_columns(MagicMock(), mock_base)

    def test_adds_missing_column(self):
        mock_col = MagicMock(name="new_col")
        mock_col.nullable = True
        mock_table = MagicMock(name="test_table")
        mock_table.columns = [mock_col]
        mock_base = MagicMock()
        mock_base.metadata.tables = {"test_table": mock_table}
        mock_engine = MagicMock()
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
            patch("app.main._sqlite_col_spec", return_value=("INTEGER", "DEFAULT 0")),
            patch("app.main.logger.info"),
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = True
            inspector.get_columns.return_value = [{"name": "id"}]
            mock_insp.return_value = inspector
            _migrate_missing_columns(mock_engine, mock_base)
            exec_mock = mock_engine.connect.return_value.__enter__.return_value.execute
            exec_mock.assert_called()

    def test_adds_column_not_null_with_default(self):
        from sqlalchemy import Column, Integer
        col = Column("c2", Integer, default=5, nullable=False)
        mock_table = MagicMock(name="t1")
        mock_table.columns = [col]
        mock_table.c = {"c2": col}
        mock_base = MagicMock()
        mock_base.metadata.tables = {"t1": mock_table}
        mock_engine = MagicMock()
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
            patch("app.main._sqlite_col_spec", wraps=_sqlite_col_spec),
            patch("app.main.logger.info"),
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = True
            inspector.get_columns.return_value = [{"name": "id"}]
            mock_insp.return_value = inspector
            _migrate_missing_columns(mock_engine, mock_base)
            exec_mock = mock_engine.connect.return_value.__enter__.return_value.execute
            exec_mock.assert_called()

    def test_column_add_failure(self):
        mock_col = MagicMock(name="bad")
        mock_table = MagicMock(name="t1")
        mock_table.columns = [mock_col]
        mock_base = MagicMock()
        mock_base.metadata.tables = {"t1": mock_table}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
            patch("app.main._sqlite_col_spec", side_effect=ValueError("bad")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = True
            inspector.get_columns.return_value = [{"name": "id"}]
            mock_insp.return_value = inspector
            _migrate_missing_columns(MagicMock(), mock_base)
            mock_warn.assert_called()

    def test_table_processing_error(self):
        mock_table = MagicMock()
        mock_table.name = "bad"
        mock_base = MagicMock()
        mock_base.metadata.tables = {"bad": mock_table}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
            patch("app.main.logger.warning") as mock_warn,
        ):
            inspector = MagicMock()
            inspector.has_table.side_effect = ValueError("bad table")
            mock_insp.return_value = inspector
            _migrate_missing_columns(MagicMock(), mock_base)
            mock_warn.assert_called()

    def test_summary_with_added_and_failed(self):
        mock_col = MagicMock()
        mock_col.name = "c1"
        mock_col.nullable = True
        mock_table = MagicMock()
        mock_table.name = "t1"
        mock_table.c = {"c1": mock_col}
        mock_base = MagicMock()
        mock_base.metadata.tables = {"t1": mock_table}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect") as mock_insp,
            patch("app.main._sqlite_col_spec", return_value=("INTEGER", "")),
            patch("app.main.logger.info"),
        ):
            inspector = MagicMock()
            inspector.has_table.return_value = True
            inspector.get_columns.return_value = [{"name": "id"}]
            mock_insp.return_value = inspector
            _migrate_missing_columns(MagicMock(), mock_base)

    def test_no_added_no_failed_summary(self):
        mock_base = MagicMock()
        mock_base.metadata.tables = {}
        with (
            patch.dict(os.environ, {}),
            patch("sqlalchemy.inspect"),
            patch("app.main.logger.info"),
        ):
            _migrate_missing_columns(MagicMock(), mock_base)


class TestSQLiteColSpec:
    def test_int_type(self):
        from sqlalchemy import Column, Integer
        col = Column("c", Integer)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "INTEGER"

    def test_bool_type(self):
        from sqlalchemy import Boolean, Column
        col = Column("c", Boolean)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "INTEGER"

    def test_float_type(self):
        from sqlalchemy import Column, Float
        col = Column("c", Float)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "REAL"

    def test_real_type(self):
        from sqlalchemy import Column, REAL
        col = Column("c", REAL)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "REAL"

    def test_numeric_type(self):
        from sqlalchemy import Column, Numeric
        col = Column("c", Numeric)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "REAL"

    def test_text_type(self):
        from sqlalchemy import Column, String
        col = Column("c", String)
        stype, _ = _sqlite_col_spec(col)
        assert stype == "TEXT"

    def test_default_int(self):
        from sqlalchemy import Column, Integer
        col = Column("c", Integer, default=5)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 5"

    def test_default_str(self):
        from sqlalchemy import Column, String
        col = Column("c", String, default="hello")
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 'hello'"

    def test_default_bool_true(self):
        from sqlalchemy import Boolean, Column
        col = Column("c", Boolean, default=True)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 1"

    def test_default_bool_false(self):
        from sqlalchemy import Boolean, Column
        col = Column("c", Boolean, default=False)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 0"

    def test_server_default_ignored(self):
        from sqlalchemy import Column, String, text
        col = Column("c", String, server_default=text("'default'"))
        _, default = _sqlite_col_spec(col)
        assert default == ""

    def test_not_null_int_no_default(self):
        from sqlalchemy import Column, Integer
        col = Column("c", Integer, nullable=False)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 0"

    def test_not_null_text_no_default(self):
        from sqlalchemy import Column, String
        col = Column("c", String, nullable=False)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT ''"

    def test_not_null_float_no_default(self):
        from sqlalchemy import Column, Float
        col = Column("c", Float, nullable=False)
        _, default = _sqlite_col_spec(col)
        assert default == "DEFAULT 0"


class TestSeedDefaultAdmin:
    @staticmethod
    def _patch_seed_default_admin(mock_db, *, unlock_expired_return=0):
        """统一 mock 设置：SessionLocal + LockoutService + getenv + logger."""
        from unittest.mock import patch as _patch

        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = unlock_expired_return
        patches = [
            _patch("app.core.database.SessionLocal", return_value=mock_db),
            _patch("app.main.os.getenv", return_value=""),
            _patch("app.main.logger.warning"),
            _patch("app.main.logger.info"),
            _patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ]
        return patches, mock_lockout

    @staticmethod
    def _build_mock_db(query_all=None, query_first=None):
        """构建 mock_db，同时支持 db.query() 和 db.execute() 两种 mock 风格.

        query_all: 列表，db.query(Model).filter(...).all() 的返回值
        query_first: 列表，db.query(Model).filter(...).first() 的返回值（按调用顺序）
        """
        mock_db = MagicMock()

        # --- db.query() 兼容（旧代码路径） ---
        mock_query = MagicMock()
        mock_filter = MagicMock()
        if query_all is not None:
            mock_filter.all.return_value = query_all
        mock_filter.first.side_effect = (
            (lambda: query_first.pop(0)) if query_first else (lambda: None)
        )
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # --- db.execute() 兼容（新 LockoutService 路径） ---
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        return mock_db

    def test_seed_admin_creation(self):
        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = 0
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
            patch("app.main.os.getenv", return_value=""),
            patch("app.core.security.generate_password", return_value="StrongP@ss1"),
            patch("app.core.security.hash_password", return_value="$2b$12$hash"),
            patch("app.main.logger.warning"),
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            mock_db = self._build_mock_db(query_all=[], query_first=[None, None])
            mock_sl.return_value = mock_db
            _seed_default_admin()
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()

    def test_seed_admin_already_exists(self):
        mock_admin = MagicMock()
        mock_db = self._build_mock_db(query_all=[], query_first=[mock_admin, mock_admin])
        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = 0
        with (
            patch("app.core.database.SessionLocal", return_value=mock_db),
            patch("app.main.os.getenv", return_value="PreSetP@ss1"),
            patch("app.main.logger.info"),
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            _seed_default_admin()
            mock_db.add.assert_not_called()
            mock_db.close.assert_called_once()

    def test_locked_users_unlocked(self):
        locked = MagicMock()
        locked.username = "locked_user"
        admin = MagicMock()
        admin.username = "admin"
        mock_db = self._build_mock_db(query_first=[admin, admin])

        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = 2

        with (
            patch("app.core.database.SessionLocal", return_value=mock_db),
            patch("app.main.os.getenv", return_value="PreSetP@ss1"),
            patch("app.main.logger.info"),
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            _seed_default_admin()
            mock_lockout.unlock_expired.assert_called_once()
            mock_db.close.assert_called_once()

    def test_exception_rollback(self):
        mock_db = MagicMock()
        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.side_effect = Exception("DB Error")
        with (
            patch("app.core.database.SessionLocal", return_value=mock_db),
            patch("app.main.os.getenv", return_value="PreSetP@ss1"),
            patch("app.main.logger.error") as mock_err,
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            _seed_default_admin()
            mock_db.rollback.assert_called_once()
            mock_err.assert_called_once()
            mock_db.close.assert_called_once()

    def test_top_org_fetch_failure(self):
        mock_db = self._build_mock_db(query_all=[], query_first=[None, None])
        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = 0
        with (
            patch("app.core.database.SessionLocal", return_value=mock_db),
            patch("app.main.os.getenv", return_value=""),
            patch("app.core.security.generate_password", return_value="GenP@ss1"),
            patch("app.core.security.hash_password", return_value="$2b$12$h"),
            patch("app.main.logger.warning"),
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            _seed_default_admin()
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()

    def test_seed_admin_with_existing_top_org(self):
        mock_org = MagicMock()
        mock_org.id = 42
        mock_db = self._build_mock_db(query_all=[], query_first=[None, mock_org])
        mock_lockout = MagicMock()
        mock_lockout.unlock_expired.return_value = 0
        with (
            patch("app.core.database.SessionLocal", return_value=mock_db),
            patch("app.main.os.getenv", return_value=""),
            patch("app.core.security.generate_password", return_value="GenP@ss1"),
            patch("app.core.security.hash_password", return_value="$2b$12$h"),
            patch("app.main.logger.warning"),
            patch(
                "app.services.lockout_service.get_lockout_service",
                return_value=mock_lockout,
            ),
        ):
            _seed_default_admin()
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()
            added_user = mock_db.add.call_args[0][0]
            assert added_user.organization_id == 42


class TestCheckRequiredPackages:
    def test_all_packages_installed(self):
        with (
            patch("builtins.__import__") as mock_import,
            patch("app.main.logger.info") as mock_info,
        ):
            _check_required_packages()
            mock_info.assert_called_once()

    def test_missing_packages(self):
        def mock_import_module(name):
            if name == "pandas":
                raise ImportError
            return MagicMock()
        with (
            patch("importlib.import_module", side_effect=mock_import_module),
        ):
            import app.main as m
            with patch.object(m.logger, "warning") as mock_warn:
                _check_required_packages()
                mock_warn.assert_called_once()


class TestResourceMonitoring:
    def test_start_success(self):
        with (
            patch("app.services.resource_limiter.resource_limiter") as mock_rl,
            patch("app.main.logger.info") as mock_info,
        ):
            _start_resource_monitoring()
            mock_rl.start_monitoring.assert_called_once()
            mock_info.assert_called_once()

    def test_start_exception(self):
        with (
            patch("app.services.resource_limiter.resource_limiter",
                  **{"start_monitoring.side_effect": Exception("fail")}),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _start_resource_monitoring()
            mock_warn.assert_called_once()

    def test_stop_success(self):
        with (
            patch("app.services.resource_limiter.resource_limiter") as mock_rl,
            patch("app.main.logger.info") as mock_info,
        ):
            _stop_resource_monitoring()
            mock_rl.stop_monitoring.assert_called_once()
            mock_info.assert_called_once()

    def test_stop_exception(self):
        with (
            patch("app.services.resource_limiter.resource_limiter",
                  **{"stop_monitoring.side_effect": Exception("fail")}),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _stop_resource_monitoring()
            mock_warn.assert_called_once()


class TestDatabaseHealthMonitoring:
    def test_start_success(self):
        with (
            patch("app.services.database_health_service.database_health_service") as svc,
            patch("app.main.logger.info") as mock_info,
        ):
            _start_database_health_monitoring()
            svc.start_monitoring.assert_called_once()
            mock_info.assert_called_once()

    def test_start_exception(self):
        with (
            patch("app.services.database_health_service.database_health_service",
                  **{"start_monitoring.side_effect": Exception("fail")}),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _start_database_health_monitoring()
            mock_warn.assert_called_once()

    def test_stop_success(self):
        with (
            patch("app.services.database_health_service.database_health_service") as svc,
            patch("app.main.logger.info") as mock_info,
        ):
            _stop_database_health_monitoring()
            svc.stop_monitoring.assert_called_once()
            mock_info.assert_called_once()

    def test_stop_exception(self):
        with (
            patch("app.services.database_health_service.database_health_service",
                  **{"stop_monitoring.side_effect": Exception("fail")}),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _stop_database_health_monitoring()
            mock_warn.assert_called_once()


class TestCheckAndRecordVersionChange:
    def test_initialize_action(self):
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_update = MagicMock()
            mock_update.check_and_record_version_change.return_value = {
                "action": "initialize",
                "result": {"initialized_count": 3},
            }
            with (
                patch("app.services.update_log_service.UpdateLogService",
                      return_value=mock_update),
                patch("app.services.version_service.version_service.get_current_version",
                      return_value={"version": "1.0.0"}),
                patch("app.main.logger.info") as mock_info,
            ):
                _check_and_record_version_change()
                mock_info.assert_called()
                mock_db.close.assert_called_once()

    def test_record_change_action(self):
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_update = MagicMock()
            mock_update.check_and_record_version_change.return_value = {
                "action": "record_change",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
            }
            with (
                patch("app.services.update_log_service.UpdateLogService",
                      return_value=mock_update),
                patch("app.services.version_service.version_service.get_current_version",
                      return_value={"version": "2.0.0"}),
                patch("app.main.logger.info") as mock_info,
            ):
                _check_and_record_version_change()
                mock_info.assert_called()
                mock_db.close.assert_called_once()

    def test_no_action(self):
        with (
            patch("app.core.database.SessionLocal") as mock_sl,
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            mock_update = MagicMock()
            mock_update.check_and_record_version_change.return_value = {}
            with (
                patch("app.services.update_log_service.UpdateLogService",
                      return_value=mock_update),
                patch("app.services.version_service.version_service.get_current_version",
                      return_value={"version": "1.0.0"}),
                patch("app.main.logger.info") as mock_info,
            ):
                _check_and_record_version_change()
                mock_info.assert_called()
                mock_db.close.assert_called_once()

    def test_exception(self):
        with (
            patch("app.core.database.SessionLocal",
                  side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _check_and_record_version_change()
            mock_warn.assert_called_once()


class TestVerifyFileIntegrity:
    def test_all_files_exist(self):
        with (
            patch("app.main.Path.exists", return_value=True),
            patch("app.main.Path.read_bytes", return_value=b"content"),
            patch("app.main.logger.info") as mock_info,
        ):
            _verify_file_integrity()
            mock_info.assert_called()

    def test_missing_file(self):
        orig = Path.exists
        call_count = [0]
        def mock_exists(self):
            call_count[0] += 1
            return call_count[0] > 2
        with (
            patch("app.main.Path.exists", mock_exists),
            patch("app.main.Path.read_bytes", return_value=b"x"),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _verify_file_integrity()
            mock_warn.assert_called()

    def test_exception(self):
        with (
            patch("app.main.Path", side_effect=Exception("fail")),
            patch("app.main.logger.error") as mock_err,
        ):
            _verify_file_integrity()
            mock_err.assert_called_once()


class TestApprovalReminder:
    def test_start_success(self):
        with (
            patch("app.services.reminder_service.start_approval_reminder",
                  return_value="reminder_ref"),
            patch("app.main.logger.info") as mock_info,
        ):
            _start_approval_reminder()
            import app.main as m
            assert m._approval_reminder == "reminder_ref"
            mock_info.assert_called_once()

    def test_start_exception(self):
        with (
            patch("app.services.reminder_service.start_approval_reminder",
                  side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _start_approval_reminder()
            mock_warn.assert_called_once()

    def test_stop_success(self):
        import app.main as m
        m._approval_reminder = "ref"
        with (
            patch("app.services.reminder_service.stop_approval_reminder") as mock_stop,
            patch("app.main.logger.info") as mock_info,
        ):
            _stop_approval_reminder()
            mock_stop.assert_called_once_with("ref")
            mock_info.assert_called_once()

    def test_stop_exception(self):
        import app.main as m
        m._approval_reminder = "ref"
        with (
            patch("app.services.reminder_service.stop_approval_reminder",
                  side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _stop_approval_reminder()
            mock_warn.assert_called_once()


class TestDbMaintenance:
    def test_start_success(self):
        with (
            patch("app.services.db_maintenance.start_db_maintenance") as mock_start,
        ):
            _start_db_maintenance()
            mock_start.assert_called_once()

    def test_start_exception(self):
        with (
            patch("app.services.db_maintenance.start_db_maintenance",
                  side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _start_db_maintenance()
            mock_warn.assert_called_once()

    def test_stop_success(self):
        with (
            patch("app.services.db_maintenance.stop_db_maintenance") as mock_stop,
        ):
            _stop_db_maintenance()
            mock_stop.assert_called_once()

    def test_stop_exception(self):
        with (
            patch("app.services.db_maintenance.stop_db_maintenance",
                  side_effect=Exception("fail")),
            patch("app.main.logger.warning") as mock_warn,
        ):
            _stop_db_maintenance()
            mock_warn.assert_called_once()


class TestCsrfMiddlewareEnabled:
    def test_csrf_middleware_added_when_enabled(self):
        import sys
        import importlib
        from app.core.config import settings
        settings.CSRF_ENABLED = True
        if "app.main" in sys.modules:
            del sys.modules["app.main"]
        mod = importlib.import_module("app.main")
        mids = [x.cls.__name__ for x in mod.app.user_middleware]
        assert "CSRFMiddleware" in mids


class TestFrontendStaticNotFound:
    def test_frontend_not_found_warning(self):
        import sys
        import importlib
        mod_ref = sys.modules.get("app.main")
        if mod_ref:
            del sys.modules["app.main"]
        with patch("app.core.static_files.setup_static_files", return_value=None):
            new_mod = importlib.import_module("app.main")
            assert new_mod._frontend_dir is None
