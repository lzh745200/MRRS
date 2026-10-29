"""baseline: 标记当前数据库 schema 为初始基线

⚠️ 本迁移会**掩盖后续迁移的验证**（2026-10-29 全库审计 C1，已按"要求迁移自带旧库证据"收口）。

本文件在核心表缺失时调用 Base.metadata.create_all()，于是**新库在第一个迁移就落成
"今天的模型"**，后面 60+ 个迁移靠存在性守卫几乎全部跳过 —— 迁移脚本本身从不在新库上被执行，
check_stack_alignment 的 B 轴（模型 ↔ 空库 upgrade head）也因此恒 0 漂移，属**自证**。

含义：**"空库 upgrade head 成功"不能证明任何一条迁移是对的**。
真实反例：v1.18.26 前 PII 列在库里是 VARCHAR(20)、模型已是 EncryptedText(256)，
而 B 轴只比列存在性、参照库又由 create_all 生成，完全看不出来（密文实测最长 115 字符）。

自本版起的约定：**任何会改 schema 形状的迁移（alter/add/drop column、create/drop index、
create/drop table）必须自带一个能手工构造「旧库状态」的测试**，例如
tests/unit/test_pii_col_width_001.py（手工建 VARCHAR(20) 再驱动迁移函数，断言改到 256）。
门禁：scripts/check_migration_self_evidence.py（CI static-analysis 的 C1 步骤）；
历史无证据的迁移登记在 backend/scripts/gate_baselines/migration_evidence.json，不追溯。

彻底根治（未做，另立项）：把 create_all 换成**静态 DDL 快照**，让迁移链在新库上真正回放。

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
