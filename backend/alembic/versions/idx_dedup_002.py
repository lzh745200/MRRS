"""idx_dedup_002: 删除按「列有序集合」判定的冗余索引

背景（2026-10-29 全库审计，Important）：

空库 `alembic upgrade head` 后实测到 11 组「同表 + 同列 + 同唯一性，多个索引名」，
另有 8 组「同列但一个普通索引 + 一个唯一索引」（普通索引被唯一索引完全覆盖）：

    audit_logs.created_at            x3  (ix_audit_timestamp / ix_audit_logs_created_at / idx_audit_created)
    audit_logs.(user_id, action)     x2
    consumption_records.supported_village_id x2
    household_members.household_id   x2
    household_risk_records.household_id x2
    households.supported_village_id  x2
    token_blacklist.expires_at       x2
    ...

重复索引不会错数据，但每次写入都要维护多份 B-tree（写放大），且让「schema 漂移」
难以发现（改了一个索引名，另一个还在，门禁看不出来）。

判据与历史迁移 `index_dedup_001` 的区别：那份按**索引名**清孤儿，漏掉了这类
**按语义重复**的；本迁移按「表 + 列有序集合 + 唯一性」分组判重。

保留规则：每组保留**模型 metadata 里声明的那一个**（`table.indexes` 的名字集合），
若不是其中任何一个则保留字典序第一个。`sqlite_autoindex_*`（表级 UNIQUE 约束自动
生成）**永不删除** —— 删了会丢唯一性。

Revision ID: idx_dedup_002
revises: pii_col_width_001
"""

from alembic import op
import sqlalchemy as sa

revision = "idx_dedup_002"
down_revision = "pii_col_width_001"
branch_labels = None
depends_on = None


# 保留清单：来自模型对索引的**显式声明**（权威口径，2026-10-29 核对）：
#   app/models/audit.py:56-58        Index("idx_audit_user_action", ...) / Index("idx_audit_created", ...)
#   app/models/household.py:50/160/240  Index("ix_households_village", ...) 等
#   app/models/consumption.py:40     Index("ix_consumption_records_village", ...)
#   app/models/token_blacklist.py:55 Index("idx_token_blacklist_expires", ...)
#
# 为什么不用 `Base.metadata` 动态取：`app.models` 是 `__getattr__` 惰性导出，
# `import app.models` 不会加载全部模型，metadata.tables 为空（实测）。
# 动态取会让迁移静默退回"字典序第一个"—— 本次恰好与模型一致，但不能靠运气。
KEEP_INDEX_NAMES = frozenset(
    {
        "idx_audit_created",
        "idx_audit_user_action",
        "ix_households_village",
        "ix_household_members_household",
        "ix_household_risk_records_household",
        "ix_consumption_records_village",
        "idx_token_blacklist_expires",
    }
)


def find_redundant(bind, keep_names=None):
    """返回应删除的冗余索引名列表（纯函数，便于单测）。

    Args:
        bind: SQLAlchemy Connection/Engine。
        keep_names: 额外视为"必须保留"的索引名集合（除了模块级 KEEP_INDEX_NAMES）。
    """
    insp = sa.inspect(bind)
    keep = set(KEEP_INDEX_NAMES) | set(keep_names or ())
    to_drop = []
    for table_name in sorted(insp.get_table_names()):
        if table_name.startswith("alembic"):
            continue
        indexes = insp.get_indexes(table_name)
        if not indexes:
            continue
        groups = {}
        for idx in indexes:
            name = idx.get("name") or ""
            # sqlite_autoindex_* 由表级 UNIQUE 约束生成，删不得
            if not name or name.startswith("sqlite_autoindex"):
                continue
            cols = tuple(idx.get("column_names") or ())
            if not cols:
                continue
            groups.setdefault((cols, bool(idx.get("unique"))), []).append(name)
        for _key, names in groups.items():
            if len(names) <= 1:
                continue
            # 优先保留"模型显式声明"的那个；都不在清单时保留字典序第一个
            kept = next((n for n in names if n in keep), sorted(names)[0])
            to_drop.extend(n for n in names if n != kept)
    return sorted(set(to_drop))


def upgrade() -> None:
    bind = op.get_bind()
    redundant = find_redundant(bind)
    insp = sa.inspect(bind)
    dropped = []
    for name in redundant:
        # 确认索引确实存在再删（幂等）
        found = False
        for table_name in insp.get_table_names():
            if any(i.get("name") == name for i in insp.get_indexes(table_name)):
                found = True
                break
        if not found:
            continue
        op.drop_index(name)
        dropped.append(name)
    print(f"idx_dedup_002: dropped {len(dropped)} redundant index(es): {dropped}")


def downgrade() -> None:
    """不回建 —— 被删的都是**同一个列组合上重复的那一个**，唯一性与查询能力由保留项承担。

    需要回滚时请直接 `alembic downgrade -1` 到上一版再重建索引；本函数保留空实现
    以维持迁移链可逆性检查。
    """
    pass
