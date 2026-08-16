"""add_permission_packs

新增权限包表 permission_packs + users.permission_pack_id 绑定列

Revision ID: perm_pack_001
Revises: policy_audit_001
Create Date: 2026-08-16

权限包 = 菜单套餐：管理员定义一组可见菜单 key，批量绑定给普通用户(user/viewer)。
菜单解析优先级：用户级 allowed_menus > 绑定的启用中权限包 > 角色默认。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'perm_pack_001'
down_revision = 'policy_audit_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 permission_packs 表并给 users 加 permission_pack_id 列（幂等操作）"""
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()

    if 'permission_packs' not in tables:
        op.create_table(
            'permission_packs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=100), nullable=False, unique=True, comment='权限包名称'),
            sa.Column('description', sa.Text(), nullable=True, comment='权限包描述'),
            sa.Column('menu_keys', sa.Text(), nullable=True, comment='菜单key列表(JSON数组)'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1'), comment='是否启用'),
            sa.Column(
                'created_by',
                sa.Integer(),
                sa.ForeignKey('users.id', ondelete='SET NULL'),
                nullable=True,
                comment='创建人用户ID',
            ),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        )

    # users 加绑定列（SQLite ALTER ADD COLUMN 不带 FK 约束，FK 由 ORM 层维护）
    if 'users' in tables:
        columns = [c['name'] for c in inspect(op.get_bind()).get_columns('users')]
        if 'permission_pack_id' not in columns:
            op.add_column(
                'users',
                sa.Column(
                    'permission_pack_id',
                    sa.Integer(),
                    nullable=True,
                    comment='绑定的权限包ID，NULL表示未绑定',
                ),
            )


def downgrade() -> None:
    """删除 users.permission_pack_id 列与 permission_packs 表（幂等操作）"""
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()

    if 'users' in tables:
        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'permission_pack_id' in columns:
            # SQLite 旧版本不支持 DROP COLUMN，统一走 batch（重建表）模式
            with op.batch_alter_table('users') as batch_op:
                batch_op.drop_column('permission_pack_id')

    if 'permission_packs' in tables:
        op.drop_table('permission_packs')
