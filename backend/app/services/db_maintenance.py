"""SQLite 定期维护 — VACUUM + PRAGMA optimize + WAL checkpoint。

在后台线程中定期执行，不阻塞主请求处理。

额外10：新增独立的每日凌晨 3 点 WAL checkpoint 调度（仅 TRUNCATE，不做 VACUUM，
避免 VACUUM 产生大量临时文件），主动回收 -wal 文件，防止长时间运行膨胀。
"""

import datetime
import logging
import threading

logger = logging.getLogger(__name__)

_maintenance_thread: threading.Thread | None = None
_stop_event = threading.Event()
# 维护间隔（秒）：首次 5 分钟后执行，之后每 6 小时
_INITIAL_DELAY = 300
_INTERVAL = 21600


def _run_maintenance():
    """后台线程：定期执行 SQLite 维护操作。"""
    if _stop_event.wait(_INITIAL_DELAY):  # 用 Event.wait 替代 time.sleep — stop 时立即唤醒
        return
    while not _stop_event.is_set():
        try:
            _do_maintenance()
        except Exception:
            logger.warning("数据库维护失败", exc_info=True)
        _stop_event.wait(_INTERVAL)


def _do_maintenance():
    """执行单次维护：VACUUM + PRAGMA optimize + WAL checkpoint。"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        conn = db.connection().connection  # raw sqlite3 connection
        cursor = conn.cursor()
        # WAL checkpoint: 将 WAL 数据写回主数据库，防止 WAL 无限增长
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        # 回收已删除记录的空间，整理碎片
        cursor.execute("VACUUM")
        # 更新查询优化器统计信息
        cursor.execute("PRAGMA optimize")
        cursor.close()
        logger.info("SQLite 定期维护完成 (WAL checkpoint + VACUUM + optimize)")
    except Exception as e:
        logger.warning("SQLite 维护操作失败: %s", e)
    finally:
        db.close()


def start_db_maintenance():
    """启动后台数据库维护线程。"""
    global _maintenance_thread
    if _maintenance_thread is not None:
        return
    _stop_event.clear()
    _maintenance_thread = threading.Thread(
        target=_run_maintenance, daemon=True, name="db-maintenance"
    )
    _maintenance_thread.start()
    logger.info("数据库定期维护已启动 (间隔 %d 秒)", _INTERVAL)


def stop_db_maintenance():
    """停止后台数据库维护线程。"""
    _stop_event.set()
    if _maintenance_thread:
        _maintenance_thread.join(timeout=1)
    logger.info("数据库定期维护已停止")


# ══════════════════════════════════════════════════════════════
#  额外10：每日凌晨 3 点 WAL checkpoint 调度（轻量，不含 VACUUM）
# ══════════════════════════════════════════════════════════════
_wal_thread: threading.Thread | None = None
_wal_stop_event = threading.Event()


def _seconds_until_next_3am(now: datetime.datetime | None = None) -> int:
    """计算距离下一个凌晨 3 点的秒数。"""
    now = now or datetime.datetime.now()
    next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += datetime.timedelta(days=1)
    return max(int((next_run - now).total_seconds()), 1)


def _run_wal_checkpoint():
    """后台线程：每天凌晨 3 点执行 PRAGMA wal_checkpoint(TRUNCATE)。"""
    # 等待到首个 3 点
    if _wal_stop_event.wait(_seconds_until_next_3am()):
        return
    while not _wal_stop_event.is_set():
        try:
            _do_wal_checkpoint()
        except Exception:
            logger.warning("WAL checkpoint 调度执行失败", exc_info=True)
        # 等待到下一个 3 点（约 24 小时后）
        if _wal_stop_event.wait(_seconds_until_next_3am()):
            return


def _do_wal_checkpoint():
    """执行单次 WAL checkpoint（TRUNCATE），不执行 VACUUM 以避免临时文件膨胀。"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        conn = db.connection().connection  # raw sqlite3 connection
        cursor = conn.cursor()
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = cursor.fetchone()
        cursor.close()
        logger.info("每日 WAL checkpoint 完成 (3:00) result=%s", result)
    except Exception as e:
        logger.warning("WAL checkpoint 失败: %s", e)
    finally:
        db.close()


def start_wal_checkpoint_scheduler():
    """启动每日凌晨 3 点的 WAL checkpoint 调度线程。"""
    global _wal_thread
    if _wal_thread is not None:
        return
    _wal_stop_event.clear()
    _wal_thread = threading.Thread(
        target=_run_wal_checkpoint, daemon=True, name="db-wal-checkpoint"
    )
    _wal_thread.start()
    logger.info("每日 WAL checkpoint 调度已启动 (凌晨 3:00)")


def stop_wal_checkpoint_scheduler():
    """停止每日 WAL checkpoint 调度线程。"""
    global _wal_thread
    _wal_stop_event.set()
    if _wal_thread:
        _wal_thread.join(timeout=1)
    # 必须复位句柄：否则同进程内二次进入 lifespan（测试用 TestClient、
    # 任何进程内重初始化）时 start_* 会因 _wal_thread is not None 直接
    # 返回，WAL 调度永久静默失效。
    _wal_thread = None
    logger.info("每日 WAL checkpoint 调度已停止")
