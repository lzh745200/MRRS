"""add attachment_urls to policies (multi-attachment support)

Revision ID: policy_attachments_001
Revises: contract_attachments_001
Create Date: 2026-09-07

政策法规模块缺陷修复：此前 Policy 只有单文件字段 ``file_path/file_type/file_size``，
前端多附件上传后保存只保留首个附件，其余 URL 被丢弃。

修复：新增 ``attachment_urls``（Text，存 JSON 数组字符串）承载全部附件 URL；
``file_path/file_type/file_size`` 继续保存首附件以兼容旧逻辑（预览/下载主文件）。

注：``main.py`` 启动时先跑 ``alembic upgrade head``，失败再回退到
``migrate_missing_columns`` 自动补列；两者对本次新增的可空列结果一致。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "policy_attachments_001"
down_revision = "contract_attachments_001"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否已存在（幂等保护）"""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table_name):
        return False
    return column_name in {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    """Add attachment_urls to policies (nullable Text, JSON array string)."""
    if not _column_exists("policies", "attachment_urls"):
        op.add_column(
            "policies",
            sa.Column(
                "attachment_urls",
                sa.Text(),
                nullable=True,
                comment="附件URL列表(JSON数组字符串)",
            ),
        )


def downgrade() -> None:
    """Remove attachment_urls from policies (multi-attachment list is dropped)."""
    if _column_exists("policies", "attachment_urls"):
        op.drop_column("policies", "attachment_urls")
