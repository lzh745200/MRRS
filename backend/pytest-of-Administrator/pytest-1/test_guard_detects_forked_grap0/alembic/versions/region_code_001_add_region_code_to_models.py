"""add region code to models

Revision ID: region_code_001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'region_code_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add region_code column to relevant tables"""
    # Check if column already exists before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Add region_code to projects table if not exists
    if 'projects' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('projects')]
        if 'region_code' not in columns:
            op.add_column('projects', sa.Column('region_code', sa.String(20), nullable=True))

    # Add region_code to supported_villages table if not exists
    if 'supported_villages' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('supported_villages')]
        if 'region_code' not in columns:
            op.add_column('supported_villages', sa.Column('region_code', sa.String(20), nullable=True))


def downgrade():
    """Remove region_code column from tables"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'projects' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('projects')]
        if 'region_code' in columns:
            op.drop_column('projects', 'region_code')

    if 'supported_villages' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('supported_villages')]
        if 'region_code' in columns:
            op.drop_column('supported_villages', 'region_code')
