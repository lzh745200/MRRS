"""add deleted_at to soft-delete tables (recycle retention)

Revision ID: recycle_retention_001
Revises: perm_pack_001
Create Date: 2026-08-25 10:00:00

为 supported_villages / projects / funds / schools 四张软删表增加 deleted_at
时间戳列（回收站保留期计算依据）。幂等：应用启动的 _migrate_missing_columns
可能已建同名列，存在则跳过，保证 alembic upgrade 在任意历史库上可重放。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "recycle_retention_001"
down_revision = "perm_pack_001"
branch_labels = None
depends_on = None

_TABLES = ["supported_villages", "projects", "funds", "schools"]


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade():
    """Add nullable deleted_at column to the four soft-delete tables."""
    for table in _TABLES:
        if not _has_column(table, "deleted_at"):
            op.add_column(
                table,
                sa.Column(
                    "deleted_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                    comment="软删时间(回收站保留期计算依据)",
                ),
            )


def downgrade():
    """Remove deleted_at column from the four soft-delete tables."""
    for table in _TABLES:
        if _has_column(table, "deleted_at"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("deleted_at")
