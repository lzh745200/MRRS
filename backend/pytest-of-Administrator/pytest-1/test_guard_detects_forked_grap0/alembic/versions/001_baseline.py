"""baseline: 标记当前数据库 schema 为初始基线

Revision ID: 001
Revises: None
Create Date: 2026-02-14

说明：
    这是初始基线迁移。现有数据库表已通过 create_all + _migrate_missing_columns 创建。
    此脚本仅作为 Alembic 迁移历史的起点，不执行任何 DDL 操作。
    后续新的 schema 变更应通过 `alembic revision --autogenerate -m "描述"` 生成。
"""
from typing import Sequence, Union


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 空库引导：历史基线原为 pass，导致 alembic upgrade 无法从零建库。
    # 检测核心表缺失时直接从当前模型 metadata 建全部表（create_all 幂等，
    # 已初始化的库自动跳过）；后续迁移各自带存在性守卫，链可完整重放。
    from alembic import op
    import sqlalchemy as sa

    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "users" in tables and "supported_villages" in tables:
        return

    import importlib
    import pkgutil

    import app.models as _models_pkg
    from app.models.base import Base

    for _m in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"app.models.{_m.name}")

    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    # 基线迁移不支持降级
    pass
