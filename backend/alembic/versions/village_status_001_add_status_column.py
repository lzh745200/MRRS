"""add status column to villages

Revision ID: village_status_001
Revises: rev_tier_bool_001
Create Date: 2026-06-19 18:00:00

迁移 _migrate_missing_columns 的职责至纯 Alembic——
将 villages.status 列添加为显式迁移。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "village_status_001"
down_revision = "rev_tier_bool_001"
branch_labels = None
depends_on = None


def upgrade():
    """Add status column to villages table（幂等：已存在或表已删除则跳过）."""
    insp = sa.inspect(op.get_bind())
    # W22（v1.14.0）：villages 遗留表已删除（w22_household_media_consumption_001 drop），
    # 空库初始化路径的 001 baseline create_all 不再创建该表。历史迁移必须幂等跳过，
    # 否则全新安装的 alembic upgrade head 会在本步失败（CI upgrade-rehearsal 实测）。
    if not insp.has_table("villages"):
        return
    cols = {c["name"] for c in insp.get_columns("villages")}
    if "status" not in cols:
        op.add_column(
            "villages",
            sa.Column(
                "status",
                sa.String(50),
                nullable=True,
                server_default=sa.text("'active'"),
                comment="状态: active/inactive/developing/completed",
            ),
        )
    # 为现有行设置默认值
    op.execute("UPDATE villages SET status = 'active' WHERE status IS NULL")


def downgrade():
    """Remove status column from villages table."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("villages"):
        return
    with op.batch_alter_table("villages") as batch_op:
        batch_op.drop_column("status")
