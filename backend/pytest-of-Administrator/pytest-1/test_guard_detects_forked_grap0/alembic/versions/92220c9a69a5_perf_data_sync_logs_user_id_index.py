"""perf_data_sync_logs_user_id_index

Revision ID: 92220c9a69a5
Revises: merge_20260530
Create Date: 2026-06-06 22:26:33.386034

为 data_sync_logs.user_id 添加索引，优化用户维度的同步日志查询。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '92220c9a69a5'
down_revision: Union[str, None] = 'merge_20260530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 data_sync_logs.user_id 添加索引 — 加速按用户查询同步日志
    op.create_index(
        "ix_data_sync_logs_user_id",
        "data_sync_logs",
        ["user_id"],
        if_not_exists=True,
    )
    # 为 data_sync_logs 添加 (user_id, created_at) 复合索引 — 优化时间排序查询
    op.create_index(
        "ix_data_sync_logs_user_created",
        "data_sync_logs",
        ["user_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_data_sync_logs_user_created", table_name="data_sync_logs", if_exists=True)
    op.drop_index("ix_data_sync_logs_user_id", table_name="data_sync_logs", if_exists=True)
