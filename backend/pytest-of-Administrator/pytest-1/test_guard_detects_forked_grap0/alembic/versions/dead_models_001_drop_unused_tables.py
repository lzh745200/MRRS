"""drop unused feature tables (dead code cleanup)

8 张零引用 ORM 模型对应的表已随模型删除。清理前已在本地全部数据库
验证行数均为 0（功能从未启用）。删除顺序先子表/独立表，最后主表。

Revision ID: dead_models_001
Revises: fk_ondelete_001
Create Date: 2026-08-29
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "dead_models_001"
down_revision = "fk_ondelete_001"
branch_labels = None
depends_on = None

# (table_name, referenced_by_fk) —— 仅需删除被引用的子表在先
TABLES = [
    "effectiveness_indicators",
    "version_history",
    "package_edit_logs",
    "user_sessions",
    "fee_standards",
    "inspection_rules",
    "data_versions",
    "army_units",
]


def upgrade() -> None:
    from sqlalchemy import text

    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    }
    for table in TABLES:
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:
    # 不可逆：这 8 张表对应的功能代码已整体移除，无模型可据以重建。
    # drop_table 本身即破坏性操作，downgrade 留空（升级前应确保已备份）。
    pass
