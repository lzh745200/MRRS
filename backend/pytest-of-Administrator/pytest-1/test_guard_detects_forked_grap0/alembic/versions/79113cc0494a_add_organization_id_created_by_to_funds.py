"""add_organization_id_created_by_to_funds

Revision ID: 79113cc0494a
Revises: 010
Create Date: 2026-03-22 16:37:09.702328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79113cc0494a'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table, column):
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, 'funds', 'organization_id'):
        op.execute("ALTER TABLE funds ADD COLUMN organization_id INTEGER")
    if not _column_exists(conn, 'funds', 'created_by'):
        op.execute("ALTER TABLE funds ADD COLUMN created_by INTEGER")

    op.execute("CREATE INDEX IF NOT EXISTS ix_funds_organization_id ON funds (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_funds_created_by ON funds (created_by)")


def downgrade() -> None:
    with op.batch_alter_table('funds', schema=None) as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')
