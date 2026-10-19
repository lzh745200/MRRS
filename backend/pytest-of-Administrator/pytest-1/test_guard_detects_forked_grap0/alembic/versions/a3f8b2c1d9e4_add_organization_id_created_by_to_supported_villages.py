"""add_organization_id_created_by_to_supported_villages

Revision ID: a3f8b2c1d9e4
Revises: 79113cc0494a
Create Date: 2026-03-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8b2c1d9e4'
down_revision: Union[str, None] = '79113cc0494a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table, column):
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, 'supported_villages', 'organization_id'):
        op.execute("ALTER TABLE supported_villages ADD COLUMN organization_id INTEGER")
    if not _column_exists(conn, 'supported_villages', 'created_by'):
        op.execute("ALTER TABLE supported_villages ADD COLUMN created_by INTEGER")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_supported_villages_organization_id "
        "ON supported_villages (organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_supported_villages_created_by "
        "ON supported_villages (created_by)"
    )


def downgrade() -> None:
    with op.batch_alter_table('supported_villages', schema=None) as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')
