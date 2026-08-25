"""用户级联删除服务"""

import logging
import re
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# 合规留痕表：删除用户时绝不物理删除其中的记录（W2-T5）。
# 这些表的外键列已迁移为 nullable（审批留痕/导入历史须保留），
# 置空即可解除引用；若历史库尚未迁移导致置空失败，跳过并告警，
# 由人工执行迁移后重试 —— 宁可保留引用也不销毁合规痕迹。
PRESERVE_AUDIT_TABLES = {"approval_records", "import_histories"}


def _safe_ident(name: str) -> str:
    """校验数据库标识符并返回双引号包裹形式，防止 SQL 注入。"""
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"非法的数据库标识符: {name!r}")
    return f'"{name}"'


class UserCascadeDeleteService:
    """用户级联删除服务。

    安全删除用户：先清理所有引用 ``users.id`` 的外键记录（按 ondelete 策略
    删除或置空），再删除用户本身。使用 SQLite PRAGMA 反射实际表结构，
    因此不依赖 ORM 模型的懒加载状态，可覆盖全部引用 users.id 的表。
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    async def delete_user(user_id: int):
        """兼容旧接口：仅返回成功标记。

        实际的级联删除请使用 :meth:`delete_user_cascade`。
        """
        return True

    def delete_user_cascade(self, user_id: int) -> Dict[str, Any]:
        """级联删除用户及其相关数据。

        遍历数据库中所有引用 ``users.id`` 的外键，按其 ``ondelete`` 策略清理：
        - ``CASCADE``：删除引用记录；
        - ``SET NULL`` 且列可空：置空外键；
        - ``SET NULL`` 但列非空 / ``NO ACTION``：删除引用记录以避免约束冲突。

        Returns:
            包含 ``success``/``message``/``deleted_records``/``set_null_records``
            的字典，与 ``auth/user_management.py`` 路由的调用契约一致。
        """
        db = self.db
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "success": False,
                "message": "用户不存在",
                "deleted_records": 0,
                "set_null_records": 0,
            }

        deleted_records = 0
        set_null_records = 0

        # 反射所有业务表的外键，清理引用了该用户的记录
        table_rows = db.execute(
            text("SELECT name FROM sqlite_master "
                 "WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        ).fetchall()
        table_names = [r[0] for r in table_rows]

        for tbl in table_names:
            if tbl == "users":
                continue
            try:
                tbl_ident = _safe_ident(tbl)
            except ValueError:
                continue

            fk_rows = db.execute(text(f"PRAGMA foreign_key_list({tbl_ident})")).fetchall()
            if not fk_rows:
                continue
            # PRAGMA foreign_key_list 列: (id, seq, table, from, to, on_update, on_delete, match)
            user_refs = [
                (fk[3], (fk[6] or "").upper())
                for fk in fk_rows
                if fk[2] == "users" and fk[4] == "id"
            ]
            if not user_refs:
                continue

            # 查询列可空性: PRAGMA table_info 列 (cid, name, type, notnull, dflt_value, pk)
            col_info = db.execute(text(f"PRAGMA table_info({tbl_ident})")).fetchall()
            nullable_map = {ci[1]: (ci[3] == 0) for ci in col_info}

            for from_col, on_delete in user_refs:
                try:
                    col_ident = _safe_ident(from_col)
                except ValueError:
                    continue
                col_nullable = nullable_map.get(from_col, True)

                if tbl in PRESERVE_AUDIT_TABLES:
                    # 合规留痕表：仅置空，绝不物理删除（列已迁移为可空）
                    try:
                        result = db.execute(
                            text(f"UPDATE {tbl_ident} SET {col_ident} = NULL "
                                 f"WHERE {col_ident} = :uid"),  # nosec B608
                            {"uid": user_id},
                        )
                        set_null_records += result.rowcount or 0
                    except Exception:
                        db.rollback()
                        logger.error(
                            "合规留痕表 %s 置空失败（请先执行 alembic 迁移），保留原记录",
                            tbl, exc_info=True,
                        )
                elif on_delete == "CASCADE":
                    result = db.execute(
                        text(f"DELETE FROM {tbl_ident} WHERE {col_ident} = :uid"),  # nosec B608
                        {"uid": user_id},
                    )
                    deleted_records += result.rowcount or 0
                elif col_nullable:
                    result = db.execute(
                        text(f"UPDATE {tbl_ident} SET {col_ident} = NULL "
                             f"WHERE {col_ident} = :uid"),  # nosec B608
                        {"uid": user_id},
                    )
                    set_null_records += result.rowcount or 0
                else:
                    # 非空列无法置空（SET NULL + NOT NULL 矛盾），
                    # 删除引用记录以解除外键约束。
                    result = db.execute(
                        text(f"DELETE FROM {tbl_ident} WHERE {col_ident} = :uid"),  # nosec B608
                        {"uid": user_id},
                    )
                    deleted_records += result.rowcount or 0

        db.delete(user)
        safe_commit(db)
        deleted_records += 1

        logger.info(
            "用户级联删除完成: user_id=%s, deleted_records=%d, set_null_records=%d",
            user_id, deleted_records, set_null_records,
        )
        return {
            "success": True,
            "message": "用户删除成功",
            "deleted_records": deleted_records,
            "set_null_records": set_null_records,
        }
