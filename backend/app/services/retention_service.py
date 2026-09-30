"""回收站保留期策略：超过 N 天的软删记录自动物理清除。

- N 由配置 RECYCLE_RETENTION_DAYS 控制（默认 30，0=禁用）；
- 仅清理 is_active=False 且 deleted_at 早于阈值的记录；
- 清除前触发一次即时备份（防误删兜底）——**备份在清除之前**，备份失败则本轮
  清除中止（2026-09-30 深审 #55 修复：原实现把备份放在清除之后，快照不含被删行，
  兜底名存实亡）；
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

    # 深审 #55：本模块 docstring 承诺"清除前触发一次即时备份（防误删兜底）"，
    # 但原实现把备份放在**清除循环之后**——快照里已经没有待删行，兜底事实上
    # 不存在。改为先算出待删清单、先备份、再执行清除（备份失败即中止本轮，
    # 不做无兜底的物理删除）。
    planned: list[tuple[str, str, int]] = []
    for table, pk in SOFT_DELETE_TABLES:
        rows = db.execute(  # nosec B608 - table/pk from code constants, value parameterized
            text(
                f"SELECT {pk} FROM {table} "  # nosec B608
                f"WHERE is_active = 0 AND deleted_at IS NOT NULL AND deleted_at < :cutoff"
            ),
            {"cutoff": cutoff},
        ).fetchall()
        planned.extend((table, pk, rid) for (rid,) in rows)

    if not planned:
        summary["total_records"] = 0
        logger.info("回收站保留期策略执行完成：无可清除记录 %s", summary)
        return summary

    try:
        from app.services.immediate_backup import trigger_immediate_backup

        trigger_immediate_backup(
            description=f"回收站保留期自动清除 {len(planned)} 条前备份", delay=1.0
        )
    except Exception:
        # fail-closed：没有兜底快照就不做物理删除（软删记录可人工再清）
        logger.error("回收站自动清除前备份失败，本轮清除中止", exc_info=True)
        summary["backup_failed"] = True
        return summary

    for table, pk, rid in planned:
        try:
            stats = svc.purge(table, rid)
            if stats.get("success"):
                summary["purged"][f"{table}#{rid}"] = stats.get("deleted_records", 0)
                total += 1
        except Exception as e:  # 单条失败不阻断其余
            db.rollback()
            logger.error("回收站自动清除失败 %s#%s: %s", table, rid, e, exc_info=True)

    summary["total_records"] = total
    logger.info("回收站保留期策略执行完成：%s", summary)
    return summary
