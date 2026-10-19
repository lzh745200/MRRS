"""走访记录增加附件列（w17-002 收尾）

Revision ID: visit_attach_001
Revises: donation_item_001
Create Date: 2026-10-18

背景：002 的记录里写着"走访记录的照片附件字段（attachments JSON）已落库"，
但 ``VisitRecord`` 实际没有该列、也没有独立附件表 —— 属**记录与代码不一致**。
本次补齐列，并接线到通用 ``/files/upload``（前端上传后回填 ``{url, file_name}``）。

说明（两路径 schema 等价，勿改成非幂等）：

- 空库初始化路径：``001_baseline`` 按当前模型 metadata ``create_all`` 全表，
  本迁移看到列已存在即跳过；
- 老库升级路径（升级排练 CI / 现场升级）：只有本迁移执行，需补出与模型
  metadata 一致的 ``attachments`` JSON 列。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "visit_attach_001"
down_revision = "donation_item_001"
branch_labels = None
depends_on = None

_TABLE = "visit_records"
_COLUMN = "attachments"


def _has_column(table: str, column: str) -> bool:
    """表存在且已有该列 → True（供 create_all 路径跳过）。"""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade():
    """幂等加列：列已存在（create_all 路径）则跳过。"""
    if _has_column(_TABLE, _COLUMN):
        return
    with op.batch_alter_table(_TABLE) as batch:
        batch.add_column(
            sa.Column(
                _COLUMN,
                sa.JSON(),
                nullable=True,
                comment="走访照片/附件列表（[{url, file_name}]）",
            )
        )


def downgrade():
    """回退：删列（幂等）。"""
    if _has_column(_TABLE, _COLUMN):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COLUMN)
