"""add pending to workstatus enum

Revision ID: workstatus_pending_001
Revises: 009
Create Date: 2026-03-14 14:00:00.000000

添加 'pending' 到 WorkStatus 枚举
"""


# revision identifiers, used by Alembic.
revision = 'workstatus_pending_001'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    """
    添加 'pending' 到 WorkStatus 枚举

    SQLite 不支持直接修改枚举类型,但由于我们使用的是字符串存储,
    只需要更新模型定义即可。数据库中已有的 'pending' 值会被正确识别。
    """
    # SQLite 使用字符串存储枚举,无需修改数据库
    # 只需要更新模型定义(已在 rural_work.py 中完成)
    pass


def downgrade():
    """回滚迁移"""
    # 如果需要回滚,需要将所有 'pending' 值改为其他状态
    # 但这可能导致数据丢失,不建议回滚
    pass
