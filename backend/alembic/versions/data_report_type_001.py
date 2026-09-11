"""add report_type to data_reports

Revision ID: data_report_type_001
Revises: contract_attachments_001
Create Date: 2026-09-11

R29 修复：`DataReportCreate.report_type` 是**必填**字段、`DataReportResponse` 也回显，
但 `data_reports` 表与模型都没有该列、service 也从未使用 —— 调用方必须传一个
"传了也没用"的值，响应里恒为空串。加列并落库，让请求/响应字段真正生效。

幂等：列已存在则跳过（与仓库既有迁移风格一致；`main.py` 的
`migrate_missing_columns` 兜底也会补列）。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "data_report_type_001"
down_revision = "contract_attachments_001"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("data_reports"):
        return
    cols = {c["name"] for c in insp.get_columns("data_reports")}
    if "report_type" not in cols:
        op.add_column(
            "data_reports",
            sa.Column("report_type", sa.String(length=50), nullable=True, comment="上报类型"),
        )


def downgrade():
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("data_reports"):
        return
    cols = {c["name"] for c in insp.get_columns("data_reports")}
    if "report_type" in cols:
        with op.batch_alter_table("data_reports") as batch_op:
            batch_op.drop_column("report_type")
