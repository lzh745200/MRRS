"""捐赠物资台账建表

Revision ID: donation_item_001
Revises: pairing_001
Create Date: 2026-10-17

说明（两路径 schema 等价，勿改成非幂等）：

- 空库初始化路径：``001_baseline`` 会按当前模型 metadata ``create_all`` 全表，
  本迁移看到表已存在即跳过；
- 老库升级路径（升级排练 CI / 现场升级）：只有本迁移执行，需建出与模型
  metadata 完全一致的列与具名索引（模型 ``__table_args__`` 的 3 个 Index）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "donation_item_001"
down_revision = "pairing_001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    """幂等建表：表已存在（create_all 路径）则跳过。"""
    if _has_table("donation_items"):
        return

    op.create_table(
        "donation_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, comment="物资名称"),
        sa.Column(
            "category",
            sa.String(16),
            nullable=False,
            server_default="material",
            comment="类别: book=图书 / equipment=设备 / material=物资 / other=其他",
        ),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=True, comment="数量"),
        sa.Column("unit", sa.String(32), nullable=True, comment="计量单位（册/台/件/套）"),
        sa.Column("valuation", sa.Numeric(15, 4), nullable=True, comment="折价(万元)"),
        sa.Column("source_unit", sa.String(200), nullable=True, comment="来源单位（捐赠方）"),
        sa.Column(
            "destination_type",
            sa.String(16),
            nullable=False,
            comment="去向类型: village/school/project",
        ),
        sa.Column(
            "village_id",
            sa.Integer(),
            sa.ForeignKey("supported_villages.id", ondelete="SET NULL"),
            nullable=True,
            comment="去向帮扶村ID（去向为村时必填）",
        ),
        sa.Column(
            "school_id",
            sa.Integer(),
            sa.ForeignKey("schools.id", ondelete="SET NULL"),
            nullable=True,
            comment="去向帮扶学校ID（去向为学校时必填）",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
            comment="去向帮扶项目ID（去向为项目时必填）",
        ),
        sa.Column("delivery_date", sa.Date(), nullable=True, comment="交付日期"),
        sa.Column("receiver", sa.String(64), nullable=True, comment="签收人"),
        sa.Column("attachments", sa.JSON(), nullable=True, comment="凭证附件列表"),
        sa.Column("remark", sa.String(500), nullable=True, comment="备注"),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
            comment="所属组织ID",
        ),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者ID"),
        sa.Column(
            # 与模型 metadata 完全一致（无 server_default）：否则新建库与老库升级
            # 两路径 DDL 分叉，同库不同行为。pairing_001 同款约定。
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="是否有效（软删除标记）",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删时间"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
    )
    op.create_index(
        "ix_donation_items_destination",
        "donation_items",
        ["destination_type", "village_id", "school_id", "project_id"],
    )
    op.create_index("ix_donation_items_category", "donation_items", ["category"])
    op.create_index("ix_donation_items_org", "donation_items", ["organization_id"])


def downgrade():
    """回退：删索引后删表。"""
    insp = sa.inspect(op.get_bind())
    if insp.has_table("donation_items"):
        op.drop_index("ix_donation_items_destination", table_name="donation_items")
        op.drop_index("ix_donation_items_category", table_name="donation_items")
        op.drop_index("ix_donation_items_org", table_name="donation_items")
        op.drop_table("donation_items")
