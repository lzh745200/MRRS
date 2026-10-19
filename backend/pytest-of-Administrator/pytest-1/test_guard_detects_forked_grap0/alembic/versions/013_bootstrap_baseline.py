"""consolidated bootstrap baseline + missing indexes

Revision ID: 013_bootstrap_baseline
Revises: fund_project_softdel_001
Create Date: 2026-07-18

解决两个结构性问题：
1. 空库无法引导——此前 001/012 基线迁移为 pass（空操作），
   `alembic upgrade head` 在全新数据库上无法建表。
   本迁移在检测到业务表缺失时，直接从当前模型 metadata 建全部表。
2. 模型已声明但存量库缺失的索引——应用启动的 create_all 不给
   已存在表补索引，导致 funds/projects 软删热字段等 8 个索引长期缺失。

全部操作幂等，可在任意历史库上重放。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013_bootstrap_baseline"
down_revision = "fund_project_softdel_001"
branch_labels = None
depends_on = None

# 模型声明但存量库可能缺失的索引（名称, 表, 列）
_MISSING_INDEXES = [
    ("ix_funds_is_active", "funds", ["is_active"]),
    ("ix_projects_is_active", "projects", ["is_active"]),
    ("ix_funds_year_month_status", "funds", ["year_month", "status"]),
    ("ix_funds_year_quarter_type", "funds", ["year_quarter", "fund_type"]),
    ("ix_funds_year_source", "funds", ["year", "fund_source"]),
    ("ix_audit_timestamp", "audit_logs", ["created_at"]),
    ("ix_audit_user_action", "audit_logs", ["user_id", "action"]),
    ("ix_organizations_created_by", "organizations", ["created_by"]),
]


def _bootstrap_if_empty() -> None:
    """空库（或缺核心表）时从当前模型 metadata 建全部表。"""
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    # 以核心业务表是否存在判断库是否已初始化
    if "users" in tables and "supported_villages" in tables:
        return

    import pkgutil
    import importlib
    import app.models as _models_pkg
    from app.models.base import Base

    # 确保全部模型子模块已导入（模型注册表完整）
    for _m in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"app.models.{_m.name}")

    Base.metadata.create_all(op.get_bind())


def _create_missing_indexes() -> None:
    insp = sa.inspect(op.get_bind())
    for name, table, columns in _MISSING_INDEXES:
        if not insp.has_table(table):
            continue
        existing = {i["name"] for i in insp.get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns)


def upgrade() -> None:
    _bootstrap_if_empty()
    _create_missing_indexes()


def downgrade() -> None:
    # 引导基线不回退（避免误删全库）；仅移除本迁移补的索引
    insp = sa.inspect(op.get_bind())
    for name, table, _columns in _MISSING_INDEXES:
        if insp.has_table(table):
            existing = {i["name"] for i in insp.get_indexes(table)}
            if name in existing:
                op.drop_index(name, table_name=table)
