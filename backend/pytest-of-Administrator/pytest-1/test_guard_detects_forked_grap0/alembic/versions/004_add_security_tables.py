"""添加安全增强相关表

Revision ID: 004
Revises: 003
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def _create_table(name, *args, **kwargs):
    """幂等建表：表已存在则跳过（兼容 create_all 已建表场景）。"""
    import sqlalchemy as sa
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *args, **kwargs)


def _create_index(name, table, columns, **kwargs):
    """幂等建索引：表缺失、列不存在或索引已存在则跳过。"""
    import sqlalchemy as sa
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
    """添加安全增强相关表"""

    # 双因素认证表
    _create_table(
        'two_factor_auth',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('secret_key', sa.String(length=255), nullable=False),
        sa.Column('backup_codes', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    _create_index('idx_two_factor_auth_user_id', 'two_factor_auth', ['user_id'])

    # 审计变更记录表
    _create_table(
        'audit_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_log_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['audit_log_id'], ['audit_logs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_audit_changes_audit_log_id', 'audit_changes', ['audit_log_id'])
    _create_index('idx_audit_changes_field_name', 'audit_changes', ['field_name'])


def downgrade():
    """移除安全增强相关表"""

    op.drop_index('idx_audit_changes_field_name', table_name='audit_changes')
    op.drop_index('idx_audit_changes_audit_log_id', table_name='audit_changes')
    op.drop_table('audit_changes')

    op.drop_index('idx_two_factor_auth_user_id', table_name='two_factor_auth')
    op.drop_table('two_factor_auth')
