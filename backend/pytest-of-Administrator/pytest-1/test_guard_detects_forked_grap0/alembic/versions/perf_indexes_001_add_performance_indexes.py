"""添加性能优化索引

Revision ID: perf_indexes_001
Revises:
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'perf_indexes_001'
down_revision = '011'  # 连接到主链
branch_labels = None
depends_on = None

def _create_table(name, *args, **kwargs):
    """幂等建表：表已存在则跳过。"""
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *args, **kwargs)


def _create_index(name, table, columns, **kwargs):
    """幂等建索引：表缺失、列不存在或索引已存在则跳过。"""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return
    table_cols = {c["name"] for c in insp.get_columns(table)}
    if not all(c in table_cols for c in columns):
        return
    if name in {i["name"] for i in insp.get_indexes(table)}:
        return
    op.create_index(name, table, columns, **kwargs)




def upgrade():
    """添加性能优化索引"""

    # Projects表 - 添加复合索引
    _create_index(
        'ix_projects_status_created',
        'projects',
        ['status', 'created_at'],
        unique=False
    )
    _create_index(
        'ix_projects_village_status',
        'projects',
        ['village_id', 'status'],
        unique=False
    )
    _create_index(
        'ix_projects_org_status',
        'projects',
        ['organization_id', 'status'],
        unique=False
    )
    _create_index(
        'ix_projects_start_date',
        'projects',
        ['start_date'],
        unique=False
    )
    _create_index(
        'ix_projects_end_date',
        'projects',
        ['end_date'],
        unique=False
    )

    # Funds表 - 添加复合索引
    _create_index(
        'ix_funds_project_status',
        'funds',
        ['project_id', 'status'],
        unique=False
    )
    _create_index(
        'ix_funds_village_status',
        'funds',
        ['village_id', 'status'],
        unique=False
    )
    _create_index(
        'ix_funds_status_date',
        'funds',
        ['status', 'date'],
        unique=False
    )
    _create_index(
        'ix_funds_created_at',
        'funds',
        ['created_at'],
        unique=False
    )

    # Supported_villages表 - 添加复合索引
    _create_index(
        'idx_village_county_created',
        'supported_villages',
        ['county', 'created_at'],
        unique=False
    )
    _create_index(
        'idx_village_department_created',
        'supported_villages',
        ['department', 'created_at'],
        unique=False
    )


def downgrade():
    """移除性能优化索引"""

    # Projects表
    op.drop_index('ix_projects_end_date', table_name='projects')
    op.drop_index('ix_projects_start_date', table_name='projects')
    op.drop_index('ix_projects_org_status', table_name='projects')
    op.drop_index('ix_projects_village_status', table_name='projects')
    op.drop_index('ix_projects_status_created', table_name='projects')

    # Funds表
    op.drop_index('ix_funds_created_at', table_name='funds')
    op.drop_index('ix_funds_status_date', table_name='funds')
    op.drop_index('ix_funds_village_status', table_name='funds')
    op.drop_index('ix_funds_project_status', table_name='funds')

    # Supported_villages表
    op.drop_index('idx_village_department_created', table_name='supported_villages')
    op.drop_index('idx_village_county_created', table_name='supported_villages')
