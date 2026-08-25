"""通用级联物理清除服务（回收站“彻底删除”统一实现）。

设计要点：
- 基于 SQLAlchemy 元数据的外键图 **自动发现** 引用表与引用列，
  深度优先先删依赖行、再删主行——新增子表无需维护手工清单，
  从根上避免 VillageCascadeDeleteService 式清单漂移。
- 与软删除体系解耦：操作对象就是已软删（is_active=False）的记录，
  调用方（回收站端点）负责权限收敛与密码二次确认。

用法::

    svc = CascadePurgeService(db)
    preview = svc.preview("supported_villages", 7)   # {"total_references": n, "details": {...}}
    stats = svc.purge("supported_villages", 7)       # 物理删除并返回统计
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class CascadePurgeService:
    """基于元数据外键图的通用级联清除。"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    def _load_graph(self, root_table: str):
        """返回 (直接引用 root 的 [(table, col)] 列表)。"""
        from app.models import Base

        refs = []
        for table in Base.metadata.tables.values():
            if table.name == root_table:
                continue
            for fk in table.foreign_keys:
                if fk.column.table.name == root_table:
                    refs.append((table.name, fk.parent.name))
        return refs

    def _count(self, table: str, col: str, rid: int) -> int:
        return self.db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :rid"),  # nosec B608 表名来自元数据白名单
            {"rid": rid},
        ).scalar() or 0

    def _delete(self, table: str, col: str, rid: int) -> int:
        res = self.db.execute(
            text(f"DELETE FROM {table} WHERE {col} = :rid"),  # nosec B608
            {"rid": rid},
        )
        return res.rowcount or 0

    # ------------------------------------------------------------------
    def preview(self, root_table: str, row_id: int) -> dict:
        """返回将级联删除的关联数据统计（不执行删除）。"""
        details = {}
        total = 0
        for tbl, col in self._load_graph(root_table):
            n = self._count(tbl, col, row_id)
            if n:
                details[tbl] = n
                total += n
                # 二级依赖：如 project → funds → fund_transactions
                for t2, c2 in self._load_graph(tbl):
                    if t2 == root_table:
                        continue
                    n2 = self._count_deep(t2, c2, tbl, col, row_id)
                    if n2:
                        key = f"{t2}(via {tbl})"
                        details[key] = n2
                        total += n2
        return {
            "root_table": root_table,
            "row_id": row_id,
            "total_references": total,
            "details": details,
        }

    def _count_deep(self, t2: str, c2: str, p_table: str, p_col: str, rid: int) -> int:
        return self.db.execute(
            text(
                f"SELECT COUNT(*) FROM {t2} WHERE {c2} IN "  # nosec B608
                f"(SELECT id FROM {p_table} WHERE {p_col} = :rid)"
            ),
            {"rid": rid},
        ).scalar() or 0

    def _delete_deep(self, t2: str, c2: str, p_table: str, p_col: str, rid: int) -> int:
        return self.db.execute(
            text(
                f"DELETE FROM {t2} WHERE {c2} IN "  # nosec B608
                f"(SELECT id FROM {p_table} WHERE {p_col} = :rid)"
            ),
            {"rid": rid},
        ).rowcount or 0

    # ------------------------------------------------------------------
    def purge(self, root_table: str, row_id: int) -> dict:
        """物理删除主行及全部层级依赖行，返回统计。"""
        logger.info("级联彻底删除 %s#%s 开始", root_table, row_id)
        stats: dict = {}
        total = 0

        # 先删二级依赖（孙表），再删一级子表，最后删主行
        for tbl, col in self._load_graph(root_table):
            for t2, c2 in self._load_graph(tbl):
                if t2 == root_table:
                    continue
                n2 = self._delete_deep(t2, c2, tbl, col, row_id)
                if n2:
                    key = f"{t2}(via {tbl})"
                    stats[key] = stats.get(key, 0) + n2
                    total += n2

        for tbl, col in self._load_graph(root_table):
            n = self._delete(tbl, col, row_id)
            if n:
                stats[tbl] = stats.get(tbl, 0) + n
                total += n

        res = self.db.execute(
            text(f"DELETE FROM {root_table} WHERE id = :rid"),  # nosec B608
            {"rid": row_id},
        )
        if (res.rowcount or 0) == 0:
            self.db.rollback()
            return {"success": False, "message": "记录不存在"}

        safe_commit(self.db)
        logger.info("级联彻底删除完成：%s#%s，共 %d 行", root_table, row_id, total + 1)
        return {
            "success": True,
            "deleted_records": total + 1,
            "details": stats,
        }
