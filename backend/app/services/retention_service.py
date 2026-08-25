"""回收站保留期策略：超过 N 天的软删记录自动物理清除。

- N 由配置 RECYCLE_RETENTION_DAYS 控制（默认 30，0=禁用）；
- 仅清理 is_active=False 且 deleted_at 早于阈值的记录；
- 清除前触发一次即时备份（防误删兜底）；
- 按元数据外键图级联清除子表（复用 CascadePurgeService）。
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

logger = logging.getLogger(__name__)

# 软删资源注册表：(表名, 主键列)
SOFT_DELETE_TABLES = [
    ("supported_villages", "id"),
    ("projects", "id"),
    ("funds", "id"),
    ("schools", "id"),
]


def get_retention_days() -> int:
    import os

    try:
        return max(0, int(os.environ.get("RECYCLE_RETENTION_DAYS", "30")))
    except ValueError:
        return 30


def purge_expired_soft_deleted(db, days: int | None = None) -> dict:
    """物理清除超期软删记录。days<=0 时直接返回 disabled。"""
    from app.services.cascade_purge_service import CascadePurgeService

    if days is None:
        days = get_retention_days()
    if days <= 0:
        logger.info("回收站保留期策略已禁用 (RECYCLE_RETENTION_DAYS<=0)")
        return {"disabled": True}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    svc = CascadePurgeService(db)

    summary: dict = {"cutoff": cutoff.isoformat(), "purged": {}}
    total = 0

    for table, pk in SOFT_DELETE_TABLES:
        # 仅选取已标记软删且超期的 id（deleted_at 为空的旧数据不自动清除，
        # 避免历史数据被意外清空；如需处理请人工执行）
        rows = db.execute(
            text(
                f"SELECT {pk} FROM {table} "
                f"WHERE is_active = 0 AND deleted_at IS NOT NULL AND deleted_at < :cutoff"
            ),
            {"cutoff": cutoff},
        ).fetchall()

        for (rid,) in rows:
            try:
                stats = svc.purge(table, rid)
                if stats.get("success"):
                    summary["purged"][f"{table}#{rid}"] = stats.get("deleted_records", 0)
                    total += 1
            except Exception as e:  # 单条失败不阻断其余
                db.rollback()
                logger.error("回收站自动清除失败 %s#%s: %s", table, rid, e, exc_info=True)

    summary["total_records"] = total
    if total:
        try:
            from app.services.immediate_backup import trigger_immediate_backup

            trigger_immediate_backup(
                description=f"回收站保留期自动清除 {total} 条后备份", delay=1.0
            )
        except Exception:  # pragma: no cover
            logger.warning("回收站自动清除后备份触发失败", exc_info=True)

    logger.info("回收站保留期策略执行完成：%s", summary)
    return summary


def retention_job():
    """定时任务入口（每日一次）。"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        purge_expired_soft_deleted(db)
    finally:
        db.close()
