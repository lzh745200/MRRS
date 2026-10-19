"""添加成效评估和舆情监控相关表

Revision ID: 006
Revises: 005
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
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
    """添加成效评估和舆情监控相关表"""

    # 评估指标表
    _create_table(
        'effectiveness_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('calculation_formula', sa.Text(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, default=1.0),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    _create_index('idx_effectiveness_indicators_category', 'effectiveness_indicators', ['category'])

    # 成效评估表
    _create_table(
        'effectiveness_evaluations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('village_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('indicators', sa.JSON(), nullable=False),
        sa.Column('economic_score', sa.Float(), nullable=False),
        sa.Column('social_score', sa.Float(), nullable=False),
        sa.Column('ecological_score', sa.Float(), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('grade', sa.String(length=10), nullable=True),
        sa.Column('report_path', sa.String(length=500), nullable=True),
        sa.Column('evaluated_by', sa.Integer(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['village_id'], ['villages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evaluated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_effectiveness_evaluations_village_id', 'effectiveness_evaluations', ['village_id'])
    _create_index('idx_effectiveness_evaluations_year', 'effectiveness_evaluations', ['year'])

    # 舆情关键词表
    _create_table(
        'sentiment_keywords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False, default=1.0),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('keyword')
    )

    # 舆情新闻表
    _create_table(
        'sentiment_news',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('author', sa.String(length=100), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(length=20), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('is_alert', sa.Boolean(), nullable=False, default=False),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_sentiment_news_published_at', 'sentiment_news', ['published_at'])

    # 舆情报告表
    _create_table(
        'sentiment_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('total_news', sa.Integer(), nullable=False),
        sa.Column('positive_count', sa.Integer(), nullable=False),
        sa.Column('negative_count', sa.Integer(), nullable=False),
        sa.Column('neutral_count', sa.Integer(), nullable=False),
        sa.Column('hot_keywords', sa.JSON(), nullable=True),
        sa.Column('alerts', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('generated_by', sa.Integer(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    _create_index('idx_sentiment_reports_generated_at', 'sentiment_reports', ['generated_at'])


def downgrade():
    """移除成效评估和舆情监控相关表"""

    op.drop_index('idx_sentiment_reports_generated_at', table_name='sentiment_reports')
    op.drop_table('sentiment_reports')

    op.drop_index('idx_sentiment_news_published_at', table_name='sentiment_news')
    op.drop_table('sentiment_news')

    op.drop_table('sentiment_keywords')

    op.drop_index('idx_effectiveness_evaluations_year', table_name='effectiveness_evaluations')
    op.drop_index('idx_effectiveness_evaluations_village_id', table_name='effectiveness_evaluations')
    op.drop_table('effectiveness_evaluations')

    op.drop_index('idx_effectiveness_indicators_category', table_name='effectiveness_indicators')
    op.drop_table('effectiveness_indicators')
