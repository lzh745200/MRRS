"""add fund management tables and fields

Revision ID: 002
Revises: 001
Create Date: 2026-02-25

说明：
    新增经费管理补充完善所需的4张新表和相关字段：
    - fee_standards: 费用标准表
    - fund_allocation_orders: 拨款指令表
    - allocation_order_items: 拨款指令明细表
    - inspection_rules: 督查规则表
    - fund_asset_verifications: 资产联动校验表

    注意：系统启动时 create_all + _migrate_missing_columns 已自动创建这些表/列，
    本迁移脚本主要用于版本化记录。upgrade/downgrade 均使用 batch 模式兼容 SQLite。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """检查表是否已存在（兼容 create_all 已建表场景）"""
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否已存在"""
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if not inspector.has_table(table_name):
        return False
    cols = {c["name"] for c in inspector.get_columns(table_name)}
    return column_name in cols


def upgrade() -> None:
    # ---- 1. fee_standards 费用标准表 ----
    if not _table_exists("fee_standards"):
        op.create_table(
            "fee_standards",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("upper_limit", sa.Numeric(15, 2), nullable=False),
            sa.Column("unit", sa.String(50), server_default="万元"),
            sa.Column("region", sa.String(100), nullable=True),
            sa.Column("industry", sa.String(100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("legal_basis", sa.String(500), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1"),
            sa.Column("is_active", sa.Boolean(), server_default="1"),
            sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_fstd_category", "fee_standards", ["category"])
        op.create_index("ix_fstd_region", "fee_standards", ["region"])
        op.create_index("ix_fstd_active", "fee_standards", ["is_active"])

    # ---- 2. fund_allocation_orders 拨款指令表 ----
    if not _table_exists("fund_allocation_orders"):
        op.create_table(
            "fund_allocation_orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id"), nullable=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("order_no", sa.String(100), unique=True, nullable=False),
            sa.Column("source_document", sa.String(200), nullable=True),
            sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("allocated_amount", sa.Numeric(15, 2), server_default="0"),
            sa.Column("target_organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("target_organization_name", sa.String(200), nullable=True),
            sa.Column("target_account", sa.String(200), nullable=True),
            sa.Column("issue_date", sa.Date(), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(20), server_default="draft"),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("received_by", sa.String(50), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_fao_fund_id", "fund_allocation_orders", ["fund_id"])
        op.create_index("ix_fao_project_id", "fund_allocation_orders", ["project_id"])
        op.create_index("ix_fao_status", "fund_allocation_orders", ["status"])
        op.create_index("ix_fao_order_no", "fund_allocation_orders", ["order_no"])

    # ---- 3. allocation_order_items 拨款指令明细表 ----
    if not _table_exists("allocation_order_items"):
        op.create_table(
            "allocation_order_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("fund_allocation_orders.id"), nullable=False),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("organization_name", sa.String(200), nullable=True),
            sa.Column("amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("account", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_aoi_order_id", "allocation_order_items", ["order_id"])
        op.create_index("ix_aoi_organization_id", "allocation_order_items", ["organization_id"])

    # ---- 4. inspection_rules 督查规则表 ----
    if not _table_exists("inspection_rules"):
        op.create_table(
            "inspection_rules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("rule_code", sa.String(50), unique=True, nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("threshold_value", sa.Numeric(15, 2), nullable=True),
            sa.Column("threshold_unit", sa.String(30), server_default="万元"),
            sa.Column("severity", sa.String(20), server_default="warning"),
            sa.Column("is_active", sa.Boolean(), server_default="1"),
            sa.Column("check_expression", sa.Text(), nullable=True),
            sa.Column("suggestion_template", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ir_rule_code", "inspection_rules", ["rule_code"])
        op.create_index("ix_ir_category", "inspection_rules", ["category"])
        op.create_index("ix_ir_active", "inspection_rules", ["is_active"])

    # ---- 5. fund_asset_verifications 资产联动校验表 ----
    if not _table_exists("fund_asset_verifications"):
        op.create_table(
            "fund_asset_verifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("fund_settlements.id"), nullable=True),
            sa.Column("total_paid", sa.Numeric(15, 2), server_default="0"),
            sa.Column("asset_value", sa.Numeric(15, 2), server_default="0"),
            sa.Column("difference", sa.Numeric(15, 2), server_default="0"),
            sa.Column("difference_rate", sa.Numeric(5, 2), server_default="0"),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("verified_by", sa.String(50), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("opinion", sa.Text(), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_fav_project_id", "fund_asset_verifications", ["project_id"])
        op.create_index("ix_fav_settlement_id", "fund_asset_verifications", ["settlement_id"])
        op.create_index("ix_fav_status", "fund_asset_verifications", ["status"])


def downgrade() -> None:
    # 按依赖顺序反向删除
    for tbl in [
        "fund_asset_verifications",
        "allocation_order_items",
        "fund_allocation_orders",
        "inspection_rules",
        "fee_standards",
    ]:
        if _table_exists(tbl):
            op.drop_table(tbl)
