"""account package exports + receipts

Revision ID: account_package_001
Revises: machine_recovery_001
"""
from alembic import op
import sqlalchemy as sa

revision = "account_package_001"
down_revision = "machine_recovery_001"
branch_labels = None
depends_on = None


def _has_table(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "account_package_exports"):
        op.create_table(
            "account_package_exports",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("package_id", sa.String(length=64), nullable=False),
            sa.Column("format_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("issuer_org_code", sa.String(length=32), nullable=False),
            sa.Column("issuer_user_id", sa.Integer(), nullable=True),
            sa.Column("target_org_code", sa.String(length=32), nullable=False),
            sa.Column("binding_mode", sa.String(length=16), nullable=False, server_default="machine"),
            sa.Column("target_machine_code", sa.String(length=64), nullable=True),
            sa.Column("kdf_iterations", sa.Integer(), nullable=False),
            sa.Column("payload_sha256", sa.String(length=64), nullable=False),
            sa.Column("key_id", sa.String(length=64), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoke_reason", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("package_id", name="uq_account_package_exports_package_id"),
        )
        op.create_index("ix_account_package_exports_id", "account_package_exports", ["id"])
        op.create_index("ix_account_package_exports_package_id", "account_package_exports", ["package_id"])
        op.create_index("ix_account_package_exports_issuer_org_code", "account_package_exports", ["issuer_org_code"])
        op.create_index("ix_account_package_exports_target_org_code", "account_package_exports", ["target_org_code"])
        op.create_index("ix_account_package_exports_state", "account_package_exports", ["state"])

    if not _has_table(inspector, "account_package_receipts"):
        op.create_table(
            "account_package_receipts",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("package_id", sa.String(length=64), nullable=False),
            sa.Column("machine_code", sa.String(length=64), nullable=True),
            sa.Column("issuer_org_code", sa.String(length=32), nullable=True),
            sa.Column("target_org_code", sa.String(length=32), nullable=True),
            sa.Column("activated_org_id", sa.Integer(), nullable=True),
            sa.Column("activated_user_id", sa.Integer(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="used"),
            sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("package_id", name="uq_account_package_receipts_package_id"),
        )
        op.create_index("ix_account_package_receipts_id", "account_package_receipts", ["id"])
        op.create_index("ix_account_package_receipts_package_id", "account_package_receipts", ["package_id"])
        op.create_index("ix_account_package_receipts_machine_code", "account_package_receipts", ["machine_code"])
        op.create_index("ix_account_package_receipts_target_org_code", "account_package_receipts", ["target_org_code"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "account_package_receipts"):
        op.drop_table("account_package_receipts")
    if _has_table(inspector, "account_package_exports"):
        op.drop_table("account_package_exports")
