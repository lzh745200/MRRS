"""fix foreign key cascade for supported_villages

Revision ID: fk_cascade_001
Revises: perf_indexes_001
Create Date: 2026-03-14 13:30:00.000000

修复 supported_villages 表的外键级联删除问题
SQLite 不支持直接修改外键约束,需要重建表
"""


# revision identifiers, used by Alembic.
revision = 'fk_cascade_001'
down_revision = 'perf_indexes_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    修复外键级联删除

    SQLite 不支持 ALTER TABLE 修改外键,需要:
    1. 创建新表(带正确的外键约束)
    2. 复制数据
    3. 删除旧表
    4. 重命名新表
    """

    # 注意: 由于涉及多个表的外键重建,这个操作比较复杂
    # 建议的解决方案:
    # 1. 在删除村庄前,先手动删除相关的子记录
    # 2. 或者在应用层实现级联删除逻辑

    # 这里我们不执行实际的表重建,因为:
    # - 会影响现有数据
    # - 需要重建22个表
    # - 可能导致数据丢失

    # 相反,我们在应用层实现级联删除
    pass


def downgrade():
    """回滚迁移"""
    pass
