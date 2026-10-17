"""结对帮扶与走访台账建表

Revision ID: pairing_001
Revises: reminder_disp_001
Create Date: 2026-10-17

说明（两路径 schema 等价，勿改成非幂等）：

- 空库初始化路径：``001_baseline`` 会按当前模型 metadata ``create_all`` 全表，
  本迁移看到表已存在即跳过；
- 老库升级路径（升级排练 CI / 现场升级）：只有本迁移执行，需建出与模型
  metadata 完全一致的列与具名索引（模型 ``__table_args__`` 的 5 个 Index）。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "pairing_001"
down_revision = "reminder_disp_001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    """幂等建表：表已存在（create_all 路径）则跳过。"""
    if not _has_table("pairing_records"):
        op.create_table(
            "pairing_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "subject_type",
                sa.String(16),
                nullable=False,
                comment="帮扶主体类型: unit/branch/person",
            ),
            sa.Column(
                "subject_name",
                sa.String(128),
                nullable=False,
                comment="帮扶主体名称（单位名/支部名/干部姓名）",
            ),
            sa.Column(
                "subject_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
                comment="关联系统用户（帮扶干部本人，可空）",
            ),
            sa.Column(
                "partner_type",
                sa.String(16),
                nullable=False,
                comment="帮扶对象类型: village/school/student",
            ),
            sa.Column(
                "village_id",
                sa.Integer(),
                sa.ForeignKey("supported_villages.id", ondelete="SET NULL"),
                nullable=True,
                comment="帮扶村ID（对象为帮扶村时必填）",
            ),
            sa.Column(
                "school_id",
                sa.Integer(),
                sa.ForeignKey("schools.id", ondelete="SET NULL"),
                nullable=True,
                comment="帮扶学校ID（对象为帮扶学校时必填）",
            ),
            sa.Column("student_name", sa.String(64), nullable=True, comment="困难学生姓名（对象为学生时必填）"),
            sa.Column("title", sa.String(200), nullable=False, comment="帮扶事项"),
            sa.Column("content", sa.Text(), nullable=True, comment="帮扶内容与计划"),
            sa.Column("start_date", sa.Date(), nullable=True, comment="结对起始日期"),
            sa.Column("end_date", sa.Date(), nullable=True, comment="结对结束日期"),
            sa.Column(
                "status",
                sa.String(16),
                nullable=False,
                server_default="active",
                comment="状态: active=帮扶中 / ended=已结束",
            ),
            sa.Column("note", sa.String(500), nullable=True, comment="备注"),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                nullable=True,
                comment="所属组织ID",
            ),
            sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者ID"),
            sa.Column(
                # 与模型 metadata 完全一致：模型 is_active 只有 Python 侧 default=True，
                # 不做 server_default —— 否则"新建库(create_all)"与"老库升级(本迁移)"
                # 会产生不同的 DDL（同样适用于 donation_item_001）。
                "is_active",
                sa.Boolean(),
                nullable=False,
                comment="是否有效（软删除标记）",
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删时间"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        )
        op.create_index(
            "ix_pairing_records_partner",
            "pairing_records",
            ["partner_type", "village_id", "school_id"],
        )
        op.create_index(
            "ix_pairing_records_subject", "pairing_records", ["subject_type", "subject_name"]
        )
        op.create_index("ix_pairing_records_org", "pairing_records", ["organization_id"])

    if not _has_table("visit_records"):
        op.create_table(
            "visit_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "pairing_id",
                sa.Integer(),
                sa.ForeignKey("pairing_records.id", ondelete="CASCADE"),
                nullable=False,
                comment="结对记录ID",
            ),
            sa.Column("visit_date", sa.Date(), nullable=False, comment="走访日期"),
            sa.Column(
                "visitors",
                sa.String(200),
                nullable=False,
                comment="走访人员（多人逗号分隔）",
            ),
            sa.Column("purpose", sa.String(200), nullable=True, comment="走访事项"),
            sa.Column("content", sa.Text(), nullable=True, comment="走访内容与结果"),
            sa.Column("materials", sa.String(200), nullable=True, comment="慰问物资简记"),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                nullable=True,
                comment="所属组织ID",
            ),
            sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者ID"),
            sa.Column(
                # 与模型 metadata 完全一致：模型 is_active 只有 Python 侧 default=True，
                # 不做 server_default —— 否则"新建库(create_all)"与"老库升级(本迁移)"
                # 会产生不同的 DDL（同样适用于 donation_item_001）。
                "is_active",
                sa.Boolean(),
                nullable=False,
                comment="是否有效（软删除标记）",
            ),
            sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删时间"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        )
        op.create_index(
            "ix_visit_records_pairing_date", "visit_records", ["pairing_id", "visit_date"]
        )
        op.create_index("ix_visit_records_org", "visit_records", ["organization_id"])


def downgrade():
    """回退：先删走访表（FK 依赖），再删结对表。"""
    insp = sa.inspect(op.get_bind())
    if insp.has_table("visit_records"):
        op.drop_index("ix_visit_records_pairing_date", table_name="visit_records")
        op.drop_index("ix_visit_records_org", table_name="visit_records")
        op.drop_table("visit_records")
    if insp.has_table("pairing_records"):
        op.drop_index("ix_pairing_records_partner", table_name="pairing_records")
        op.drop_index("ix_pairing_records_subject", table_name="pairing_records")
        op.drop_index("ix_pairing_records_org", table_name="pairing_records")
        op.drop_table("pairing_records")
