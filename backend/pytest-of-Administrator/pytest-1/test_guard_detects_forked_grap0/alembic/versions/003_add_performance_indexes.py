"""添加性能优化索引

Revision ID: 003
Revises: 002
Create Date: 2026-03-10

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """添加性能优化索引（幂等：表或索引已存在则跳过）"""
    import sqlalchemy as sa

    indexes = [
        # 用户表索引
        ('idx_users_username', 'users', ['username']),
        ('idx_users_email', 'users', ['email']),
        ('idx_users_is_active', 'users', ['is_active']),
        # 村庄表索引
        ('idx_villages_name', 'villages', ['name']),
        ('idx_villages_province_city', 'villages', ['province', 'city']),
        ('idx_villages_army_unit_id', 'villages', ['army_unit_id']),
        # 项目表索引
        ('idx_projects_village_id', 'projects', ['supported_village_id']),
        ('idx_projects_status', 'projects', ['status']),
        ('idx_projects_start_date', 'projects', ['start_date']),
        ('idx_projects_village_status', 'projects', ['supported_village_id', 'status']),
        # 资金表索引
        ('idx_funds_project_id', 'funds', ['project_id']),
        ('idx_funds_village_id', 'funds', ['supported_village_id']),
        ('idx_funds_allocation_date', 'funds', ['allocation_date']),
        ('idx_funds_status', 'funds', ['status']),
        # 审计日志索引
        ('idx_audit_logs_user_id', 'audit_logs', ['user_id']),
        ('idx_audit_logs_action', 'audit_logs', ['action']),
        ('idx_audit_logs_timestamp', 'audit_logs', ['timestamp']),
        ('idx_audit_logs_entity_type_id', 'audit_logs', ['entity_type', 'entity_id']),
        # 审批流索引
        ('idx_approvals_entity_type_id', 'approvals', ['entity_type', 'entity_id']),
        ('idx_approvals_status', 'approvals', ['status']),
        ('idx_approvals_approver_id', 'approvals', ['approver_id']),
        # 消息表索引
        ('idx_messages_receiver_id', 'messages', ['receiver_id']),
        ('idx_messages_is_read', 'messages', ['is_read']),
        ('idx_messages_created_at', 'messages', ['created_at']),
        # 年度数据表索引
        ('idx_annual_population_village_year', 'annual_population', ['supported_village_id', 'year']),
        ('idx_annual_income_village_year', 'annual_income', ['supported_village_id', 'year']),
        ('idx_annual_industry_village_year', 'annual_industry', ['supported_village_id', 'year']),
        ('idx_annual_infrastructure_village_year', 'annual_infrastructure', ['supported_village_id', 'year']),
    ]

    insp = sa.inspect(op.get_bind())
    for name, table, columns in indexes:
        if not insp.has_table(table):
            continue
        # 表结构可能已演进：引用的列不存在则跳过（历史索引名）
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if not all(c in table_cols for c in columns):
            continue
        existing = {i["name"] for i in insp.get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns)


def downgrade():
    """移除性能优化索引"""

    # 用户表索引
    op.drop_index('idx_users_username', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_is_active', table_name='users')

    # 村庄表索引
    op.drop_index('idx_villages_name', table_name='villages')
    op.drop_index('idx_villages_province_city', table_name='villages')
    op.drop_index('idx_villages_army_unit_id', table_name='villages')

    # 项目表索引
    op.drop_index('idx_projects_village_id', table_name='projects')
    op.drop_index('idx_projects_status', table_name='projects')
    op.drop_index('idx_projects_start_date', table_name='projects')
    op.drop_index('idx_projects_village_status', table_name='projects')

    # 资金表索引
    op.drop_index('idx_funds_project_id', table_name='funds')
    op.drop_index('idx_funds_village_id', table_name='funds')
    op.drop_index('idx_funds_allocation_date', table_name='funds')
    op.drop_index('idx_funds_status', table_name='funds')

    # 审计日志索引
    op.drop_index('idx_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('idx_audit_logs_action', table_name='audit_logs')
    op.drop_index('idx_audit_logs_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_logs_entity_type_id', table_name='audit_logs')

    # 审批流索引
    op.drop_index('idx_approvals_entity_type_id', table_name='approvals')
    op.drop_index('idx_approvals_status', table_name='approvals')
    op.drop_index('idx_approvals_approver_id', table_name='approvals')

    op.drop_index('idx_messages_receiver_id', table_name='messages')
    op.drop_index('idx_messages_is_read', table_name='messages')
    op.drop_index('idx_messages_created_at', table_name='messages')

    # 年度数据表索引
    op.drop_index('idx_annual_population_village_year', table_name='annual_population')
    op.drop_index('idx_annual_income_village_year', table_name='annual_income')
    op.drop_index('idx_annual_industry_village_year', table_name='annual_industry')
    op.drop_index('idx_annual_infrastructure_village_year', table_name='annual_infrastructure')
