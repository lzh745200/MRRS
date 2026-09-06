"""add last_sent_at to report_subscriptions

Revision ID: subscription_last_sent_001
Revises: org_guard_001
Create Date: 2026-09-06

工单 003（报表订阅闭环）：last_sent_at 记录该订阅最近一次成功生成/送达时间，
是 dispatch 判定「本周期已生成过、不重复生成」的依据。历史行为 NULL = 从未生成。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "subscription_last_sent_001"
down_revision = "org_guard_001"
branch_labels = None
depends_on = None


def upgrade():
    """Add last_sent_at column to report_subscriptions（幂等：已存在则跳过）."""
    insp = sa.inspect(op.get_bind())
    cols = (
        {c["name"] for c in insp.get_columns("report_subscriptions")}
        if insp.has_table("report_subscriptions")
        else set()
    )
    if "last_sent_at" not in cols:
        op.add_column(
            "report_subscriptions",
            sa.Column(
                "last_sent_at",
                sa.DateTime(),
                nullable=True,
                comment="最近一次成功生成/送达时间（NULL=从未生成）",
            ),
        )


def downgrade():
    """Remove last_sent_at column from report_subscriptions."""
    with op.batch_alter_table("report_subscriptions") as batch_op:
        batch_op.drop_column("last_sent_at")
