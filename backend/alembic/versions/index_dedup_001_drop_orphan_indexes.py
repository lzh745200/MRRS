"""P2-1 索引精简：删除历史孤儿索引（源码已无定义）

背景
----
`app/core/audit` 诊断发现数据库存在 456 个显式索引，而当前源码（ORM 模型
`__table_args__` + `Column(index=True)` + `EXTRA_INDEXES`）仅定义 413 个。
差额 49 个为**历史迁移遗留的孤儿索引**（多为 `idx_*` 旧命名，后续模型改用
`ix_*` 后未清理），既不被源码重建、也无任何代码/测试引用（已 grep 验证 0 引用）。

判定方式（权威）
----------------
以 SQLAlchemy 元数据（`Base.metadata.tables[*].indexes`，强制加载全部懒模型）
并集 `EXTRA_INDEXES` 作为「源码定义索引集合」；凡存活于 DB 但不在此集合、
且非 `sqlite_autoindex_*` 的显式索引即为孤儿。分析脚本：
`backend/scripts/gen_dedup_index_migration.py`。

安全性
------
- 每个 DROP 均使用 `IF EXISTS`，幂等；
- 仅删除「源码不再定义」的索引，等价索引（同表同列）在多数情况下仍由模型定义；
- 仅影响已有数据库的写放大与体积，不改变任何查询语义；
- downgrade 尽力重建（表不存在则跳过），便于回退。

Revision ID: index_dedup_001
Revises: data_report_type_001
"""
from alembic import op

revision = "index_dedup_001"
down_revision = "data_report_type_001"
branch_labels = None
depends_on = None


# (表名, 索引名, [列...])
_ORPHAN_INDEXES = [
    ("annual_income", "idx_annual_income_village_year", ["supported_village_id", "year"]),
    ("annual_industry", "idx_annual_industry_village_year", ["supported_village_id", "year"]),
    ("annual_infrastructure", "idx_annual_infrastructure_village_year", ["supported_village_id", "year"]),
    ("annual_population", "idx_annual_population_village_year", ["supported_village_id", "year"]),
    ("audit_changes", "idx_audit_changes_audit_log_id", ["audit_log_id"]),
    ("audit_changes", "idx_audit_changes_field_name", ["field_name"]),
    ("audit_logs", "idx_audit_logs_action", ["action"]),
    ("audit_logs", "idx_audit_logs_user_id", ["user_id"]),
    ("comments", "idx_comments_created_at", ["created_at"]),
    ("comments", "idx_comments_entity", ["entity_type", "entity_id"]),
    ("data_sync_logs", "ix_data_sync_logs_user_created", ["user_id", "created_at"]),
    ("data_sync_logs", "ix_data_sync_logs_user_id", ["user_id"]),
    ("effectiveness_evaluations", "idx_effectiveness_evaluations_village_id", ["village_id"]),
    ("effectiveness_evaluations", "idx_effectiveness_evaluations_year", ["year"]),
    ("funds", "idx_funds_allocation_date", ["allocation_date"]),
    ("funds", "idx_funds_org_date", ["organization_id", "allocation_date"]),
    ("funds", "idx_funds_project_id", ["project_id"]),
    ("funds", "idx_funds_project_type_date", ["project_id", "fund_type", "allocation_date"]),
    ("funds", "idx_funds_status", ["status"]),
    ("funds", "idx_funds_village_date_status", ["village_id", "allocation_date", "status"]),
    ("funds", "ix_funds_created_at", ["created_at"]),
    ("messages", "idx_messages_created_at", ["created_at"]),
    ("messages", "idx_messages_is_read", ["is_read"]),
    ("messages_extended", "idx_messages_extended_created_at", ["created_at"]),
    ("messages_extended", "idx_messages_extended_is_read", ["is_read"]),
    ("messages_extended", "idx_messages_extended_message_type", ["message_type"]),
    ("messages_extended", "idx_messages_extended_receiver_id", ["receiver_id"]),
    ("organizations", "idx_organizations_level_parent", ["level", "parent_id"]),
    ("organizations", "idx_organizations_parent_type", ["parent_id", "type"]),
    ("projects", "idx_projects_org_status", ["organization_id", "status"]),
    ("projects", "idx_projects_start_date", ["start_date"]),
    ("projects", "idx_projects_status", ["status"]),
    ("projects", "idx_projects_village_status_date", ["village_id", "status", "start_date"]),
    ("sentiment_news", "idx_sentiment_news_published_at", ["published_at"]),
    ("sentiment_reports", "idx_sentiment_reports_generated_at", ["generated_at"]),
    ("supported_villages", "idx_village_county_created", ["county", "created_at"]),
    ("supported_villages", "idx_village_department_created", ["department", "created_at"]),
    ("supported_villages", "ix_supported_villages_is_active", ["is_active"]),
    ("two_factor_auth", "idx_two_factor_auth_user_id", ["user_id"]),
    ("users", "idx_users_active_role", ["is_active", "role"]),
    ("users", "idx_users_email", ["email"]),
    ("users", "idx_users_is_active", ["is_active"]),
    ("users", "idx_users_org_role", ["organization_id", "role"]),
    ("users", "idx_users_username", ["username"]),
    ("villages", "idx_villages_name", ["name"]),
    ("villages", "idx_villages_province_city", ["province", "city"]),
    ("villages", "idx_villages_province_city_county", ["province", "city", "county"]),
    ("workflow_definitions", "idx_workflow_definitions_entity_type", ["entity_type"]),
    ("workflow_instances", "idx_workflow_instances_entity", ["entity_type", "entity_id"]),
]


def upgrade() -> None:
    """删除历史孤儿索引（幂等；仅影响源码不再定义的显式索引）。"""
    conn = op.get_bind()
    for _table, name, _cols in _ORPHAN_INDEXES:
        conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{name}"')


def downgrade() -> None:
    """尽力重建被删除的索引（表不存在时跳过，避免 downgrade 失败）。"""
    conn = op.get_bind()
    for table, name, cols in _ORPHAN_INDEXES:
        exists = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            continue
        col_list = ", ".join(cols)
        conn.exec_driver_sql(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({col_list})')
