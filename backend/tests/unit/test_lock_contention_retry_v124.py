# -*- coding: utf-8 -*-
"""D1 写锁竞争退避重试的回归（v1.12.4）。

架构评估 D1【P1】：SQLite 单写多读，后台长事务（备份/清理/导出/导入）与在线写
操作争抢写锁时，`busy_timeout=10000` 用尽即抛 `database is locked`，且**无人重试**
—— 而仓库里唯一的重试工具 `retry_on_deadlock` 只有测试引用（事实上的死代码）。

本文件锁定三件事：

1. **判定收口**：`is_lock_contention` 只认锁竞争白名单（sqlite locked / deadlock /
   lock wait timeout / sqlite_busy），**不得**把 `no such table`、唯一约束冲突这类
   真实缺陷纳入重试（否则重试会掩盖 bug，而不是提升可用性）。
2. **同步与协程**：`retry_on_deadlock` 两种函数形态都要能用（后台作业多为 async），
   退避为线性 `delay * (attempt + 1)`，重试次数耗尽抛原异常，`max_retries<=0` 抛
   泛化文案的 DatabaseError（不带异常原文，W1 #6）。
3. **生产在用**：备份创建与保留期清理这两条真实长事务写入口必须挂着该装饰器
   —— 防止有人"清理死代码"时把它摘掉，退回 D1 原始状态。
"""

import asyncio

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services.backup_service import BackupService

import app.core.transaction as tx


def _lock_error(text="sqlite3.OperationalError: database is locked"):
    return SQLAlchemyError(text)


class TestLockContentionClassifier:
    @pytest.mark.parametrize(
        "message",
        [
            "sqlite3.OperationalError: database is locked",
            "database table is locked",
            "database schema is locked",
            "deadlock detected",
            "Lock wait timeout exceeded; try restarting transaction",
            "SQLITE_BUSY: database is locked",
        ],
    )
    def test_retryable_messages(self, message):
        assert tx.is_lock_contention(SQLAlchemyError(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "no such table: supported_villages",
            "UNIQUE constraint failed: users.username",
            "NOT NULL constraint failed: funds.amount",
            "syntax error near FROM",
            "",
        ],
    )
    def test_non_retryable_messages(self, message):
        """真实缺陷必须立刻暴露 —— 重试只会把它藏起来。"""
        assert tx.is_lock_contention(SQLAlchemyError(message)) is False


class TestSyncRetry:
    def test_retries_then_succeeds(self):
        calls = []

        @tx.retry_on_deadlock(max_retries=3, delay=0)
        def work():
            calls.append(1)
            if len(calls) < 2:
                raise _lock_error()
            return "ok"

        assert work() == "ok"
        assert len(calls) == 2

    def test_non_lock_error_is_not_retried(self):
        calls = []

        @tx.retry_on_deadlock(max_retries=3, delay=0)
        def work():
            calls.append(1)
            raise _lock_error("no such table: t")

        with pytest.raises(SQLAlchemyError):
            work()
        assert len(calls) == 1

    def test_exhaustion_reraises_original(self):
        calls = []

        @tx.retry_on_deadlock(max_retries=2, delay=0)
        def work():
            calls.append(1)
            raise _lock_error()

        with pytest.raises(SQLAlchemyError):
            work()
        assert len(calls) == 2

    def test_zero_retries_raises_generic_database_error(self):
        """max_retries<=0 时抛 DatabaseError；出站文案不得带异常原文。"""
        from app.core.exceptions import DatabaseError

        @tx.retry_on_deadlock(max_retries=0, delay=0)
        def work():
            raise AssertionError("不应执行")

        with pytest.raises(DatabaseError) as exc:
            work()
        assert "重试0次" in str(exc.value)
        assert "database is locked" not in str(exc.value)


class TestAsyncRetry:
    def test_async_retries_then_succeeds(self):
        calls = []

        @tx.retry_on_deadlock(max_retries=3, delay=0)
        async def work():
            calls.append(1)
            if len(calls) < 3:
                raise _lock_error()
            return "ok"

        assert asyncio.run(work()) == "ok"
        assert len(calls) == 3

    def test_async_non_lock_error_propagates(self):
        calls = []

        @tx.retry_on_deadlock(max_retries=3, delay=0)
        async def work():
            calls.append(1)
            raise _lock_error("UNIQUE constraint failed: x.y")

        with pytest.raises(SQLAlchemyError):
            asyncio.run(work())
        assert len(calls) == 1

    def test_async_zero_retries_raises_database_error(self):
        from app.core.exceptions import DatabaseError

        @tx.retry_on_deadlock(max_retries=0, delay=0)
        async def work():
            raise AssertionError("不应执行")

        with pytest.raises(DatabaseError):
            asyncio.run(work())


class TestProductionWiring:
    """D1 的修复必须真的挂在生产路径上，而不是又一个"仅测试引用"的工具。"""

    def test_backup_write_units_are_retry_protected(self):
        for name in ("create_backup", "cleanup_by_retention_days"):
            func = getattr(BackupService, name)
            assert hasattr(func, "__wrapped__"), (
                "%s 未挂 retry_on_deadlock（D1 退避重试被摘掉了？）" % name
            )

    def test_decorator_used_by_production_code(self):
        """`retry_on_deadlock` 必须在 backend/app 下被真实引用（消除死代码）。"""
        import pathlib

        root = pathlib.Path(tx.__file__).resolve().parents[1]  # backend/app
        hits = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "retry_on_deadlock" in text and path.name != "transaction.py":
                hits.append(path.name)
        assert hits, "retry_on_deadlock 在 app/ 下无生产引用（仍是死代码）"
