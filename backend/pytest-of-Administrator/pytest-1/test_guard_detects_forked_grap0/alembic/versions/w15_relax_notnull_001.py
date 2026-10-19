"""W15 深审：放宽审计/留痕外键列的可空性 + 补齐唯一约束

Revision ID: w15_relax_notnull_001
Revises: file_blob_001
Create Date: 2026-09-30 20:10:00

背景（2026-09-17 OpenCodeReview + 人工复核）：
- 多张审计/留痕表的 user_id（或等价引用列）声明为 `nullable=False`，而外键动作是
  `ON DELETE SET NULL` —— 删除被引用主体时数据库要写 NULL，必然 IntegrityError，
  删除用户/数据包/工作任务会整体失败。模型已放宽为可空，这里同步物理 schema。
- effectiveness_evaluations(village_id, year) 与 package_versions(package_id, version)
  缺唯一约束，并发/直写会产生重复行，排名与版本比对随之漂移。

幂等：列已可空则跳过；唯一索引已存在则跳过；检测到重复数据时**不**建唯一约束
（只告警），避免升级直接失败把既有安装卡死。

注意：模型里另有 4 处外键动作由 SET NULL 调成 CASCADE（notification_preferences、
allocation_order_items、fund_contract_payments 等）。可空性放宽后 SET NULL 已不再
报错，动作语义差异只影响新建库；为避免在既有安装上重建大表，本次不迁移外键动作。
"""
from alembic import op
import sqlalchemy as sa


revision = "w15_relax_notnull_001"
down_revision = "file_blob_001"
branch_labels = None
depends_on = None


def _column_nullable(table: str, column: str):
    """返回列的 nullable 属性；列不存在返回 None。"""
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return None
    for col in insp.get_columns(table):
        if col["name"] == column:
            return bool(col.get("nullable", True))
    return None


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return False
    return index_name in [i["name"] for i in insp.get_indexes(table)]


def _has_duplicates(table: str, columns) -> bool:
    cols = ", ".join(columns)
    row = op.get_bind().execute(
        sa.text(
            f"SELECT 1 FROM {table} GROUP BY {cols} HAVING COUNT(*) > 1 LIMIT 1"  # nosec B608
        )
    ).fetchone()
    return row is not None


# 需要放宽为可空的引用列（外键动作为 SET NULL）
_RELAX_COLUMNS = [
    ("approval_tasks", "submitter_id"),
    ("data_reports", "package_id"),
    ("data_export_logs", "user_id"),
    ("export_tasks", "user_id"),
    ("import_export_history", "user_id"),
    ("messages", "user_id"),
    ("rural_tasks", "rural_work_id"),
    ("work_logs", "user_id"),
]

# 需要补齐的唯一约束（表, 列, 索引名）
_UNIQUE_INDEXES = [
    ("effectiveness_evaluations", ["village_id", "year"], "uq_effectiveness_village_year"),
    ("package_versions", ["package_id", "version"], "uq_package_version_package_id_version"),
]


def upgrade():
    for table, column in _RELAX_COLUMNS:
        if _column_nullable(table, column) is False:
            with op.batch_alter_table(table) as batch_op:
                batch_op.alter_column(column, existing_type=sa.Integer(), nullable=True)

    for table, columns, index_name in _UNIQUE_INDEXES:
        if _has_index(table, index_name):
            continue
        if _has_duplicates(table, columns):
            print(f"[w15] {table}{tuple(columns)} 存在重复数据，跳过唯一约束（请先人工清理）")
            continue
        op.create_index(index_name, table, columns, unique=True)


def downgrade():
    for table, columns, index_name in reversed(_UNIQUE_INDEXES):
        if _has_index(table, index_name):
            op.drop_index(index_name, table_name=table)
