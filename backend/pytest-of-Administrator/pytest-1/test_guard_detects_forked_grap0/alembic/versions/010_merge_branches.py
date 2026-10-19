"""合并迁移分支

Revision ID: 010
Revises: 009, workstatus_pending_001
Create Date: 2026-03-15 15:22:00.000000

"""


# revision identifiers, used by Alembic.
revision = '010'
down_revision = ('009', 'workstatus_pending_001')
branch_labels = None
depends_on = None


def upgrade():
    """合并分支，无需额外操作"""
    pass


def downgrade():
    """合并分支，无需额外操作"""
    pass
