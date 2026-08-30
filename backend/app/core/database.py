"""
Database engine and session configuration.

离线桌面管理系统 - 数据库核心配置
针对 SQLite 进行了深度调优，确保在单机/多机物理协同环境下的数据一致性与极致性能。

SQLite 性能优化策略：
1. WAL (Write-Ahead Logging) 模式：实现并发读写，读写互不阻塞。
2. NORMAL 同步模式：在 WAL 下兼顾数据安全与写入性能。
3. 动态 PRAGMA 调优：根据现代硬件自动调整 cache_size (64MB) 和 mmap_size (可配，默认 128MB)。
4. 长事务独占锁机制：解决大批量数据导入 (.rrs) 时的 SQLITE_BUSY 问题。
"""

import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Generator, Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger(__name__)


# 模块级常量：SQLite PRAGMA 调优值（避免每次连接重复计算）
def _parse_env_int(key: str, default: int) -> int:
    """从环境变量解析整数值，非数字值时给出清晰错误并回退到默认。"""
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s=%r 不是有效整数，使用默认值 %d", key, raw, default)
        return default


SQLITE_MMAP_SIZE = _parse_env_int("SQLITE_MMAP_SIZE", 134217728)  # 默认 128MB
SQLITE_CACHE_SIZE = _parse_env_int("SQLITE_CACHE_SIZE", -64000)    # 默认 64MB

DATABASE_URL = settings.DATABASE_URL
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# SQLite 必须禁用线程检查，以支持 FastAPI 的多线程/协程环境
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

# 引擎配置
# 对于 SQLite，使用 QueuePool 并限制连接数，避免过多连接导致文件锁竞争
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool if IS_SQLITE else None,
    pool_size=getattr(settings, "DB_POOL_SIZE", 10),
    max_overflow=getattr(settings, "DB_MAX_OVERFLOW", 20),
    pool_pre_ping=getattr(settings, "DB_POOL_PRE_PING", True),  # 连接池健康检查
    pool_recycle=getattr(settings, "DB_POOL_RECYCLE", 3600),    # 每小时回收连接
    pool_timeout=getattr(settings, "DB_POOL_TIMEOUT", 30),      # 获取连接超时
    echo=getattr(settings, "DB_ECHO", False),                   # SQL 日志（调试用）
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "after_cursor_execute")
def _count_query_execution(conn, cursor, statement, parameters, context, executemany) -> None:
    """N+1 检测：SQL 执行计数写入当前请求的 contextvar 计数器（query_counter 中间件消费）。"""
    from app.middleware.query_counter import _on_cursor_execute

    _on_cursor_execute(conn, cursor, statement, parameters, context, executemany)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """
    每次建立新连接时，自动执行 SQLite PRAGMA 性能调优。
    仅在 SQLite 数据库下生效。
    """
    if not IS_SQLITE:
        return

    cursor = dbapi_connection.cursor()

    # 0. SQLCipher 加密支持（零信任安全要求，W5-T7）
    # PRAGMA key 必须是连接的首条语句（先于 journal_mode 等），且普通 sqlite3
    # 驱动会静默忽略 PRAGMA key 造成"假加密"——启用加密时必须探测到 SQLCipher
    # 驱动，否则拒绝启动（fail-closed，保留现场优于静默明文）。
    if getattr(settings, "DB_ENCRYPTION_ENABLED", False):
        try:
            cipher_version = cursor.execute("PRAGMA cipher_version").fetchone()
        except Exception as _probe_err:
            cipher_version = None
            logger.warning("SQLCipher 探测异常: %s", _probe_err)
        if not cipher_version:
            cursor.close()
            raise RuntimeError(
                "DB_ENCRYPTION_ENABLED 已启用，但当前 sqlite3 驱动不支持 SQLCipher"
                "（PRAGMA key 会被静默忽略导致假加密）。请安装 pysqlcipher3/sqlcipher3，"
                "或显式关闭 DB_ENCRYPTION_ENABLED。"
            )
        # 兼容 PyInstaller 打包后的绝对路径
        base_dir = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent))
        key_file = base_dir / "config" / "db.key"
        if not key_file.exists():
            cursor.close()
            raise RuntimeError(f"未找到数据库加密密钥文件: {key_file}（DB_ENCRYPTION_ENABLED 已启用）")
        key = key_file.read_text(encoding="utf-8").strip()
        if not key:
            cursor.close()
            raise RuntimeError(f"数据库加密密钥文件为空: {key_file}")
        # SQLCipher 的 PRAGMA key 不支持绑定参数，须为字面量；密钥来自本机文件，转义后使用
        safe_key = key.replace("'", "''")
        cursor.execute(f"PRAGMA key = '{safe_key}'")
        logger.info("SQLCipher 数据库加密已启用 (cipher=%s)", cipher_version[0])

    # 1. 核心日志与一致性
    cursor.execute("PRAGMA journal_mode=WAL")         # 启用 WAL 模式，支持并发读写
    cursor.execute("PRAGMA foreign_keys=ON")          # 强制外键约束

    # 2. 性能与安全性平衡
    # WAL 模式下 NORMAL 已经足够安全，无需 FULL（FULL 会严重拖慢写入）
    cursor.execute("PRAGMA synchronous=NORMAL")

    # 3. 锁等待与超时 (本地环境硬件可能较慢或存在大事务，放宽至 10 秒)
    cursor.execute("PRAGMA busy_timeout=10000")

    # 4. 内存与缓存调优 (针对现代 PC/工控机，适当放大；可通过环境变量覆盖)
    cursor.execute(f"PRAGMA cache_size={SQLITE_CACHE_SIZE}")
    cursor.execute(f"PRAGMA mmap_size={SQLITE_MMAP_SIZE}")
    cursor.execute("PRAGMA temp_store=MEMORY")        # 临时表/索引存储在内存中

    # 5. WAL 维护
    cursor.execute("PRAGMA wal_autocheckpoint=1000")  # 每 1000 页自动 checkpoint

    # 6. 查询优化器
    cursor.execute("PRAGMA automatic_index=ON")       # 允许自动创建临时索引

    cursor.close()
    logger.debug("SQLite PRAGMAs 初始化完成: WAL, cache=%dKB, mmap=%dMB, timeout=10s",
                 abs(SQLITE_CACHE_SIZE), SQLITE_MMAP_SIZE // (1024 * 1024))


@event.listens_for(engine, "close")
def _on_connection_close(dbapi_connection: Any, connection_record: Any) -> None:
    """连接关闭时执行 PRAGMA optimize，帮助 SQLite 优化查询计划。"""
    if not IS_SQLITE:
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA optimize")
        cursor.close()
    except Exception:
        # 连接关闭时的优化失败不应影响正常流程
        pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供数据库 Session，并在请求结束后自动关闭。

    异常时显式 rollback，避免连接池复用时携带脏事务状态。
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 数据库写入协调器 (SQLite Write Coordinator)
#
# 设计原则：
# 1. 短事务 (常规 CRUD)：依赖 WAL + busy_timeout=10000 自动重试，无需加锁，性能最高。
# 2. 长事务 (.rrs 导入、大批量更新)：使用 exclusive_write() 获取独占锁，防止
#    长事务被 busy_timeout 截断，同时避免阻塞其他短事务的读取。
# ---------------------------------------------------------------------------

class SQLiteWriteCoordinator:
    """
    SQLite 写入协调器。
    解决高并发或长事务下的 SQLITE_BUSY 问题。
    """

    def __init__(self):
        # 使用 threading.Lock 实现进程内的互斥锁
        self._lock = threading.Lock()
        # 保留 Queue 以兼容旧版 enqueue 调用（不推荐在新代码中使用）
        self._queue: Queue = Queue()
        self._worker: threading.Thread | None = None

    @contextmanager
    def exclusive_write(self, timeout: float = 60.0) -> Iterator[None]:
        """
        长事务独占写上下文管理器。

        用法：
            with db_coordinator.exclusive_write():
                with SessionLocal() as session:
                    session.bulk_insert_mappings(...)
                    session.commit()
        """
        if not IS_SQLITE:
            # 非 SQLite 数据库（如测试时用的内存库或未来的 PG/MySQL）无需此锁
            yield
            return

        acquired = self._lock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(
                f"获取数据库独占写锁超时（{timeout}秒）。"
                "可能有其他大型数据导入任务正在执行，请稍后重试。"
            )
        try:
            yield
        finally:
            self._lock.release()

    def _ensure_worker(self) -> None:
        """懒加载启动后台写入线程（仅用于兼容旧的 enqueue 方法）。"""
        if self._worker is None:
            self._worker = threading.Thread(
                target=self._process_queue,
                daemon=True,
                name="sqlite-write-worker"
            )
            self._worker.start()

    def enqueue(self, fn: Callable[[], Any], timeout: float = 30.0) -> Any:
        """
        [向后兼容] 将写操作放入队列串行执行。
        ⚠️ 警告：在 FastAPI 同步路由中调用此方法会阻塞工作线程。
        建议新代码使用 `exclusive_write()` 上下文管理器，并将长任务放入 BackgroundTasks。
        """
        self._ensure_worker()
        result_holder: dict = {"result": None, "error": None, "done": threading.Event()}
        self._queue.put((fn, result_holder))

        if not result_holder["done"].wait(timeout):
            raise TimeoutError(f"数据库写入队列操作超时（{timeout}秒）")
        if result_holder["error"]:
            raise result_holder["error"]
        return result_holder["result"]

    def _process_queue(self) -> None:
        """后台线程：持续消费队列中的写操作。"""
        while True:
            fn, holder = self._queue.get()
            try:
                # 在队列消费时，也加上独占锁，确保绝对串行
                with self.exclusive_write(timeout=60.0):
                    holder["result"] = fn()
            except Exception as e:
                holder["error"] = e
            finally:
                holder["done"].set()
                self._queue.task_done()

    @property
    def pending(self) -> int:
        """队列中等待的写操作数量。"""
        return self._queue.qsize()


# 全局单例：在整个应用生命周期内共享
db_coordinator = SQLiteWriteCoordinator()

# 向后兼容别名
write_queue = db_coordinator
SQLiteWriteQueue = SQLiteWriteCoordinator  # 旧类名别名


def check_disk_space(min_mb: int = 100, path: str | None = None) -> dict:
    """
    检查指定路径所在磁盘的剩余空间（W12-T045：支持自定义 path）。

    Args:
        min_mb: 最小所需空间（MB），默认 100MB
        path: 待检查目录；默认数据库目录

    Returns:
        dict: {
            "free_mb": 剩余空间(MB),
            "total_mb": 总空间(MB),
            "sufficient": 是否充足,
            "path": 目录路径
        }
    """
    import shutil

    if path is None:
        db_path = Path(DATABASE_URL.replace("sqlite:///", ""))
        check_dir = db_path.parent
    else:
        check_dir = Path(path)

    # 目录可能尚未创建（如首次备份前），向上回溯到最近存在的父目录再检查
    resolved = check_dir
    while not resolved.exists() and resolved != resolved.parent:
        resolved = resolved.parent
    if not resolved.exists():
        resolved = Path.cwd()
    check_dir = resolved

    try:
        usage = shutil.disk_usage(str(check_dir))
        free_mb = usage.free // (1024 * 1024)
        total_mb = usage.total // (1024 * 1024)
        return {
            "free_mb": free_mb,
            "total_mb": total_mb,
            "sufficient": free_mb >= min_mb,
            "path": str(check_dir),
        }
    except Exception as e:
        logger.error("磁盘空间检查失败: %s", e)
        return {
            "free_mb": -1,
            "total_mb": -1,
            "sufficient": False,
            "path": str(check_dir),
            "error": str(e),
        }
