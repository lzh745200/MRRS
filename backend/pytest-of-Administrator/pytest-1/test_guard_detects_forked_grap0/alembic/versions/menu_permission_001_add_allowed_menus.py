"""add_allowed_menus_to_users

添加用户菜单权限配置字段 allowed_menus

Revision ID: menu_permission_001
Revises:
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'menu_permission_001'
down_revision = 'perf_indexes_001'  # 连接到迁移链
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 allowed_menus 字段到 users 表（幂等操作）"""
    # 检查列是否已存在
    inspector = inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'allowed_menus' not in columns:
        op.add_column(
            'users',
            sa.Column(
                'allowed_menus',
                sa.Text(),
                nullable=True,
                comment='用户可见菜单key列表(JSON数组)，NULL表示继承角色默认菜单，空数组[]表示无菜单',
            )
        )


def downgrade() -> None:
    """删除 allowed_menus 字段"""
    # 检查列是否存在
    inspector = inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'allowed_menus' in columns:
        op.drop_column('users', 'allowed_menus')
