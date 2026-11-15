"""machine recovery codes

Revision ID: machine_recovery_001
Revises: audit_chain_001
"""

from alembic import op
import sqlalchemy as sa

revision = "machine_recovery_001"
down_revision = "audit_chain_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_recovery_codes" not in inspector.get_table_names():
        op.create_table(
            "machine_recovery_codes",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("machine_code", sa.String(length=64), nullable=False),
            sa.Column("code_hash", sa.String(length=128), nullable=False),
            sa.Column("purpose", sa.String(length=20), nullable=False, server_default="password_reset"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_machine_recovery_codes_id", "machine_recovery_codes", ["id"])
        op.create_index("ix_machine_recovery_codes_machine_code", "machine_recovery_codes", ["machine_code"])
        op.create_index("ix_machine_recovery_codes_expires_at", "machine_recovery_codes", ["expires_at"])
        op.create_index(
            "ix_machine_recovery_lookup",
            "machine_recovery_codes",
            ["machine_code", "purpose", "used_at", "expires_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "machine_recovery_codes" in inspector.get_table_names():
        op.drop_table("machine_recovery_codes")
