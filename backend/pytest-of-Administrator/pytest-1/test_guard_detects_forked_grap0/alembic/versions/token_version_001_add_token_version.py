"""add_token_version_to_users

添加 token_version 字段，支持真正吊销用户所有 token

Revision ID: token_version_001
Revises: menu_permission_001
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'token_version_001'
down_revision = 'menu_permission_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'token_version' not in columns:
        op.add_column(
            'users',
            sa.Column(
                'token_version',
                sa.Integer(),
                default=0,
                nullable=False,
                server_default=sa.text('0'),
                comment='Token版本号，递增后旧token全部失效',
            )
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = [c['name'] for c in inspector.get_columns('users')]
    if 'token_version' in columns:
        op.drop_column('users', 'token_version')
