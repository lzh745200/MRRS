"""add is_active, organization_id, created_by to policies

Revision ID: policy_audit_001
Revises: subordinate_ctrl_001
Create Date: 2026-07-29

政策法规模块增强：
- is_active: 软删除标记（默认True）
- organization_id: 所属组织ID（数据隔离）
- created_by: 创建人用户ID（审计追溯）
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "policy_audit_001"
down_revision = "subordinate_ctrl_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _column_exists("policies", "is_active"):
        op.add_column("policies", sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("1"), comment="是否活跃（软删除标记）",
        ))
    if not _column_exists("policies", "organization_id"):
        op.add_column("policies", sa.Column(
            "organization_id", sa.Integer(), nullable=True, comment="所属组织ID",
        ))
        op.create_index("ix_policies_organization_id", "policies", ["organization_id"])
    if not _column_exists("policies", "created_by"):
        op.add_column("policies", sa.Column(
            "created_by", sa.Integer(), nullable=True, comment="创建人用户ID",
        ))


def downgrade() -> None:
    op.drop_column("policies", "created_by")
    op.drop_index("ix_policies_organization_id", "policies")
    op.drop_column("policies", "organization_id")
    op.drop_column("policies", "is_active")


def _column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否已存在（幂等保护）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns
