"""users: credential_expires_at for provisioning OTP

Revision ID: account_credential_expiry_001
Revises: account_package_001
"""
from alembic import op
import sqlalchemy as sa

revision = "account_credential_expiry_001"
down_revision = "account_package_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "credential_expires_at" not in cols:
        op.add_column("users", sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "credential_expires_at" in cols:
        op.drop_column("users", "credential_expires_at")
