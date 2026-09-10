"""R22 回归锁定：事务层的异常文案不得内插异常原文（W1 不变量 #6）。

R22 实测缺陷：`TransactionManager.transaction` 等 8 处把 `str(e)` 内插进
`DatabaseError`，而 SQLAlchemy 的异常原文形如

    (sqlite3.OperationalError) FOREIGN KEY constraint failed
    [SQL: INSERT INTO rbac_user_permissions (id, user_id, permission, granted_by, expires_at)
     VALUES (?, ?, ?, ?, ?) RETURNING created_at, updated_at]
    [parameters: ('b0b7792e...', 99999999, 'user:read', '1', None)]

于是 `POST /rbac/grant/permission` 的 500 响应体里带着完整 SQL 结构、表名、列名与
绑定参数 —— 直接违反军事审计红线 W1 #6。修复：约束类错误映射为 4xx
（`map_db_exception`），其余一律泛化文案，原文只进日志。
"""

import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.exceptions import DatabaseError
from app.core.transaction import (
    TransactionManager,
    _batch_failure,
    _transaction_failure,
    nested_transaction,
    retry_on_deadlock,
    savepoint,
    transaction,
)

FK = "FOREIGN KEY constraint failed"
SQL_TEXT = (
    "INSERT INTO rbac_user_permissions (id, user_id, permission) VALUES (?, ?, ?)"
)
PARAMS = "[parameters: ('abc', 99999999, 'user:read')]"
LEAKY = f"(sqlite3.OperationalError) {FK}\n[SQL: {SQL_TEXT}]\n{PARAMS}"


def _op(message):
    return OperationalError(SQL_TEXT, {"x": 1}, sqlite3.OperationalError(message))


class TestTransactionFailureMessage:
    def test_constraint_becomes_4xx(self):
        mapped = _transaction_failure(_op(FK))
        assert mapped.status_code == 400
        assert "关联数据不存在" in mapped.detail

    def test_unique_becomes_409(self):
        mapped = _transaction_failure(_op("UNIQUE constraint failed: users.username"))
        assert mapped.status_code == 409

    def test_integrity_error_becomes_4xx(self):
        exc = IntegrityError("INSERT", None, sqlite3.IntegrityError(FK))
        assert _transaction_failure(exc).status_code == 400

    def test_other_error_is_generic_and_leak_free(self):
        err = _transaction_failure(_op("unable to open database file"))
        assert isinstance(err, DatabaseError)
        assert err.message == "事务执行失败，请稍后重试或联系管理员"
        for token in ("[SQL", "INSERT INTO", "parameters", "rbac_user_permissions", "sqlite3"):
            assert token not in err.message

    def test_business_app_error_passes_through(self):
        """业务异常（如 NotFoundError 角色不存在）不能被泛化文案吞掉。"""
        from app.core.exceptions import NotFoundError

        exc = NotFoundError("角色", "no-such-role")
        assert _transaction_failure(exc) is exc

    def test_business_http_exception_passes_through(self):
        from fastapi import HTTPException

        exc = HTTPException(status_code=409, detail="编号已存在")
        assert _transaction_failure(exc) is exc

    def test_business_error_carrying_db_text_is_genericized(self):
        """业务异常文案里夹带 SQL 原文时照样降级（防 `BusinessError(f'失败: {e}')`）。"""
        from app.core.exceptions import BusinessError

        leaky = BusinessError(f"保存失败: {LEAKY}")
        err = _transaction_failure(leaky)
        assert isinstance(err, DatabaseError)
        assert "[SQL" not in err.message and "parameters" not in err.message

    def test_nested_and_savepoint_messages(self):
        assert _transaction_failure(_op("boom"), kind="nested").message == "嵌套事务执行失败，请稍后重试或联系管理员"
        assert _transaction_failure(_op("boom"), kind="savepoint").message == "保存点执行失败，请稍后重试或联系管理员"

    def test_batch_failure_messages(self):
        assert _batch_failure(_op(FK), "批量插入").status_code == 400
        err = _batch_failure(_op("disk I/O error"), "批量插入")
        assert err.message == "批量插入失败，请稍后重试或联系管理员"
        assert "disk I/O" not in err.message


class _Boom(Exception):
    pass


class TestTransactionPathsDoNotLeak:
    def test_transaction_context_manager_generic(self, mock_db):
        with pytest.raises(DatabaseError) as ei:
            with transaction(mock_db):
                raise _op("unable to open database file")
        assert "[SQL" not in ei.value.message
        mock_db.rollback.assert_called()

    def test_transaction_context_manager_constraint(self, mock_db):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            with transaction(mock_db):
                raise _op(FK)
        assert ei.value.status_code == 400

    def test_nested_transaction_generic(self, mock_db):
        with pytest.raises(DatabaseError) as ei:
            with nested_transaction(mock_db):
                raise _op("boom")
        assert ei.value.message == "嵌套事务执行失败，请稍后重试或联系管理员"

    def test_savepoint_generic(self, mock_db):
        with pytest.raises(DatabaseError) as ei:
            with savepoint(mock_db, "sp1"):
                raise _op("boom")
        assert ei.value.message == "保存点执行失败，请稍后重试或联系管理员"

    def test_run_in_transaction_generic(self, mock_db):
        def _boom(db):
            raise _op("boom")

        with pytest.raises(DatabaseError) as ei:
            TransactionManager.run_in_transaction(_boom, mock_db)
        assert "[SQL" not in ei.value.message

    def test_transactional_without_session_generic(self):
        from app.core.transaction import transactional

        @transactional
        def _boom(db):
            raise _op("boom")

        with pytest.raises(DatabaseError) as ei:
            _boom()
        assert "[SQL" not in ei.value.message

    def test_retry_on_deadlock_keeps_count_without_leak(self):
        @retry_on_deadlock(max_retries=0, delay=0)
        def _boom():
            raise _op("database is locked")

        with pytest.raises(DatabaseError) as ei:
            _boom()
        assert "重试0次后" in ei.value.message
        assert "[SQL" not in ei.value.message

    def test_retry_exhausted_reraises_original_for_global_mapping(self):
        """重试次数用尽且仍是锁冲突时，原样抛出 —— 由全局处理器统一映射，不再自带文案。"""
        from sqlalchemy.exc import SQLAlchemyError

        @retry_on_deadlock(max_retries=1, delay=0)
        def _boom():
            raise _op("database is locked")

        with pytest.raises(SQLAlchemyError):
            _boom()

    def test_retry_zero_max_retries_fallback(self):
        @retry_on_deadlock(max_retries=0, delay=0)
        def _boom():
            raise _op("deadlock")

        with pytest.raises(DatabaseError) as ei:
            _boom()
        assert "重试0次后" in ei.value.message

    def test_exception_text_falls_back_to_str(self):
        """既无 message 也无 detail 的异常回落到 str(exc)（防御分支）。"""
        from app.core.transaction import _exception_text

        assert _exception_text(RuntimeError("boom")) == "boom"

    def test_leaky_original_still_reaches_log(self, caplog):
        import logging

        with caplog.at_level(logging.ERROR, logger="app.core.transaction"):
            _transaction_failure(_op(LEAKY))
        assert any("constraint" in r.message.lower() or "rolled back" in r.message for r in caplog.records)
