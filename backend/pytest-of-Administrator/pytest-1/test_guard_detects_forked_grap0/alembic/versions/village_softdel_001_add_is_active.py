"""add is_active column to supported_villages for soft delete

Revision ID: village_softdel_001
Revises: village_status_001
Create Date: 2026-07-05 10:00:00

为 supported_villages 表增加 is_active 软删字段，与 schools/projects 一致。
默认 True，删除操作置 False（软删），列表默认过滤，详情可见。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "village_softdel_001"
down_revision = "village_status_001"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in [c["name"] for c in insp.get_columns(table)]


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return index_name in [i["name"] for i in insp.get_indexes(table)]


def upgrade():
    """Add is_active column to supported_villages table.

    幂等：应用启动的 _migrate_missing_columns 可能已建同名列/索引，
    存在则跳过，保证 alembic upgrade 在任意历史库上可重放。
    """
    if not _has_column("supported_villages", "is_active"):
        op.add_column(
            "supported_villages",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
                comment="是否启用(软删标记)",
            ),
        )
    # 为现有行设置默认值
    op.execute("UPDATE supported_villages SET is_active = 1 WHERE is_active IS NULL")
    # 加索引便于列表过滤
    if not _has_index("supported_villages", "ix_supported_villages_is_active"):
        op.create_index("ix_supported_villages_is_active", "supported_villages", ["is_active"])


def downgrade():
    """Remove is_active column from supported_villages table."""
    op.drop_index("ix_supported_villages_is_active", table_name="supported_villages")
    with op.batch_alter_table("supported_villages") as batch_op:
        batch_op.drop_column("is_active")
