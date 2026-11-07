"""数据库健康检查异常路径必须关闭 SQLite 连接。"""

import sqlite3
from unittest.mock import MagicMock, patch

from app.services.database_health_service import DatabaseHealthService


def test_integrity_check_closes_connection_on_pragma_error(tmp_path):
    db_file = tmp_path / "health.db"
    db_file.write_bytes(b"")
    svc = DatabaseHealthService()
    svc.db_path = db_file

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.execute.side_effect = sqlite3.DatabaseError("database is locked")

    with patch(
        "app.services.database_health_service.sqlite3.connect", return_value=conn
    ):
        result = svc.check_integrity()

    assert result["status"] == "error"
    conn.close.assert_called_once()


def test_quick_check_closes_connection_on_error(tmp_path):
    db_file = tmp_path / "health.db"
    db_file.write_bytes(b"")
    svc = DatabaseHealthService()
    svc.db_path = db_file

    conn = MagicMock()
    conn.cursor.side_effect = sqlite3.DatabaseError("database is locked")

    with patch(
        "app.services.database_health_service.sqlite3.connect", return_value=conn
    ):
        result = svc.quick_check()

    assert result["status"] == "error"
    conn.close.assert_called_once()
