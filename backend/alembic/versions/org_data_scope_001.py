"""org_data_scope_001: organizations 增加 data_scope（R48 影子观测）

背景（2026-11-01 审计报告，阶段 3）：

R33 授权矩阵解决的是「菜单/写接口」，数据范围仍只有角色级 ``users.data_scope``
与 ``core/data_permission`` 的角色推断。要评估「组织级数据范围」是否值得落地，
先加一列可空配置 + 影子观测：默认 ``ORG_DATA_SCOPE_MODE=off``，本列不参与任何查询，
只有 shadow 模式下 ``get_data_scope`` 会记差异日志。

本迁移只做 ``ADD COLUMN nullable``，不重建表、不改历史行、不改任何默认值；
SQLite 与 PostgreSQL 均可用 batch 模式执行，重复执行安全。

Revision ID: org_data_scope_001
revises: fk_machine_codes_created_by_001
"""

from alembic import op
import sqlalchemy as sa

revision = "org_data_scope_001"
down_revision = "fk_machine_codes_created_by_001"
branch_labels = None
depends_on = None

TABLE = "organizations"
COLUMN = "data_scope"


def _has_column(bind) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(TABLE):
        return False
    return COLUMN in {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind):
        print("org_data_scope_001: skip（%s.%s 已存在）" % (TABLE, COLUMN))
        return
    if not sa.inspect(bind).has_table(TABLE):
        print("org_data_scope_001: skip（%s 不存在）" % TABLE)
        return
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column(COLUMN, sa.String(length=16), nullable=True))
    print("org_data_scope_001: %s.%s 已添加" % (TABLE, COLUMN))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind):
        return
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column(COLUMN)
