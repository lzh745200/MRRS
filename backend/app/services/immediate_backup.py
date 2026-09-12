"""
关键操作即时备份触发器（单机防丢失）

重大变更（数据导入/批量删除/恢复等）后自动触发一次备份，确保操作前数据可回退。
备份在后台线程执行，不阻塞 API 响应。
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_triggered_once = threading.Lock()


def trigger_immediate_backup(description: str = "关键操作前备份", delay: float = 0.0) -> bool:
    """
    触发一次即时备份（后台线程，幂等保护：同一时刻只允许一个在跑）。

    Args:
        description: 备份描述
        delay: 延迟秒数（避免与操作并发写库）

    Returns:
        True 已排队; False 已有备份在跑（跳过本次）
    """
    if not _triggered_once.acquire(blocking=False):
        logger.info("即时备份已在执行，跳过本次触发")
        return False

    def _run():
        try:
            import time

            if delay > 0:
                time.sleep(delay)
            from app.core.transaction import get_db_context
            from app.services.backup_service import BackupService
            from app.services.system_config_service import get_config

            with get_db_context() as db:
                target_dir = (get_config("backup_target_dir", "") or "").strip()
                svc = BackupService(db, backup_dir=target_dir) if target_dir else BackupService(db)
                svc.create_backup(
                    description=description,
                    include_uploads=False,
                )
                logger.info("即时备份完成: %s", description)
        except Exception as e:
            logger.error("即时备份失败: %s", e, exc_info=True)
        finally:
            _triggered_once.release()

    t = threading.Thread(target=_run, name="immediate-backup", daemon=True)
    try:
        t.start()
    except Exception:
        # 线程启动失败（如线程资源耗尽）时必须释放幂等锁，
        # 否则后续所有「关键操作前备份」都会走 29 行提前返回而被静默跳过
        _triggered_once.release()
        logger.error("即时备份线程启动失败", exc_info=True)
        return False
    return True
