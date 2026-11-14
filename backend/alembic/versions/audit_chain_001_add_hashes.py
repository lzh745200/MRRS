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
    """幂等加列/加索引。

    001_baseline 用 create_all() 按**当前模型**建库，空库升级到本迁移时两列
    可能已存在；直接 add_column 会在真实 / 临时库上报 duplicate column。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    if "prev_hash" not in columns:
        op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    if "payload_hash" not in columns:
        op.add_column("audit_logs", sa.Column("payload_hash", sa.String(length=64), nullable=True))
    indexes = {idx["name"] for idx in inspector.get_indexes("audit_logs")}
    if "ix_audit_logs_payload_hash" not in indexes:
        op.create_index("ix_audit_logs_payload_hash", "audit_logs", ["payload_hash"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("audit_logs")}
    if "ix_audit_logs_payload_hash" in indexes:
        op.drop_index("ix_audit_logs_payload_hash", table_name="audit_logs")
    columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    if "payload_hash" in columns:
        op.drop_column("audit_logs", "payload_hash")
    if "prev_hash" in columns:
        op.drop_column("audit_logs", "prev_hash")
