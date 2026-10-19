"""添加高级性能优化索引

Revision ID: 008
Revises: 007
Create Date: 2026-03-11

添加复合索引和覆盖索引以优化常见查询场景
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

def _create_index(name, table, columns, **kwargs):
    """幂等建索引：表缺失、列不存在（表结构已演进）或索引已存在则跳过。"""
    import sqlalchemy as sa
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return
    table_cols = {c["name"] for c in insp.get_columns(table)}
    if not all(c in table_cols for c in columns):
        return
    if name in {i["name"] for i in insp.get_indexes(table)}:
        return
    op.create_index(name, table, columns, **kwargs)




def upgrade():
    """添加高级性能优化索引"""

    # 组织表复合索引 - 优化组织树查询
    _create_index('idx_organizations_parent_type', 'organizations', ['parent_id', 'type'])
    _create_index('idx_organizations_level_parent', 'organizations', ['level', 'parent_id'])

    # 项目表复合索引 - 优化项目列表和统计查询
    _create_index('idx_projects_village_status_date', 'projects', ['village_id', 'status', 'start_date'])
    _create_index('idx_projects_org_status', 'projects', ['organization_id', 'status'])

    # 资金表复合索引 - 优化资金统计和审计查询
    _create_index('idx_funds_village_date_status', 'funds', ['village_id', 'allocation_date', 'status'])
    _create_index('idx_funds_project_type_date', 'funds', ['project_id', 'fund_type', 'allocation_date'])
    _create_index('idx_funds_org_date', 'funds', ['organization_id', 'allocation_date'])

    # 审计日志复合索引 - 优化审计查询和报表
    _create_index('idx_audit_logs_user_time', 'audit_logs', ['user_id', 'timestamp'])
    _create_index('idx_audit_logs_entity_action_time', 'audit_logs', ['entity_type', 'action', 'timestamp'])
    _create_index('idx_audit_logs_time_action', 'audit_logs', ['timestamp', 'action'])

    # 用户表复合索引 - 优化用户查询和权限检查
    _create_index('idx_users_org_role', 'users', ['organization_id', 'role'])
    _create_index('idx_users_active_role', 'users', ['is_active', 'role'])

    # 消息表复合索引 - 优化消息列表查询
    _create_index('idx_messages_receiver_read_time', 'messages', ['receiver_id', 'is_read', 'created_at'])
    _create_index('idx_messages_sender_time', 'messages', ['sender_id', 'created_at'])

    # 审批流复合索引 - 优化审批列表和统计
    _create_index('idx_approvals_approver_status_time', 'approvals', ['approver_id', 'status', 'created_at'])
    _create_index('idx_approvals_entity_status', 'approvals', ['entity_type', 'entity_id', 'status'])

    # 村庄表复合索引 - 优化地理位置和组织查询
    _create_index('idx_villages_province_city_county', 'villages', ['province', 'city', 'county'])
    _create_index('idx_villages_org_province', 'villages', ['army_unit_id', 'province'])

    # Token黑名单索引 - 优化token验证性能
    _create_index('idx_token_blacklist_token_expires', 'token_blacklist', ['token', 'expires_at'])

    # 用户会话索引 - 优化会话管理
    _create_index('idx_user_sessions_user_active', 'user_sessions', ['user_id', 'is_active'])
    _create_index('idx_user_sessions_expires', 'user_sessions', ['expires_at'])


def downgrade():
    """移除高级性能优化索引"""

    # 组织表索引
    op.drop_index('idx_organizations_parent_type', table_name='organizations')
    op.drop_index('idx_organizations_level_parent', table_name='organizations')

    # 项目表索引
    op.drop_index('idx_projects_village_status_date', table_name='projects')
    op.drop_index('idx_projects_org_status', table_name='projects')

    # 资金表索引
    op.drop_index('idx_funds_village_date_status', table_name='funds')
    op.drop_index('idx_funds_project_type_date', table_name='funds')
    op.drop_index('idx_funds_org_date', table_name='funds')

    # 审计日志索引
    op.drop_index('idx_audit_logs_user_time', table_name='audit_logs')
    op.drop_index('idx_audit_logs_entity_action_time', table_name='audit_logs')
    op.drop_index('idx_audit_logs_time_action', table_name='audit_logs')

    # 用户表索引
    op.drop_index('idx_users_org_role', table_name='users')
    op.drop_index('idx_users_active_role', table_name='users')

    # 消息表索引
    op.drop_index('idx_messages_receiver_read_time', table_name='messages')
    op.drop_index('idx_messages_sender_time', table_name='messages')

    # 审批流索引
    op.drop_index('idx_approvals_approver_status_time', table_name='approvals')
    op.drop_index('idx_approvals_entity_status', table_name='approvals')

    # 村庄表索引
    op.drop_index('idx_villages_province_city_county', table_name='villages')
    op.drop_index('idx_villages_org_province', table_name='villages')

    # Token黑名单索引
    op.drop_index('idx_token_blacklist_token_expires', table_name='token_blacklist')

    # 用户会话索引
    op.drop_index('idx_user_sessions_user_active', table_name='user_sessions')
    op.drop_index('idx_user_sessions_expires', table_name='user_sessions')
