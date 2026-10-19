"""添加机器码权限管理功能

Revision ID: 011
Revises: 010
Create Date: 2026-03-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    """添加机器码权限管理相关字段和表（幂等：已存在则跳过）"""
    insp = sa.inspect(op.get_bind())

    user_cols = {c["name"] for c in insp.get_columns("users")} if insp.has_table("users") else set()
    # 1. users 表添加新字段
    if "machine_binding_required" not in user_cols:
        op.add_column('users', sa.Column('machine_binding_required', sa.Boolean(), default=False, nullable=False, comment='是否强制机器码绑定'))
    if "allowed_permissions" not in user_cols:
        op.add_column('users', sa.Column('allowed_permissions', sa.Text(), default='', nullable=True, comment='白名单权限(JSON数组)'))

    mc_cols = {c["name"] for c in insp.get_columns("machine_codes")} if insp.has_table("machine_codes") else set()
    # 2. machine_codes 表添加新字段
    if "restrict_permissions" not in mc_cols:
        op.add_column('machine_codes', sa.Column('restrict_permissions', sa.Text(), default='', nullable=True, comment='此机器码限制的功能权限(JSON数组)'))

    # 3. 创建 machine_code_permissions 表
    if not insp.has_table("machine_code_permissions"):
        op.create_table(
            'machine_code_permissions',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('machine_code_id', sa.Integer(), nullable=False, comment='机器码ID'),
            sa.Column('permission', sa.String(length=100), nullable=False, comment='权限标识符'),
            sa.Column('granted_by', sa.Integer(), nullable=True, comment='授权人ID'),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
            sa.ForeignKeyConstraint(['machine_code_id'], ['machine_codes.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # 创建索引
    idx_names = {i["name"] for i in insp.get_indexes("machine_code_permissions")} if insp.has_table("machine_code_permissions") else set()
    if "ix_mcp_machine_permission" not in idx_names:
        op.create_index('ix_mcp_machine_permission', 'machine_code_permissions', ['machine_code_id', 'permission'], unique=True)


def downgrade():
    """删除机器码权限管理相关字段和表"""
    # 删除索引
    op.drop_index('ix_mcp_machine_permission', table_name='machine_code_permissions')

    # 删除表
    op.drop_table('machine_code_permissions')

    # 删除 machine_codes 表字段
    op.drop_column('machine_codes', 'restrict_permissions')

    # 删除 users 表字段
    op.drop_column('users', 'allowed_permissions')
    op.drop_column('users', 'machine_binding_required')
