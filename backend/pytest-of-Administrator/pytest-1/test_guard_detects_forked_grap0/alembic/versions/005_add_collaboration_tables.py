"""添加协作功能相关表

Revision ID: 005
Revises: 004
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def _create_table(name, *args, **kwargs):
    """幂等建表：表已存在则跳过（兼容 create_all 已建表场景）。"""
    import sqlalchemy as sa
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *args, **kwargs)


def _create_index(name, table, columns, **kwargs):
    """幂等建索引：表缺失、列不存在或索引已存在则跳过。"""
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
    """添加协作功能相关表"""

    # 扩展消息表
    _create_table(
        'messages_extended',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=True),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False, default='normal'),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('related_entity_type', sa.String(length=50), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_messages_extended_receiver_id', 'messages_extended', ['receiver_id'])
    _create_index('idx_messages_extended_message_type', 'messages_extended', ['message_type'])
    _create_index('idx_messages_extended_is_read', 'messages_extended', ['is_read'])
    _create_index('idx_messages_extended_created_at', 'messages_extended', ['created_at'])

    # 消息模板表
    _create_table(
        'message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('title_template', sa.String(length=255), nullable=False),
        sa.Column('content_template', sa.Text(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 评论表
    _create_table(
        'comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('mentions', sa.JSON(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_comments_entity', 'comments', ['entity_type', 'entity_id'])
    _create_index('idx_comments_created_at', 'comments', ['created_at'])

    # 工作流定义表
    _create_table(
        'workflow_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_workflow_definitions_entity_type', 'workflow_definitions', ['entity_type'])

    # 工作流实例表
    _create_table(
        'workflow_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('current_node', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='running'),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('started_by', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['started_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_workflow_instances_entity', 'workflow_instances', ['entity_type', 'entity_id'])


def downgrade():
    """移除协作功能相关表"""

    op.drop_index('idx_workflow_instances_entity', table_name='workflow_instances')
    op.drop_table('workflow_instances')

    op.drop_index('idx_workflow_definitions_entity_type', table_name='workflow_definitions')
    op.drop_table('workflow_definitions')

    op.drop_index('idx_comments_created_at', table_name='comments')
    op.drop_index('idx_comments_entity', table_name='comments')
    op.drop_table('comments')

    op.drop_table('message_templates')

    op.drop_index('idx_messages_extended_created_at', table_name='messages_extended')
    op.drop_index('idx_messages_extended_is_read', table_name='messages_extended')
    op.drop_index('idx_messages_extended_message_type', table_name='messages_extended')
    op.drop_index('idx_messages_extended_receiver_id', table_name='messages_extended')
    op.drop_table('messages_extended')
