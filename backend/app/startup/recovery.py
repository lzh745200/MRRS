"""启动恢复钩子：token 黑名单 / 中断导出任务（B3 自 main.py 迁入，逻辑不变）。"""

import logging

logger = logging.getLogger("assistance_management")


def _load_token_blacklist():
    """启动时从数据库恢复 token 黑名单到内存。"""
    try:
        from app.core.database import SessionLocal
        from app.core.token_blacklist import load_from_db
        db = SessionLocal()
        try:
            count = load_from_db(db)
            if count:
                logger.info("Token 黑名单已恢复: %d 条记录", count)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Token 黑名单加载失败: %s", e)


def _recover_interrupted_exports():
    """启动时恢复中断的异步导出任务（架构评估 A1）。

    任务队列（task_queue）为进程内存态，重启后队列清空；export_tasks 中
    残留的 pending/processing 行将永远无人推进。此处统一回写为 failed，
    让用户可重新发起导出。失败仅告警不阻断启动（与既有启动钩子一致）。
    """
    try:
        from app.core.database import SessionLocal
        from app.services.async_export_service import recover_stale_export_tasks

        db = SessionLocal()
        try:
            recovered = recover_stale_export_tasks(db)
            if recovered:
                logger.warning(
                    "启动恢复：已将 %d 个中断导出任务标记为失败（原队列随重启丢失）",
                    recovered,
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning("导出任务恢复检查失败: %s", e)
