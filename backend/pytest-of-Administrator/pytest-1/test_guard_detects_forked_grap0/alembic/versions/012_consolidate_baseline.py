"""
基线合并迁移 (v1.2.0)

将所有 001-011 迁移和后续分支迁移合并为单一基线。
此迁移用于新数据库初始化，不适用于已有生产数据库升级。

此迁移文件汇总了以下变更：
- 001: 初始表创建 (users, villages, schools, projects, funds, organizations, policies, 等)
- 002: 经费管理表扩展
- 003: 性能索引
- 004: 安全相关表
- 005: 协同工作表
- 006: 效能评估与舆情表
- 007: 加密字段
- 008: 高级性能索引
- 009: 机器码管理
- 010: 分支合并头部
- 011: 机器码权限

注意：此文件仅作为文档参考。实际的 migrate 操作应使用
alembic upgrade head（包含所有独立迁移）。

生成时间: 2026-07-08
系统版本: 1.2.0
"""
# revision identifiers, used by Alembic.
revision = '012_consolidate_baseline'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    """基线合并：无需重复执行已有迁移，所有表结构已通过 001-011 创建"""
    pass


def downgrade():
    """回退到 011 之前的状态"""
    pass
