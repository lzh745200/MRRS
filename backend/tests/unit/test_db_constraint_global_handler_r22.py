"""R22 回归锁定：数据库约束类错误必须映射为 4xx，不得升级为 500。

背景（R22 sweep 实测）：33 个带 `*_id` 的 POST 端点里，8 个在传入不存在的关联 ID
时直接 500/503 —— 日志显示 `sqlite3.OperationalError: FOREIGN KEY constraint failed`
（SQLite 把外键冲突报成 OperationalError，不是 IntegrityError）。根因是"直接 INSERT，
未先验关联对象存在"，而 @handle_db_errors 装饰器只覆盖了一小部分端点。

修复分两层：
1. 共享映射 `core.exceptions.map_db_exception`（装饰器与全局处理器单一事实源）；
2. 全局 `IntegrityError` / `OperationalError` 处理器兜底——约束类 → 4xx，
   非约束类 OperationalError 维持既有 500 语义（真实服务端故障，行为不变）。
"""

import sqlite3

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions import map_db_exception, register_exception_handlers


def _sqlalchemy_error(kind, message):
    """构造带 sqlite3 原始异常的 SQLAlchemy 包装异常。"""
    return kind("INSERT INTO t VALUES (1)", None, sqlite3.OperationalError(message))


class TestMapDbException:
    def test_integrity_unique_is_conflict(self):
        exc = IntegrityError("INSERT", None, sqlite3.IntegrityError("UNIQUE constraint failed: t.a"))
        mapped = map_db_exception(exc)
        assert mapped.status_code == 409
        assert "已存在" in mapped.detail

    def test_integrity_foreign_key_is_bad_request(self):
        exc = IntegrityError("INSERT", None, sqlite3.IntegrityError("FOREIGN KEY constraint failed"))
        mapped = map_db_exception(exc)
        assert mapped.status_code == 400
        assert "关联数据不存在" in mapped.detail

    def test_integrity_other_is_bad_request(self):
        exc = IntegrityError("INSERT", None, sqlite3.IntegrityError("NOT NULL constraint failed: t.a"))
        mapped = map_db_exception(exc)
        assert mapped.status_code == 400
        assert mapped.detail == "数据完整性错误，请检查提交的数据"

    def test_operational_foreign_key_is_bad_request(self):
        """SQLite 的真实形态：外键冲突是 OperationalError。"""
        mapped = map_db_exception(_sqlalchemy_error(OperationalError, "FOREIGN KEY constraint failed"))
        assert mapped.status_code == 400
        assert "关联数据不存在" in mapped.detail

    def test_operational_unique_is_conflict(self):
        mapped = map_db_exception(_sqlalchemy_error(OperationalError, "UNIQUE constraint failed: t.a"))
        assert mapped.status_code == 409

    def test_operational_not_null_and_check(self):
        assert map_db_exception(
            _sqlalchemy_error(OperationalError, "NOT NULL constraint failed: t.a")
        ).status_code == 400
        assert map_db_exception(_sqlalchemy_error(OperationalError, "CHECK constraint failed: ck")).status_code == 400

    def test_operational_unrelated_returns_none(self):
        """真正的服务端故障（磁盘/锁/无表）不映射，维持既有 500。"""
        assert map_db_exception(_sqlalchemy_error(OperationalError, "database or disk is full")) is None
        assert map_db_exception(_sqlalchemy_error(OperationalError, "database is locked")) is None

    def test_other_exception_returns_none(self):
        assert map_db_exception(RuntimeError("boom")) is None

    def test_error_text_never_leaks_schema(self):
        """出站文案不得含表名/列名/SQL 片段（W1 #6）。"""
        exc = _sqlalchemy_error(OperationalError, "FOREIGN KEY constraint failed")
        mapped = map_db_exception(exc)
        for token in ("INSERT", "fund_contracts", "FOREIGN KEY", "constraint"):
            assert token not in mapped.detail


@pytest.fixture
def app_client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/fk")
    def _fk():
        raise _sqlalchemy_error(OperationalError, "FOREIGN KEY constraint failed")

    @app.get("/unique")
    def _unique():
        raise _sqlalchemy_error(OperationalError, "UNIQUE constraint failed: users.username")

    @app.get("/integrity")
    def _integrity():
        raise IntegrityError("INSERT", None, sqlite3.IntegrityError("NOT NULL constraint failed: t.a"))

    @app.get("/db-down")
    def _db_down():
        raise _sqlalchemy_error(OperationalError, "unable to open database file")

    @app.get("/http-error")
    def _http_error():
        raise HTTPException(status_code=418, detail="teapot")

    return TestClient(app, raise_server_exceptions=False)


class TestGlobalConstraintHandler:
    def test_foreign_key_becomes_400(self, app_client):
        resp = app_client.get("/fk")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 400
        assert body["message"] == "关联数据不存在或已被删除"
        assert body["detail"] == body["message"]  # 两种前端读取方式都要能拿到
        assert body["success"] is False

    def test_unique_becomes_409(self, app_client):
        resp = app_client.get("/unique")
        assert resp.status_code == 409
        assert resp.json()["message"] == "数据已存在，请检查唯一性约束"

    def test_integrity_becomes_400(self, app_client):
        resp = app_client.get("/integrity")
        assert resp.status_code == 400
        assert resp.json()["message"] == "数据完整性错误，请检查提交的数据"

    def test_non_constraint_operational_error_stays_500(self, app_client):
        resp = app_client.get("/db-down")
        assert resp.status_code == 500
        assert resp.json() == {"code": 500, "message": "服务器内部错误", "success": False}

    def test_http_exception_unaffected(self, app_client):
        resp = app_client.get("/http-error")
        assert resp.status_code == 418
