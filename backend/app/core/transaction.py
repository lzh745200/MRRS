"""
事务管理工具
提供声明式和编程式事务管理
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.database import IS_SQLITE
from app.core.exceptions import AppError, DatabaseError, map_db_exception

# 合法的事务隔离级别白名单
_VALID_ISOLATION_LEVELS = frozenset(
    {
        "READ UNCOMMITTED",
        "READ COMMITTED",
        "REPEATABLE READ",
        "SERIALIZABLE",
    }
)


@contextmanager
def get_db_context():
    """将 get_db 生成器包装为上下文管理器"""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


logger = logging.getLogger(__name__)


_DB_DETAIL_MARKERS = (
    "[sql:",
    "[parameters:",
    "sqlalchemy.exc",
    "sqlite3.",
    "sqlstate",
    "psycopg",
    "mysql.connector",
)


def _exception_text(exc: Exception) -> str:
    for attr in ("message", "detail"):
        val = getattr(exc, attr, None)
        if isinstance(val, str) and val:
            return val
    return str(exc)


def _looks_like_db_detail(exc: Exception) -> bool:
    """文案里是否夹带了 SQLAlchemy/driver 的原文（含 SQL 结构与绑定参数）。"""
    low = _exception_text(exc).lower()
    return any(marker in low for marker in _DB_DETAIL_MARKERS)


def _transaction_failure(exc: Exception, *, kind: str = "transaction") -> Exception:
    """把事务内异常翻译成**出站安全**的应用异常（R22）。

    - 约束类错误（外键/唯一/NOT NULL/CHECK）→ 对应 4xx HTTPException（用户输入可纠正）；
    - 业务异常（`AppError` / `HTTPException`，如 NotFoundError("角色(x)不存在")）→ 原样透出，
      不能让泛化文案把有价值的业务提示吞掉；
    - 其余 → 泛化的 DatabaseError(500)。

    ⚠️ **禁止**把 `str(exc)` 内插进出站文案（W1 不变量 #6）：SQLAlchemy 异常原文
    形如 ``(sqlite3.OperationalError) FOREIGN KEY constraint failed
    [SQL: INSERT INTO rbac_user_permissions (id, user_id, ...) VALUES (?, ?, ...)]
    [parameters: ('...', 99999999, ...)]`` —— 出站即泄露表名、列名、SQL 结构与
    绑定参数。R22 实测：给不存在的用户授权时 `/rbac/grant/permission` 的 500
    响应体里带着完整 INSERT 语句与参数。原文只进日志（exc_info=True）。

    业务异常透出前也做一次夹带检测：若其文案里已含 SQL/driver 原文（例如某处
    `BusinessError(f"失败: {e}")`），照样降级为泛化文案。
    """
    mapped = map_db_exception(exc)
    if mapped is not None:
        logger.error("Transaction failed (constraint), rolled back", exc_info=True)
        return mapped

    if isinstance(exc, (HTTPException, AppError)) and not _looks_like_db_detail(exc):
        logger.error("Transaction failed (business), rolled back", exc_info=True)
        return exc

    logger.error("Transaction failed, rolled back", exc_info=True)
    if kind == "nested":
        return DatabaseError("嵌套事务执行失败，请稍后重试或联系管理员")
    if kind == "savepoint":
        return DatabaseError("保存点执行失败，请稍后重试或联系管理员")
    return DatabaseError("事务执行失败，请稍后重试或联系管理员")


class TransactionManager:
    """事务管理器"""

    @staticmethod
    @contextmanager
    def transaction(db: Session):
        """
        事务上下文管理器

        使用方法:
            with transaction(db) as session:
                # 执行数据库操作
                session.add(user)
                # 如果发生异常，自动回滚
                # 否则自动提交
        """
        try:
            yield db
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise _transaction_failure(e) from e

    @staticmethod
    def transactional(func: Callable) -> Callable:
        """
        事务装饰器

        使用方法:
            @transactional
            def create_user(db: Session, user_data: dict):
                user = User(**user_data)
                db.add(user)
                return user
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            # 查找数据库会话参数
            db = None
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                    break

            if db is None:
                # 从关键字参数中查找
                db = kwargs.get("db")

            if db is None:
                # 自动创建会话
                with get_db_context() as session:
                    try:
                        return func(session, *args, **kwargs)
                    except Exception as e:
                        session.rollback()
                        raise _transaction_failure(e) from e
            else:
                # 使用现有会话
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    db.rollback()
                    raise _transaction_failure(e) from e

        return wrapper

    @staticmethod
    def run_in_transaction(func: Callable, db: Session, *args, **kwargs) -> Any:
        """
        在事务中执行函数

        Args:
            func: 要执行的函数
            db: 数据库会话
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果
        """
        try:
            result = func(db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise _transaction_failure(e) from e

    @staticmethod
    @contextmanager
    def nested_transaction(db: Session):
        """
        嵌套事务上下文管理器

        使用方法:
            with nested_transaction(db) as session:
                # 执行数据库操作
                session.add(user)
        """
        # 开始嵌套事务
        nested = db.begin_nested()
        try:
            yield nested
            nested.commit()
        except Exception as e:
            nested.rollback()
            raise _transaction_failure(e, kind="nested") from e

    @staticmethod
    @contextmanager
    def savepoint(db: Session, name: Optional[str] = None):
        """
        保存点上下文管理器

        Args:
            db: 数据库会话
            name: 保存点名称（可选）

        使用方法:
            with savepoint(db, 'user_savepoint') as sp:
                # 执行数据库操作
                db.add(user)
                # 可以回滚到这个保存点
                # sp.rollback()
        """
        sp = db.begin_nested()
        if name:
            sp.name = name
        try:
            yield sp
            sp.commit()
        except Exception as e:
            sp.rollback()
            raise _transaction_failure(e, kind="savepoint") from e


# 便捷函数
transaction = TransactionManager.transaction
transactional = TransactionManager.transactional
run_in_transaction = TransactionManager.run_in_transaction
nested_transaction = TransactionManager.nested_transaction
savepoint = TransactionManager.savepoint


def safe_commit(db: Session, logger: Optional[logging.Logger] = None) -> bool:
    """
    安全提交事务：commit 失败时自动 rollback、记录日志并重新抛出异常。

    用作 ``db.commit()`` 的安全替代品，确保：
    1. commit 异常时 session 一定被 rollback（不会卡在脏状态）
    2. 异常被重新抛出，调用方的 try/except 仍能捕获并返回适当的 HTTP 错误

    Args:
        db: SQLAlchemy 会话
        logger: 可选的 logger 实例（默认使用模块 logger）

    Returns:
        True 表示提交成功（失败时抛出异常，不会返回 False）

    Usage::

        # 替换裸 db.commit()
        safe_commit(db)

        # 在 try/except 中使用（异常会被抛出）
        try:
            safe_commit(db)
        except Exception:
            raise HTTPException(status_code=500, detail="提交失败")
    """
    log = logger or logging.getLogger(__name__)
    try:
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        log.error(f"safe_commit: commit failed, rolled back: {e}")
        raise


def _apply_tx_settings(sess: Session, isolation: Optional[str], readonly: bool):
    """Apply transaction isolation level and read-only settings."""
    # SQLite 不支持 SET TRANSACTION 语法，直接短路
    if IS_SQLITE:
        return
    if isolation:
        sess.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation}"))
    if readonly:
        sess.execute(text("SET TRANSACTION READ ONLY"))


def _execute_in_transaction(db: Optional[Session], func: Callable, args, kwargs,
                            isolation: Optional[str], readonly: bool):
    """Execute function within a transaction, handling commit/rollback."""
    if db is not None:
        return _execute_with_existing_session(db, func, args, kwargs, isolation, readonly)
    else:
        return _execute_with_new_session(func, args, kwargs, isolation, readonly)


def _execute_with_existing_session(db: Session, func: Callable, args, kwargs,
                                   isolation: Optional[str], readonly: bool):
    """Execute using an existing database session."""
    try:
        _apply_tx_settings(db, isolation, readonly)
        result = func(*args, **kwargs)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise _transaction_failure(e) from e


def _execute_with_new_session(
    func: Callable, args, kwargs, isolation: Optional[str], readonly: bool
):
    """Execute within a new database session context."""
    with get_db_context() as session:
        try:
            _apply_tx_settings(session, isolation, readonly)
            result = func(session, *args, **kwargs)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise _transaction_failure(e) from e


def _find_db_session(args, kwargs) -> Optional[Session]:
    """Find the database session from function arguments."""
    for arg in args:
        if isinstance(arg, Session):
            return arg
    return kwargs.get("db")


def with_transaction(isolation_level: Optional[str] = None, readonly: bool = False):
    """
    高级事务装饰器

    Args:
        isolation_level: 隔离级别（READ COMMITTED, REPEATABLE READ, SERIALIZABLE）
        readonly: 是否只读事务

    使用方法:
        @with_transaction(isolation_level="READ COMMITTED")
        def create_user(db: Session, user_data: dict):
            user = User(**user_data)
            db.add(user)
            return user
    """
    # 在装饰器定义期间（而非运行时）校验隔离级别，防止 SQL 注入
    if isolation_level and isolation_level.upper() not in _VALID_ISOLATION_LEVELS:
        raise ValueError(f"无效的隔离级别: {isolation_level}，" f"允许值: {', '.join(sorted(_VALID_ISOLATION_LEVELS))}")
    _safe_isolation = isolation_level.upper() if isolation_level else None

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            db = _find_db_session(args, kwargs)
            return _execute_in_transaction(db, func, args, kwargs, _safe_isolation, readonly)
        return wrapper

    return decorator


# 重试装饰器
def is_lock_contention(exc: BaseException) -> bool:
    """判定是否为"写锁竞争"类错误（唯一判定入口，供重试逻辑共用）。

    SQLite 在 WAL 下允许单写多读：写事务争抢时 `busy_timeout`（=10s，见
    `core/database.py`）等待超时后抛 `database is locked`；其他后端对应
    deadlock / lock wait timeout。这类错误**重试即可**，与语法/约束错误
    （如 `no such table`、唯一键冲突）性质完全不同 —— 后者重试只会掩盖真实缺陷，
    因此这里用**白名单文本**而不是宽泛的 `"lock" in text`。
    """
    text = str(exc).lower()
    return (
        "database is locked" in text
        or "database table is locked" in text
        or "database schema is locked" in text
        or "deadlock" in text
        # 两种措辞都要覆盖："database lock timeout"（既有 test_lock_error_retries）
        # 与 "Lock wait timeout exceeded"（MySQL 风格，本文件分类器测试锁定）
        or "lock timeout" in text
        or "lock wait timeout" in text
        or "sqlite_busy" in text
    )


def retry_on_deadlock(max_retries: int = 3, delay: float = 0.1):
    """锁竞争重试装饰器（同步函数与协程函数均支持）。

    背景（架构评估 D1）：SQLite 写并发下偶发 `database is locked`，
    此前只靠 `busy_timeout` 硬等 10s，超时即失败；而唯一的重试工具
    `retry_on_deadlock` 只有测试引用（事实上的死代码）。现将其变成
    **生产在用**的退避重试：

    * 判定收口到 :func:`is_lock_contention`（白名单，不误吞真实错误）；
    * 线性退避 `delay * (attempt + 1)`：多次争抢时逐步让出写窗口；
    * 仅重试锁竞争；其他异常立即抛出（保持原有语义，测试已锁定）；
    * 重试次数耗尽仍抛原异常；`max_retries <= 0` 时抛 :class:`DatabaseError`
      （出站文案不带异常原文，W1 #6）。

    Args:
        max_retries: 最大尝试次数（含首次）
        delay: 首次重试延迟（秒），第 n 次重试等待 `delay * n`

    使用方法::

        @retry_on_deadlock(max_retries=3, delay=0.5)
        def update_user(db: Session, user_id: int, data: dict):
            ...

    注意：被装饰函数应为**完整的工作单元** —— `safe_commit` 在提交失败时会
    rollback 并抛出，因此重试必须重新执行整个单元，而不是只重试 commit。
    """
    import asyncio
    import inspect
    import time

    def decorator(func: Callable) -> Callable:
        def _log_retry(attempt: int, exc: Exception) -> None:
            logger.warning(
                "锁竞争重试 %s（%d/%d）: %s",
                getattr(func, "__qualname__", func),
                attempt + 1,
                max_retries,
                exc,
            )

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except SQLAlchemyError as e:
                        last_exception = e
                        if is_lock_contention(e) and attempt < max_retries - 1:
                            _log_retry(attempt, e)
                            await asyncio.sleep(delay * (attempt + 1))
                            continue
                        raise
                logger.error(
                    "事务执行失败（重试%d次后），已回滚", max_retries, exc_info=True
                )
                raise DatabaseError(
                    f"事务执行失败（重试{max_retries}次后），请稍后重试或联系管理员"
                ) from last_exception

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except SQLAlchemyError as e:
                    last_exception = e
                    if is_lock_contention(e) and attempt < max_retries - 1:
                        _log_retry(attempt, e)
                        time.sleep(delay * (attempt + 1))
                        continue
                    raise

            # 循环结束只剩 max_retries<=0 一种可能（每轮要么 return、要么 continue、
            # 要么 raise），此时 last_exception 必为 None，因此这里只需泛化文案 +
            # 重试次数；出站文案仍不带异常原文（W1 #6）。
            logger.error("Transaction failed after %d retries, rolled back", max_retries, exc_info=True)
            raise DatabaseError(
                f"事务执行失败（重试{max_retries}次后），请稍后重试或联系管理员"
            ) from last_exception

        return wrapper

    return decorator


# 批量操作工具
class BatchOperation:
    """批量操作工具"""

    @staticmethod
    def batch_insert(db: Session, model_class: type, items: list[dict], batch_size: int = 1000) -> int:
        """
        批量插入

        Args:
            db: 数据库会话
            model_class: 模型类
            items: 要插入的数据列表
            batch_size: 批次大小

        Returns:
            插入的记录数
        """
        total_inserted = 0

        try:
            for i in range(0, len(items), batch_size):
                batch = items[i: i + batch_size]
                db.bulk_insert_mappings(model_class, batch)
                total_inserted += len(batch)

                # 每个批次后刷新，避免内存占用过大
                db.flush()

            db.commit()
            return total_inserted
        except Exception as e:
            db.rollback()
            raise _batch_failure(e, "批量插入") from e

    @staticmethod
    def batch_update(db: Session, model_class: type, updates: list[dict], batch_size: int = 1000) -> int:
        """
        批量更新

        Args:
            db: 数据库会话
            model_class: 模型类
            updates: 更新数据列表（每个字典必须包含id）
            batch_size: 批次大小

        Returns:
            更新的记录数
        """
        total_updated = 0

        try:
            for i in range(0, len(updates), batch_size):
                batch = updates[i: i + batch_size]
                db.bulk_update_mappings(model_class, batch)
                total_updated += len(batch)
                db.flush()

            db.commit()
            return total_updated
        except Exception as e:
            db.rollback()
            raise _batch_failure(e, "批量更新") from e

    @staticmethod
    def batch_delete(db: Session, model_class: type, ids: list, batch_size: int = 1000) -> int:
        """
        批量删除

        Args:
            db: 数据库会话
            model_class: 模型类
            ids: 要删除的ID列表
            batch_size: 批次大小

        Returns:
            删除的记录数
        """
        total_deleted = 0

        try:
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i: i + batch_size]
                db.query(model_class).filter(model_class.id.in_(batch_ids)).delete(synchronize_session=False)
                total_deleted += len(batch_ids)
                db.flush()

            db.commit()
            return total_deleted
        except Exception as e:
            db.rollback()
            raise _batch_failure(e, "批量删除") from e


def _batch_failure(exc: Exception, action: str) -> Exception:
    """批量操作的出站安全异常（同 `_transaction_failure`：禁止内插异常原文）。"""
    mapped = map_db_exception(exc)
    if mapped is not None:
        logger.error("%s failed (constraint), rolled back", action, exc_info=True)
        return mapped
    logger.error("%s failed, rolled back", action, exc_info=True)
    return DatabaseError(f"{action}失败，请稍后重试或联系管理员")
