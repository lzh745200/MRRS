"""add_organization_id_created_by_to_schools

Revision ID: b5c9d3e7f1a2
Revises: a3f8b2c1d9e4
Create Date: 2026-03-22 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c9d3e7f1a2'
down_revision: Union[str, None] = 'a3f8b2c1d9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table, column):
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, 'schools', 'organization_id'):
        op.execute("ALTER TABLE schools ADD COLUMN organization_id INTEGER")
    if not _column_exists(conn, 'schools', 'created_by'):
        op.execute("ALTER TABLE schools ADD COLUMN created_by INTEGER")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_schools_organization_id "
        "ON schools (organization_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_schools_created_by "
        "ON schools (created_by)"
    )


def downgrade() -> None:
    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('organization_id')
