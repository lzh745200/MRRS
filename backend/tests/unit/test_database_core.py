"""
app/core/database.py 单元测试 — 目标 100% 行覆盖。

测试内容：
- _parse_env_int：空值/有效整数/无效整数（ValueError 回退）
- _set_sqlite_pragma：标准 PRAGMA（真实连接 + 直接调用 mock）、SQLCipher 加密分支
  （密钥文件存在/缺失/空白/异常）
- get_db：生成器 yield Session 并在结束时 close
- SQLiteWriteCoordinator.exclusive_write：非 SQLite 直接 yield / SQLite 加锁释放 / 超时
- SQLiteWriteCoordinator.enqueue：成功 / 超时 / 错误传播
- SQLiteWriteCoordinator._process_queue：通过 enqueue 触发
- SQLiteWriteCoordinator.pending：队列大小
- 模块别名：db_coordinator / write_queue / SQLiteWriteQueue
"""
import threading
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core import database
from app.core.database import (
    SQLITE_CACHE_SIZE,
    SQLITE_MMAP_SIZE,
    SQLiteWriteCoordinator,
    _parse_env_int,
    _set_sqlite_pragma,
    db_coordinator,
    engine,
    get_db,
)


# ---------------------------------------------------------------------------
# _parse_env_int
# ---------------------------------------------------------------------------
class TestParseEnvInt:
    """测试环境变量整数解析的三个分支。"""

    def test_empty_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_PARSE_INT_VAR", raising=False)
        assert _parse_env_int("TEST_PARSE_INT_VAR", 42) == 42

    def test_valid_integer_env(self, monkeypatch):
        monkeypatch.setenv("TEST_PARSE_INT_VAR", "999")
        assert _parse_env_int("TEST_PARSE_INT_VAR", 42) == 999

    def test_invalid_integer_falls_back_with_warning(self, monkeypatch):
        monkeypatch.setenv("TEST_PARSE_INT_VAR", "not-a-number")
        result = _parse_env_int("TEST_PARSE_INT_VAR", 42)
        assert result == 42

    def test_module_level_constants_are_integers(self):
        """模块级常量在导入时已通过 _parse_env_int 计算，验证类型。"""
        assert isinstance(SQLITE_MMAP_SIZE, int)
        assert isinstance(SQLITE_CACHE_SIZE, int)
        # 默认值验证
        assert SQLITE_MMAP_SIZE == 134217728
        assert SQLITE_CACHE_SIZE == -64000


# ---------------------------------------------------------------------------
# _set_sqlite_pragma
# ---------------------------------------------------------------------------
class TestSetSqlitePragma:
    """测试 SQLite PRAGMA 事件监听器。"""

    def test_real_connection_sets_wal_and_foreign_keys(self, tmp_path):
        """真实 SQLite 文件连接验证 PRAGMA 生效（端到端行为验证）。

        注：内存数据库 (:memory:) 不支持 WAL 模式，必须用文件数据库。
        """
        db_file = tmp_path / "test_pragma.db"
        test_engine = create_engine(
            f"sqlite:///{db_file}",
            connect_args={"check_same_thread": False},
        )
        event.listen(test_engine, "connect", _set_sqlite_pragma)
        try:
            with test_engine.connect() as conn:
                assert conn.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"
                assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
                # synchronous=NORMAL 对应值 1
                assert conn.exec_driver_sql("PRAGMA synchronous").scalar() == 1
        finally:
            test_engine.dispose()

    def test_non_sqlite_returns_early(self, monkeypatch):
        """IS_SQLITE=False 时直接返回，不创建 cursor。"""
        monkeypatch.setattr(database, "IS_SQLITE", False)
        dbapi_connection = MagicMock()
        _set_sqlite_pragma(dbapi_connection, None)
        dbapi_connection.cursor.assert_not_called()

    def test_standard_pragmas_via_direct_call(self, monkeypatch):
        """直接调用验证所有标准 PRAGMA 语句被执行。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        mock_settings = MagicMock()
        mock_settings.DB_ENCRYPTION_ENABLED = False
        monkeypatch.setattr(database, "settings", mock_settings)

        cursor = MagicMock()
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        _set_sqlite_pragma(dbapi_connection, None)

        executed = [call.args[0] for call in cursor.execute.call_args_list]
        assert "PRAGMA journal_mode=WAL" in executed
        assert "PRAGMA foreign_keys=ON" in executed
        assert "PRAGMA synchronous=NORMAL" in executed
        assert "PRAGMA busy_timeout=10000" in executed
        assert f"PRAGMA cache_size={SQLITE_CACHE_SIZE}" in executed
        assert f"PRAGMA mmap_size={SQLITE_MMAP_SIZE}" in executed
        assert "PRAGMA temp_store=MEMORY" in executed
        assert "PRAGMA wal_autocheckpoint=1000" in executed
        assert "PRAGMA automatic_index=ON" in executed
        cursor.close.assert_called_once()

    def test_encryption_key_file_exists(self, tmp_path, monkeypatch):
        """SQLCipher：密钥文件存在且非空 → 执行 PRAGMA key。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "db.key").write_text("super-secret-key-32-chars!", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.DB_ENCRYPTION_ENABLED = True
        mock_settings.BASE_DIR = tmp_path
        monkeypatch.setattr(database, "settings", mock_settings)

        cursor = MagicMock()
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        _set_sqlite_pragma(dbapi_connection, None)

        key_calls = [c for c in cursor.execute.call_args_list if "PRAGMA key" in str(c)]
        assert len(key_calls) == 1
        cursor.close.assert_called_once()

    def test_encryption_key_file_missing(self, tmp_path, monkeypatch):
        """SQLCipher：密钥文件缺失 → fail-closed 拒绝（不静默假加密，W5-T7）。"""
        import pytest as _pytest

        monkeypatch.setattr(database, "IS_SQLITE", True)
        mock_settings = MagicMock()
        mock_settings.DB_ENCRYPTION_ENABLED = True
        mock_settings.BASE_DIR = tmp_path  # 此目录下无 config/db.key
        monkeypatch.setattr(database, "settings", mock_settings)

        cursor = MagicMock()
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        with _pytest.raises(RuntimeError, match="未找到数据库加密密钥文件"):
            _set_sqlite_pragma(dbapi_connection, None)

        key_calls = [c for c in cursor.execute.call_args_list if "PRAGMA key" in str(c)]
        assert len(key_calls) == 0
        cursor.close.assert_called_once()

    def test_encryption_key_empty(self, tmp_path, monkeypatch):
        """SQLCipher：密钥文件存在但内容为空白 → fail-closed 拒绝（W5-T7）。"""
        import pytest as _pytest

        monkeypatch.setattr(database, "IS_SQLITE", True)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "db.key").write_text("  \n  \t ", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.DB_ENCRYPTION_ENABLED = True
        mock_settings.BASE_DIR = tmp_path
        monkeypatch.setattr(database, "settings", mock_settings)

        cursor = MagicMock()
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        with _pytest.raises(RuntimeError, match="密钥文件为空"):
            _set_sqlite_pragma(dbapi_connection, None)

        key_calls = [c for c in cursor.execute.call_args_list if "PRAGMA key" in str(c)]
        assert len(key_calls) == 0

    def test_encryption_key_statement_failure_propagates(self, tmp_path, monkeypatch):
        """SQLCipher：PRAGMA key 执行失败 → 异常上抛（fail-closed，连接不建立）。"""
        import pytest as _pytest

        monkeypatch.setattr(database, "IS_SQLITE", True)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "db.key").write_text("some-key", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.DB_ENCRYPTION_ENABLED = True
        mock_settings.BASE_DIR = tmp_path
        monkeypatch.setattr(database, "settings", mock_settings)

        cursor = MagicMock()

        def execute_side_effect(stmt, *args):
            if "PRAGMA key" in stmt:
                raise RuntimeError("SQLCipher not available")
            probe = MagicMock()
            probe.fetchone.return_value = ("4.0.0",)  # 探测语句返回驱动版本 → 通过
            return probe

        cursor.execute.side_effect = execute_side_effect

        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        with _pytest.raises(RuntimeError, match="SQLCipher not available"):
            _set_sqlite_pragma(dbapi_connection, None)

        cursor.close.assert_not_called()


# ---------------------------------------------------------------------------
# get_db
# ---------------------------------------------------------------------------
class TestGetDb:
    """测试 FastAPI 依赖注入生成器。"""

    def test_yields_session_and_closes(self):
        """get_db 生成器 yield 一个 Session，耗尽后自动 close。"""
        gen = get_db()
        db = next(gen)
        assert isinstance(db, Session)

        # 用 spy 验证 close 被调用（Session.is_active 在 close 后仍为 True）
        original_close = db.close
        close_calls = []

        def tracking_close():
            close_calls.append(1)
            original_close()

        db.close = tracking_close

        # 耗尽生成器，触发 finally → db.close()
        with pytest.raises(StopIteration):
            next(gen)
        assert len(close_calls) == 1

    def test_closes_on_generator_close(self):
        """生成器被提前 close 时也触发 finally。"""
        gen = get_db()
        db = next(gen)

        original_close = db.close
        close_calls = []

        def tracking_close():
            close_calls.append(1)
            original_close()

        db.close = tracking_close
        gen.close()
        assert len(close_calls) == 1


# ---------------------------------------------------------------------------
# SQLiteWriteCoordinator
# ---------------------------------------------------------------------------
class TestExclusiveWrite:
    """测试 exclusive_write 上下文管理器的三个分支。"""

    def test_non_sqlite_yields_without_lock(self, monkeypatch):
        """IS_SQLITE=False 时不加锁，直接 yield。"""
        monkeypatch.setattr(database, "IS_SQLITE", False)
        coord = SQLiteWriteCoordinator()
        # 确保锁未被持有
        assert coord._lock.acquire(blocking=False)
        coord._lock.release()

        with coord.exclusive_write(timeout=1.0):
            # 在上下文内，锁仍未被持有（非 SQLite 模式不加锁）
            assert coord._lock.acquire(blocking=False)
            coord._lock.release()

    def test_sqlite_acquires_and_releases_lock(self, monkeypatch):
        """IS_SQLITE=True 时获取锁，退出后释放。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()

        with coord.exclusive_write(timeout=1.0):
            # 上下文内：锁被持有
            assert not coord._lock.acquire(blocking=False)

        # 退出后：锁已释放
        assert coord._lock.acquire(blocking=False)
        coord._lock.release()

    def test_sqlite_lock_timeout_raises(self, monkeypatch):
        """IS_SQLITE=True 且锁被占用 → 超时抛出 TimeoutError。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()

        # 在另一个线程持有锁
        ready = threading.Event()
        release = threading.Event()

        def hold():
            coord._lock.acquire()
            ready.set()
            release.wait()
            coord._lock.release()

        holder = threading.Thread(target=hold)
        holder.start()
        assert ready.wait(timeout=2)

        try:
            with pytest.raises(TimeoutError, match="独占写锁超时"):
                with coord.exclusive_write(timeout=0.2):
                    pass
        finally:
            release.set()
            holder.join(timeout=2)


class TestEnqueueAndWorker:
    """测试 enqueue / _ensure_worker / _process_queue / pending。"""

    def test_enqueue_success(self, monkeypatch):
        """enqueue 成功执行并返回结果。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()
        result = coord.enqueue(lambda: 42, timeout=5.0)
        assert result == 42

    def test_enqueue_propagates_error(self, monkeypatch):
        """enqueue 中函数抛出异常 → 异常传播给调用方。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()

        def boom():
            raise ValueError("task failed")

        with pytest.raises(ValueError, match="task failed"):
            coord.enqueue(boom, timeout=5.0)

    def test_enqueue_timeout(self, monkeypatch):
        """enqueue 超时：工作线程被锁阻塞 → 调用方超时。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()

        # 持有锁，使工作线程的 exclusive_write 阻塞
        coord._lock.acquire()
        try:
            with pytest.raises(TimeoutError, match="队列操作超时"):
                coord.enqueue(lambda: 1, timeout=0.2)
        finally:
            coord._lock.release()

    def test_pending_returns_queue_size(self):
        """pending 属性返回队列大小（空队列为 0）。"""
        coord = SQLiteWriteCoordinator()
        assert coord.pending == 0

    def test_ensure_worker_starts_thread(self, monkeypatch):
        """_ensure_worker 懒启动后台线程。"""
        monkeypatch.setattr(database, "IS_SQLITE", True)
        coord = SQLiteWriteCoordinator()
        assert coord._worker is None
        # enqueue 会调用 _ensure_worker
        coord.enqueue(lambda: None, timeout=5.0)
        assert coord._worker is not None
        assert coord._worker.daemon is True


# ---------------------------------------------------------------------------
# 模块级别名
# ---------------------------------------------------------------------------
class TestModuleAliases:
    """验证向后兼容别名。"""

    def test_write_queue_is_db_coordinator(self):
        assert database.write_queue is db_coordinator

    def test_sqlite_write_queue_alias(self):
        assert database.SQLiteWriteQueue is SQLiteWriteCoordinator

    def test_db_coordinator_is_coordinator_instance(self):
        assert isinstance(db_coordinator, SQLiteWriteCoordinator)

    def test_engine_exists(self):
        assert engine is not None

    def test_session_local_bound_to_engine(self):
        from app.core.database import SessionLocal as SL
        assert SL.kw["bind"] is database.engine
