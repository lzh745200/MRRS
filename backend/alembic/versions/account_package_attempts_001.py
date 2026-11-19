"""account package attempts ledger (P4 rate limiting)

Revision ID: account_package_attempts_001
Revises: account_credential_expiry_001

新增 ``account_package_attempts`` 台账：以 ``subject_key`` 唯一记录账号包导出/导入的
失败尝试次数、锁定截止时间与最近失败时间，消费 ``ACCOUNT_PACKAGE_MAX_ATTEMPTS``。
自检可重入，旧库缺表时才创建。
"""
from alembic import op
import sqlalchemy as sa

revision = "account_package_attempts_001"
down_revision = "account_credential_expiry_001"
branch_labels = None
depends_on = None


def _has_table(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "account_package_attempts"):
        op.create_table(
            "account_package_attempts",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("subject_key", sa.String(length=160), nullable=False),
            sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.String(length=64), nullable=True),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("subject_key", name="uq_account_package_attempts_subject_key"),
        )
        op.create_index("ix_account_package_attempts_id", "account_package_attempts", ["id"])
        op.create_index(
            "ix_account_package_attempts_subject_key", "account_package_attempts", ["subject_key"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "account_package_attempts"):
        op.drop_table("account_package_attempts")
