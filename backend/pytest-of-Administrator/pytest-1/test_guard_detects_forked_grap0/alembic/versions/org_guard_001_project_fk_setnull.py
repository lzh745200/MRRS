"""组织删除级联守卫：Project.organization_id 外键 CASCADE→SET NULL（W2-T2 / ADR-0003）

与其他实体（指向组织均 SET NULL）对齐：硬删组织不再连带物理删除项目
（项目→资金/合同/凭证的级联链随之截断）。应用层另有 OrganizationInUseError
守卫要求先迁移名下数据。

实现说明：基线建表的 SQLite 外键为匿名约束，无法按名 drop。采用 SQLite 官方
"影子表"变更舞步：foreign_keys=OFF → 建影子表（DDL 替换外键动作）→ 拷贝数据 →
删旧表 → 改名 → 重建索引。列集与顺序完全同源自同一 DDL，INSERT SELECT * 安全。

降级说明：downgrade 以同样舞步把 SET NULL 换回 CASCADE。

Revision ID: org_guard_001
Revises: pii_encrypt_001
Create Date: 2026-08-30
"""
import logging

from sqlalchemy import text

from alembic import op

revision = "org_guard_001"
down_revision = "pii_encrypt_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime")

_OLD = "REFERENCES organizations (id) ON DELETE CASCADE"
_NEW = "REFERENCES organizations (id) ON DELETE SET NULL"


def _rebuild(conn, ondelete: str) -> None:
    # 0. 外键必须先关（本迁移连接独立于应用引擎，默认即 OFF，显式声明防御两者）
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='projects'")
        ).scalar_one()
        if f"ON DELETE {ondelete}" in ddl and "organization_id" in ddl:
            already = ondelete == "SET NULL" and _NEW in ddl
            if already or (ondelete == "CASCADE" and _OLD in ddl):
                logger.info("projects 外键已为 %s，跳过", ondelete)
                return

        # 1. 影子表：同源 DDL 仅替换目标外键动作
        shadow_ddl = ddl.replace("CREATE TABLE projects", "CREATE TABLE projects_new_guard", 1)
        if ondelete == "SET NULL":
            assert _OLD in ddl, "projects DDL 中未找到预期的 CASCADE 外键定义"
            shadow_ddl = shadow_ddl.replace(_OLD, _NEW, 1)
        else:
            shadow_ddl = shadow_ddl.replace(_NEW, _OLD, 1)
        conn.execute(text(shadow_ddl))

        # 2. 拷数据（同源 DDL 列序一致）
        conn.execute(text("INSERT INTO projects_new_guard SELECT * FROM projects"))

        # 3. 记录并删除旧表（FK OFF，无级联副作用）
        indexes = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='projects' AND sql IS NOT NULL")
        ).fetchall()
        conn.execute(text("DROP TABLE projects"))

        # 4. 影子表转正（此时其他表的 REFERENCES 仍指向 'projects' 名，未被改动）
        conn.execute(text("ALTER TABLE projects_new_guard RENAME TO projects"))

        # 5. 重建索引（DROP TABLE 时随表移除）
        for (idx_sql,) in indexes:
            conn.execute(text(idx_sql))
    finally:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    logger.info("projects.organization_id 外键已改为 ondelete=%s", ondelete)


def upgrade() -> None:
    _rebuild(op.get_bind(), "SET NULL")


def downgrade() -> None:
    _rebuild(op.get_bind(), "CASCADE")
