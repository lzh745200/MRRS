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
from typing import List

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

    def _descendant_chains(self, root_table: str) -> List[List[tuple]]:
        """从根表出发做 DFS，返回自底向上的"删除链"列表。

        每个链形如 [(leaf_table, leaf_col, parent_table, parent_col), ..., (t1, c1, root, root_pk)]，
        按由深到浅排列 —— 调用方按此顺序 DELETE，可保证外键始终先于被引用行删除。

        深审 #1：原实现只做两层（root → 子表 → 孙表），supported_villages ←
        projects ← funds ← fund_transactions 这类**第三级**依赖不会被删除，
        残留孤儿行；且跨分支删除顺序随元数据序，先删 projects 分支会连带影响
        funds 分支的定位条件。改为访问集 DFS + 自底向上展开。
        """
        visited: set = set()
        chains: List[List[tuple]] = []

        def walk(table: str, root_pk: str, lineage: List[tuple], seen: set) -> None:
            for child, col in self._load_graph(table):
                if child == root_table or child in seen:
                    continue
                # child 直接引用 table（经由 table 的主键）
                link = (child, col, table, root_pk)
                new_lineage = lineage + [link]
                chains.append(list(reversed(new_lineage)))
                walk(child, "id", new_lineage, seen | {child})

        # root 的主键列固定为 id（与 _delete 用的 WHERE id 一致）
        walk(root_table, "id", [], visited)
        return chains

    def _delete_chain(self, chain: List[tuple], rid: int) -> int:
        """按链删除（最深层用子查询锚定到根行），返回删除行数。"""
        total = 0
        # chain 已按由深到浅排列：最深的一跳用 IN (SELECT ... WHERE root_pk = :rid)
        for idx, (table, col, parent, parent_pk) in enumerate(chain):
            if idx == 0:
                sql = (
                    f"DELETE FROM {table} WHERE {col} IN "  # nosec B608
                    f"(SELECT {parent_pk} FROM {parent} WHERE id = :rid)"
                )
            else:
                # 中间层已由上一跳删除，这里用"不在父表中"兜底清理残留
                sql = (
                    f"DELETE FROM {table} WHERE {col} NOT IN "  # nosec B608
                    f"(SELECT {parent_pk} FROM {parent})"
                )
            total += self.db.execute(text(sql), {"rid": rid}).rowcount or 0
        return total

    # ------------------------------------------------------------------
    def purge(self, root_table: str, row_id: int) -> dict:
        """物理删除主行及全部层级依赖行，返回统计。

        **自底向上**：先删最深依赖，再逐层向上，最后删主行（深审 #1）。
        """
        logger.info("级联彻底删除 %s#%s 开始", root_table, row_id)
        stats: dict = {}
        total = 0

        # 依赖链按"深度降序"处理：深的先删
        chains = sorted(self._descendant_chains(root_table), key=len, reverse=True)
        deep_deleted: set = set()
        for chain in chains:
            head = chain[0]
            key = f"{head[0]}(via {head[2]})"
            if key in deep_deleted:
                continue
            n = self._delete_chain(chain, row_id)
            if n:
                stats[key] = stats.get(key, 0) + n
                total += n
            deep_deleted.add(key)

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
