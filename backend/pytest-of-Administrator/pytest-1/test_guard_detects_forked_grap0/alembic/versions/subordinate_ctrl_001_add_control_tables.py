"""add org_module_policies and subordinate_instances tables

Revision ID: subordinate_ctrl_001
Revises: 013_bootstrap_baseline
Create Date: 2026-07-29

下级单位管控系统 Phase1 数据表：
- org_module_policies: 组织级模块策略（可见性+编辑模式）
- subordinate_instances: 下级单位系统实例注册表
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "subordinate_ctrl_001"
down_revision = "013_bootstrap_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 组织级模块策略表
    if not _table_exists("org_module_policies"):
        op.create_table(
            "org_module_policies",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False, comment="目标下级组织ID"),
            sa.Column("module_key", sa.String(64), nullable=False, comment="模块标识"),
            sa.Column("visibility", sa.String(20), nullable=False, server_default="visible", comment="可见性"),
            sa.Column("edit_mode", sa.String(20), nullable=False, server_default="full_edit", comment="编辑模式"),
            sa.Column("created_by", sa.Integer(), nullable=True, comment="创建人用户ID"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sync_version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "module_key", name="uq_org_module"),
        )
        op.create_index("ix_org_module_policies_organization_id", "org_module_policies", ["organization_id"])
        op.create_index("ix_org_module_policies_module_key", "org_module_policies", ["module_key"])

    # 下级单位系统实例注册表
    if not _table_exists("subordinate_instances"):
        op.create_table(
            "subordinate_instances",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False, comment="所属组织ID"),
            sa.Column("instance_code", sa.String(64), nullable=False, comment="下级系统唯一标识"),
            sa.Column("machine_code", sa.String(255), nullable=True, comment="绑定的机器码"),
            sa.Column("system_version", sa.String(32), nullable=True, comment="最后已知系统版本"),
            sa.Column("license_status", sa.String(20), nullable=False, server_default="pending", comment="授权状态"),
            sa.Column("license_expiry", sa.Date(), nullable=True, comment="授权到期日"),
            sa.Column("last_config_hash", sa.String(64), nullable=True, comment="最后下发的管控配置包哈希"),
            sa.Column("last_config_applied_at", sa.DateTime(timezone=True), nullable=True, comment="下级最后应用配置时间"),
            sa.Column("last_report_at", sa.DateTime(timezone=True), nullable=True, comment="最后收到状态报告时间"),
            sa.Column("user_count", sa.Integer(), default=0, comment="下级系统注册用户数"),
            sa.Column("status", sa.String(20), nullable=False, server_default="unknown", comment="在线状态"),
            sa.Column("remark", sa.Text(), nullable=True, comment="备注"),
            sa.Column("created_by", sa.Integer(), nullable=True, comment="注册操作人用户ID"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sync_version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("instance_code", name="uq_subordinate_instance_code"),
        )
        op.create_index("ix_subordinate_instances_organization_id", "subordinate_instances", ["organization_id"])
        op.create_index("ix_subordinate_instances_instance_code", "subordinate_instances", ["instance_code"])


def downgrade() -> None:
    op.drop_table("subordinate_instances")
    op.drop_table("org_module_policies")


def _table_exists(table_name: str) -> bool:
    """检查表是否已存在（幂等保护）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()
