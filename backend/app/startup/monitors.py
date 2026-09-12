"""启动监控/调度钩子（B3 自 main.py 迁入，逻辑不变）。

资源监控、数据库健康监控、审批提醒、WAL checkpoint 调度、备份调度器、
数据库维护（已禁用）。全部为薄封装：try/except 兜底 + 委托给 services 层。
"""

import logging
import threading

logger = logging.getLogger("assistance_management")


def _start_resource_monitoring():
    """启动资源监控"""
    try:
        from app.services.resource_limiter import resource_limiter

        resource_limiter.start_monitoring()
        logger.info("资源监控已启动")
    except Exception as e:
        logger.warning("启动资源监控失败: %s", e)


def _stop_resource_monitoring():
    """停止资源监控"""
    try:
        from app.services.resource_limiter import resource_limiter

        resource_limiter.stop_monitoring()
        logger.info("资源监控已停止")
    except Exception as e:
        logger.warning("停止资源监控失败: %s", e)


def _start_database_health_monitoring():
    """启动数据库健康监控"""
    try:
        from app.services.database_health_service import database_health_service

        database_health_service.start_monitoring()
        logger.info("数据库健康监控已启动")
    except Exception as e:
        logger.warning("启动数据库健康监控失败: %s", e)


def _stop_database_health_monitoring():
    """停止数据库健康监控"""
    try:
        from app.services.database_health_service import database_health_service

        database_health_service.stop_monitoring()
        logger.info("数据库健康监控已停止")
    except Exception as e:
        logger.warning("停止数据库健康监控失败: %s", e)


def _start_approval_reminder():
    """启动审批超时提醒后台服务"""
    global _approval_reminder
    try:
        from app.services.reminder_service import start_approval_reminder

        _approval_reminder = start_approval_reminder(check_interval_minutes=30)
        logger.info("审批超时提醒服务已启动")
    except Exception as e:
        logger.warning("启动审批提醒服务失败: %s", e)


def _stop_approval_reminder():
    """停止审批超时提醒后台服务"""
    global _approval_reminder
    try:
        from app.services.reminder_service import stop_approval_reminder

        stop_approval_reminder(_approval_reminder)
        _approval_reminder = None
        logger.info("审批超时提醒服务已停止")
    except Exception as e:
        logger.warning("停止审批提醒服务失败: %s", e)


# 审批提醒服务全局引用（原 main.py 模块级状态随钩子一并迁入）
_approval_reminder = None


def _start_db_maintenance():
    """启动 SQLite 定期维护（VACUUM + PRAGMA optimize）。"""
    try:
        from app.services.db_maintenance import start_db_maintenance
        start_db_maintenance()
    except Exception as e:
        logger.warning("数据库维护启动失败: %s", e)


def _stop_db_maintenance():
    """停止 SQLite 定期维护。"""
    try:
        from app.services.db_maintenance import stop_db_maintenance
        stop_db_maintenance()
    except Exception as e:
        logger.warning("数据库维护停止失败: %s", e)


def _start_wal_checkpoint_scheduler():
    """启动每日凌晨 3 点 WAL checkpoint 调度（额外10）。"""
    try:
        from app.services.db_maintenance import start_wal_checkpoint_scheduler
        start_wal_checkpoint_scheduler()
    except Exception as e:
        logger.warning("WAL checkpoint 调度启动失败: %s", e)


def _stop_wal_checkpoint_scheduler():
    """停止每日 WAL checkpoint 调度。"""
    try:
        from app.services.db_maintenance import stop_wal_checkpoint_scheduler
        stop_wal_checkpoint_scheduler()
    except Exception as e:
        logger.warning("WAL checkpoint 调度停止失败: %s", e)


def _start_backup_scheduler():
    """启动备份调度器（自动备份/异常检测/待办提醒/周报/KPI 预计算/恢复演练）。"""
    try:
        from app.services.backup_scheduler import start_backup_scheduler
        start_backup_scheduler()
    except Exception as e:
        logger.warning("备份调度器启动失败: %s", e)


def _run_database_startup_check():
    """启动时后台执行数据库快速自检（不阻塞启动）。"""
    def _run():
        try:
            from app.services.database_health_service import database_health_service
            result = database_health_service.startup_check()
            if result.get("status") != "ok":
                logger.warning("数据库启动自检异常: %s", result.get("message", "unknown"))
            else:
                logger.info("数据库启动自检通过 (%s)", result.get("db_size_mb", "?"))
        except Exception as e:  # pragma: no cover
            logger.warning("数据库启动自检失败: %s", e)

    threading.Thread(target=_run, name="db-startup-check", daemon=True).start()


def _stop_backup_scheduler():
    """停止备份调度器。"""
    try:
        from app.services.backup_scheduler import stop_backup_scheduler
        stop_backup_scheduler()
    except Exception as e:
        logger.warning("备份调度器停止失败: %s", e)
