"""performance: add facet indexes on support_unit / responsible_unit

Revision ID: perf_facet_indexes_001
Revises: account_package_attempts_001

背景（2026-11-21 审计 P1）：汇报大屏"帮扶单位"facet 从"整表 .all() 到 Python 计数"
改为 `GROUP BY ... COUNT(*)` 后，这两列需要索引支撑；否则省级数据仍是全表扫描。
"""

from alembic import op
import sqlalchemy as sa

revision = "perf_facet_indexes_001"
down_revision = "account_package_attempts_001"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_supported_villages_support_unit", "supported_villages", "support_unit"),
    ("ix_projects_responsible_unit", "projects", "responsible_unit"),
)


def _existing_indexes(inspector, table: str) -> set:
    try:
        return {idx["name"] for idx in inspector.get_indexes(table)}
    except Exception:  # 表不存在等场景交给调用方判断
        return set()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for name, table, column in _INDEXES:
        if table not in tables:
            continue
        if name in _existing_indexes(inspector, table):
            continue
        op.create_index(name, table, [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for name, table, _column in _INDEXES:
        if table not in tables:
            continue
        if name in _existing_indexes(inspector, table):
            op.drop_index(name, table_name=table)
