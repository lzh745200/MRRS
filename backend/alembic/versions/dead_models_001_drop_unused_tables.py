"""drop unused feature tables (dead code cleanup)

清理 8 张「零引用 ORM 模型」对应的表。

**2026-10-29 全库审计修复（Important）**：原实现只判断「表存在」就 `op.drop_table`，
没有任何行数护栏 —— 违反 r35 契约（`r35_drop_legacy_tables_001` 定下的三分支：
表不存在→跳过；**0 行→DROP**；**有数据→改名 `legacy_<表名>` 归档**）。
本文件在开发库上验证过行数全为 0，但生产/其它机器的库不一定 —— 一旦有数据就会静默丢。
现改为与 r35 一致的三分支，并把逻辑抽成 `apply_dead_models_cleanup(bind)` 便于单测。

注：本迁移位于链中段（`fk_ondelete_001` 之后）。已升级的库因 alembic_version 已记录
而不会重跑；新库与未升级的旧库走新逻辑，只会更安全。

Revision ID: dead_models_001
Revises: fk_ondelete_001
Create Date: 2026-08-29
"""
import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger(__name__)

revision = "dead_models_001"
down_revision = "fk_ondelete_001"
branch_labels = None
depends_on = None

ARCHIVE_PREFIX = "legacy_"

# 删除顺序：先子表/独立表，最后主表（沿用原顺序）
TABLES = [
    "effectiveness_indicators",
    "version_history",
    "package_edit_logs",
    "user_sessions",
    "fee_standards",
    "inspection_rules",
    "data_versions",
    "army_units",
]


def _has_table(bind, name: str) -> bool:
    row = bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone()
    return row is not None


def _row_count(bind, name: str) -> int:
    return bind.execute(sa.text('SELECT COUNT(*) FROM "%s"' % name)).scalar() or 0  # nosec B608


def apply_dead_models_cleanup(bind):
    """三分支清理（r35 契约），返回 {dropped, archived, skipped}。

    - 表不存在 → skipped；
    - 0 行 → DROP；
    - 有数据 → 改名 `legacy_<表名>` 归档（归档表已存在时保留原表、人工确认）。

    抽成纯函数便于单测直接喂 sqlite 连接（三种分支都必须有用例覆盖）。
    """
    dropped, archived, skipped = [], [], []
    for name in TABLES:
        if not _has_table(bind, name):
            skipped.append(name)
            continue
        count = _row_count(bind, name)
        if count:
            archive = ARCHIVE_PREFIX + name
            if _has_table(bind, archive):
                logger.warning(
                    "dead_models_001: %s 有 %d 行但归档表 %s 已存在，保留原表（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "dead_models_001: %s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
                name, count, archive,
            )
        else:
            bind.execute(sa.text('DROP TABLE "%s"' % name))  # nosec B608
            dropped.append(name)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade() -> None:
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
    except Exception as exc:  # noqa: BLE001 - 关不掉 FK 不阻断（后续改名/删表仍可执行）
        logger.debug("dead_models_001: PRAGMA foreign_keys 设置失败: %s", exc)
    result = apply_dead_models_cleanup(bind)
    print(
        "dead_models_001: dropped=%s archived=%s skipped=%s"
        % (result["dropped"], result["archived"], result["skipped"])
    )


def downgrade() -> None:
    """不可逆：对应功能代码已整体移除，无模型可据以重建。

    drop_table 本身即破坏性操作；有数据的表已被改名为 `legacy_*` 归档（可人工恢复），
    故 downgrade 留空。升级前应确保已备份。
    """
    pass
