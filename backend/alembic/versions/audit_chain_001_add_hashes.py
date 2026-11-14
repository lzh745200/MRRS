"""audit_logs: add optional hash-chain columns

Revision ID: audit_chain_001
Revises: org_data_scope_001
"""
from alembic import op
import sqlalchemy as sa

revision = "audit_chain_001"
down_revision = "org_data_scope_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("payload_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_audit_logs_payload_hash", "audit_logs", ["payload_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_payload_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "payload_hash")
    op.drop_column("audit_logs", "prev_hash")
