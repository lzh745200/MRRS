"""OCR 第二轮深审：审计外键可空性 / 差异率精度 / 舆情采集时间可空性

Revision ID: ocr2_schema_001
Revises: w15_relax_notnull_001
Create Date: 2026-09-30

背景（2026-09-30 第二轮逐条复核 part-B）：
- import_export_history.org_id 原为 NOT NULL + ON DELETE CASCADE：删除组织会连带
  清空导入导出审计留痕。模型已改 SET NULL + 可空（SQLite 既有安装不做整表重建，
  外键动作变更只影响新建库 —— 与 w15 迁移同样的取舍口径），可空性在此同步物理 schema。
- sentiment_news.collected_at 由迁移 006 建为 NOT NULL 且无 server_default，而模型与
  全仓写入点都不提供该值 → 迁移建的库插入必失败、create_all 建的库却可空，行为分裂。
  放宽为可空，ORM 侧已补默认值（models/sentiment.py）。
- fund_asset_verifications.difference_rate 原 Numeric(5,2)（上限 999.99），而差异率按
  |已付款-转固资产|/已付款*100 计算可达 1e6 量级 → 严格数值型库提交溢出报错。加宽到
  Numeric(12,2)。SQLite 不校验精度，跳过以免无谓整表重建。

幂等：列不存在或已是目标状态则跳过。
"""
from alembic import op
import sqlalchemy as sa


revision = "ocr2_schema_001"
down_revision = "w15_relax_notnull_001"
branch_labels = None
depends_on = None


def _column(table: str, column: str):
    """返回列的反射信息；表/列不存在返回 None。"""
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return None
    for col in insp.get_columns(table):
        if col["name"] == column:
            return col
    return None


def _relax_nullable(table: str, column: str) -> None:
    col = _column(table, column)
    if col is not None and col.get("nullable") is False:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(column, existing_type=sa.Integer(), nullable=True)


def upgrade():
    _relax_nullable("import_export_history", "org_id")

    col = _column("sentiment_news", "collected_at")
    if col is not None and col.get("nullable") is False:
        with op.batch_alter_table("sentiment_news") as batch_op:
            batch_op.alter_column(
                "collected_at", existing_type=sa.DateTime(), nullable=True
            )

    if op.get_bind().dialect.name == "sqlite":
        # SQLite 的 NUMERIC 无精度语义，加宽不产生任何行为差异
        return
    col = _column("fund_asset_verifications", "difference_rate")
    if col is None:
        return
    current = col.get("type")
    if isinstance(current, sa.Numeric) and (current.precision or 0) < 12:
        with op.batch_alter_table("fund_asset_verifications") as batch_op:
            batch_op.alter_column(
                "difference_rate",
                existing_type=sa.Numeric(5, 2),
                type_=sa.Numeric(12, 2),
                existing_nullable=True,
            )


def downgrade():
    if op.get_bind().dialect.name != "sqlite":
        col = _column("fund_asset_verifications", "difference_rate")
        if col is not None:
            current = col.get("type")
            if isinstance(current, sa.Numeric) and (current.precision or 0) >= 12:
                with op.batch_alter_table("fund_asset_verifications") as batch_op:
                    batch_op.alter_column(
                        "difference_rate",
                        existing_type=sa.Numeric(12, 2),
                        type_=sa.Numeric(5, 2),
                        existing_nullable=True,
                    )
    # 可空性放宽不回退：回退会把历史留痕/舆情行重新卡在 NOT NULL 上
