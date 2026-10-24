# -*- coding: utf-8 -*-
"""R36 · WAL 返回值断言 + 连接级健康快照（`app/core/database.py`）

背景：``PRAGMA journal_mode=WAL`` 只是请求，SQLite 可拒绝/降级（只读介质、
网络盘、其它连接已持有不同 journal 模式）。旧实现不看返回值 → 「以为开了 WAL，
实际 delete 模式」，并发读写退化成互斥、长时间运行偶发 SQLITE_BUSY，而
``/health`` 一切正常。

本文件锁定：
1. 返回 ``wal`` → 快照 ``journal_mode_ok=True``，不告警；
2. 返回 ``delete`` → logger.warning，且快照如实记录 ``journal_mode=delete``；
3. 探测本身异常（fetchone 抛错）→ 不打断连接建立，快照记 ``check_error_type``；
4. 真实文件连接仍然进入 WAL（端到端不回归）。
"""
import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event

from app.core import database
from app.core.database import _set_sqlite_pragma, database_health


@pytest.fixture(autouse=True)
def _reset_health_snapshot():
    """快照是模块级状态，用例间必须隔离。"""
    database._database_health.clear()
    yield
    database._database_health.clear()


def _conn_with_cursor(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def _cursor_returning(fetchone_return=None, fetchone_side_effect=None):
    cursor = MagicMock()
    if fetchone_side_effect is not None:
        cursor.fetchone.side_effect = fetchone_side_effect
    else:
        cursor.fetchone.return_value = fetchone_return
    return cursor


@pytest.fixture
def sqlite_settings(monkeypatch):
    """锁定为「非加密 SQLite」分支，隔离对真实 settings 的依赖。"""
    monkeypatch.setattr(database, "IS_SQLITE", True)
    mock_settings = MagicMock()
    mock_settings.DB_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(database, "settings", mock_settings)


class TestWalReturnValue:
    def test_wal_mode_recorded_as_ok(self, sqlite_settings):
        cursor = _cursor_returning(("wal",))
        _set_sqlite_pragma(_conn_with_cursor(cursor), None)

        snapshot = database_health()
        assert snapshot["journal_mode"] == "wal"
        assert snapshot["journal_mode_ok"] is True

    def test_wal_mode_is_case_insensitive(self, sqlite_settings):
        """SQLite 可能返回 "WAL"（大小写随驱动/版本），必须归一后再判定。"""
        cursor = _cursor_returning(("WAL",))
        _set_sqlite_pragma(_conn_with_cursor(cursor), None)

        assert database_health()["journal_mode"] == "wal"
        assert database_health()["journal_mode_ok"] is True

    def test_non_wal_mode_warns_and_records(self, sqlite_settings, caplog):
        """返回 delete → 必须告警（不能静默），且快照如实记录实际值。"""
        cursor = _cursor_returning(("delete",))
        with caplog.at_level(logging.WARNING, logger=database.__name__):
            _set_sqlite_pragma(_conn_with_cursor(cursor), None)

        assert any(
            "WAL" in record.getMessage() and record.levelno >= logging.WARNING
            for record in caplog.records
        ), "未进入 WAL 模式时必须 logger.warning 暴露"

        snapshot = database_health()
        assert snapshot["journal_mode"] == "delete"
        assert snapshot["journal_mode_ok"] is False

    def test_empty_fetchone_treated_as_unknown(self, sqlite_settings, caplog):
        """fetchone() 返回 None（异常驱动）→ 视作 unknown，不得误报 ok。"""
        cursor = _cursor_returning(None)
        with caplog.at_level(logging.WARNING, logger=database.__name__):
            _set_sqlite_pragma(_conn_with_cursor(cursor), None)

        snapshot = database_health()
        assert snapshot["journal_mode"] == "unknown"
        assert snapshot["journal_mode_ok"] is False

    def test_probe_error_does_not_break_connection(self, sqlite_settings, caplog):
        """探测异常不得让连接建立失败（离线现场：能跑比完美更重要）。"""
        cursor = _cursor_returning(fetchone_side_effect=RuntimeError("probe boom"))
        with caplog.at_level(logging.WARNING, logger=database.__name__):
            _set_sqlite_pragma(_conn_with_cursor(cursor), None)  # 不应抛出

        snapshot = database_health()
        assert snapshot["journal_mode_ok"] is False
        assert snapshot["check_error_type"] == "RuntimeError"

    def test_real_file_connection_reports_wal(self, tmp_path, sqlite_settings):
        """端到端：真实文件库连接后的快照必须是 wal（防止 mock 掩盖真回归）。"""
        db_file = tmp_path / "wal_health.db"
        test_engine = create_engine(f"sqlite:///{db_file}")
        event.listen(test_engine, "connect", _set_sqlite_pragma)
        try:
            with test_engine.connect() as conn:
                assert conn.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"
        finally:
            test_engine.dispose()

        snapshot = database_health()
        assert snapshot["journal_mode"] == "wal"
        assert snapshot["journal_mode_ok"] is True


class TestHealthSnapshotShape:
    def test_snapshot_is_copy_not_live_state(self, sqlite_settings):
        """返回副本：调用方改返回值不得污染模块状态。"""
        _set_sqlite_pragma(_conn_with_cursor(_cursor_returning(("wal",))), None)
        snapshot = database_health()
        snapshot["journal_mode"] = "tampered"
        assert database_health()["journal_mode"] == "wal"

    def test_snapshot_never_records_exception_message(self, sqlite_settings):
        """诊断口径：只记异常类名，不记原文（可能含数据库绝对路径）。"""
        cursor = _cursor_returning(
            fetchone_side_effect=RuntimeError("C:/secret/path/rural_revitalization.db")
        )
        _set_sqlite_pragma(_conn_with_cursor(cursor), None)

        raw = str(database_health())
        assert "RuntimeError" in raw
        assert "secret" not in raw
        assert "rural_revitalization.db" not in raw
