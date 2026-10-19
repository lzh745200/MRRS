"""R34（v1.15.14）：修复 effectiveness_evaluations 外键 + 补齐升级库缺失索引

Revision ID: r34_effectiveness_fk_rebuild_001
Revises: r33_org_grants_001
Create Date: 2026-10-19

## 背景（R34 深度复检实测，真实旧库升级路径）

旧版本创建的 effectiveness_evaluations 表，village_id 外键指向 legacy 表 villages；
v1.14 迁移删除 villages 表时未重建该外键，SQLite 也不会清理其他表的 FK 定义。
结果在「从旧库升级」的数据库上：

- PRAGMA foreign_key_check 恒报 1 条违规（effectiveness_evaluations -> villages）；
- 写入 effectiveness_evaluations 直接 OperationalError: no such table: main.villages，
  成效评估功能 100% 不可用；
- 全新安装库（create_all 建表 + stamp 到 head，不执行迁移）结构正确，故 CI/新装全绿。

## 本迁移做什么

1. 孤儿评估数据保全：village_id 在 supported_villages 中不存在（旧 villages 表已删，
   无映射依据）的评估行搬入审计表 r34_orphan_effectiveness_evaluations 后从主表删除。
   列定义 nullable=False，不能置 NULL；采用「搬移」而非直接丢弃，保留可追溯性。
2. batch_alter_table 重建 effectiveness_evaluations（copy_from 显式表定义）：
   - 外键 village_id -> supported_villages.id（ON DELETE CASCADE）；
   - 保留 evaluated_by -> users.id（ON DELETE SET NULL）；
   - 保留 uq_effectiveness_village_year 唯一约束与三个模型索引，结构与全新库对齐。
3. 迁移内断言 PRAGMA foreign_key_check 为空，否则 raise（fail-loud，禁止带病上线）。
4. 保守补建「模型声明但升级库缺失」的索引：共 21 个候选中创建 19 个；
   tea_plantations / cactus_fruit_plots 的 2 个索引跳过 —— 这两张表在 W22 迁移中列名已
   改为 supported_village_id 且两个模型当前零业务引用（死模型，见 R34 报告）。
   建索引前逐项检查表/列/同名索引是否存在（幂等；全新库 stamp 到 head 不会执行迁移）。

## 本迁移明确不处理（R34 报告列为后续专项，避免高重建风险）

- 其余 9 个模型声明但升级库缺失的外键（households / household_members /
  household_risk_records / photo_archives / consumption_records 的 organization_id、
  users.permission_pack_id 等）：需逐表 batch 重建；
- 6 张零引用 legacy 表（comments / messages_extended / sentiment_keywords /
  sentiment_reports / workflow_definitions / workflow_instances）的清理；
- tea_plantations / cactus_fruit_plots 列名漂移（W22 改名后模型未同步，零业务引用）。

## downgrade

不可逆：父表 villages 已不存在，无法恢复指向它的外键；表重建无法无损回滚。
按 R34 决策显式 raise NotImplementedError（升级前必须先备份数据库）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r34_effectiveness_fk_rebuild_001"
down_revision = "r33_org_grants_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r34")

_TABLE = "effectiveness_evaluations"
_ORPHAN_TABLE = "r34_orphan_effectiveness_evaluations"
_LEGACY_PARENT = "villages"
_TARGET_PARENT = "supported_villages"

# 模型已声明、但「旧库升级」后缺失的索引（21 个候选中 19 个可建）。
# 每项：(表, 索引名, 列名列表)
_MISSING_INDEXES = [
    ("consumption_records", "ix_consumption_records_org", ["organization_id"]),
    ("consumption_records", "ix_consumption_records_village", ["supported_village_id"]),
    ("household_members", "ix_household_members_household", ["household_id"]),
    ("household_members", "ix_household_members_org", ["organization_id"]),
    ("household_risk_records", "ix_household_risk_records_status", ["status"]),
    ("household_risk_records", "ix_household_risk_records_org", ["organization_id"]),
    ("household_risk_records", "ix_household_risk_records_household", ["household_id"]),
    ("households", "ix_households_org", ["organization_id"]),
    ("households", "ix_households_village", ["supported_village_id"]),
    ("permission_packs", "ix_permission_packs_id", ["id"]),
    ("photo_archives", "ix_photo_archives_id", ["id"]),
    ("photo_archives", "ix_photo_archives_organization_id", ["organization_id"]),
    ("policies", "ix_policies_organization_id", ["organization_id"]),
    ("policy_favorites", "ix_policy_favorites_id", ["id"]),
    ("policy_favorites", "ix_policy_favorites_user_id", ["user_id"]),
    ("policy_favorites", "ix_policy_favorites_policy_id", ["policy_id"]),
    ("rural_tasks", "ix_rural_tasks_village", ["supported_village_id"]),
    ("rural_works", "ix_rural_works_supported_village_id", ["supported_village_id"]),
    ("rural_works", "ix_rural_works_organization_id", ["organization_id"]),
]

# 重建表后需要恢复的模型索引（重建会随旧表一起删除它们）
_REBUILD_INDEXES = [
    ("ix_effectiveness_evaluations_id", ["id"]),
    ("ix_effectiveness_evaluations_village_id", ["village_id"]),
    ("ix_effectiveness_evaluations_year", ["year"]),
]


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _column_names(bind, table: str) -> set:
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_exists(bind, name: str) -> bool:
    row = bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = :n"),
        {"n": name},
    ).first()
    return row is not None


def _fk_targets(bind) -> set:
    """当前 effectiveness_evaluations 的外键目标表集合。"""
    rows = bind.exec_driver_sql("PRAGMA foreign_key_list(%s)" % _TABLE).fetchall()
    return {row[2] for row in rows}


def _archive_and_delete_orphans(bind) -> int:
    """把 village_id 无对应 supported_villages 行的评估行搬入审计表并删除。

    返回搬移行数。孤儿行无法映射（旧 villages 表已删除且业务无映射依据），
    直接 DELETE 会丢失可追溯性，故整体搬移保留。
    """
    if not (_table_exists(bind, _TABLE) and _table_exists(bind, _TARGET_PARENT)):
        return 0
    orphan_filter = "village_id NOT IN (SELECT id FROM %s)" % _TARGET_PARENT
    count = bind.execute(
        sa.text("SELECT COUNT(*) FROM %s WHERE %s" % (_TABLE, orphan_filter))
    ).scalar() or 0
    if not count:
        return 0
    if not _table_exists(bind, _ORPHAN_TABLE):
        bind.execute(
            sa.text(
                "CREATE TABLE %s AS SELECT * FROM %s WHERE %s"
                % (_ORPHAN_TABLE, _TABLE, orphan_filter)
            )
        )
    else:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO %s SELECT * FROM %s WHERE %s"
                % (_ORPHAN_TABLE, _TABLE, orphan_filter)
            )
        )
    bind.execute(sa.text("DELETE FROM %s WHERE %s" % (_TABLE, orphan_filter)))
    logger.warning(
        "r34: %d 条成效评估因 village_id 指向已删除的 legacy villages 表而无法映射，",
        count,
    )
    logger.warning("r34: 已搬移至审计表 %s 并从主表删除", _ORPHAN_TABLE)
    return count


def _rebuilt_table() -> sa.Table:
    """重建目标表定义（与 app.models.effectiveness 一致）。

    显式静态定义而非导入模型：迁移必须对「当时」的 schema 负责，不能随未来
    模型演化改变语义。
    """
    metadata = sa.MetaData()
    return sa.Table(
        _TABLE,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "village_id",
            sa.Integer(),
            sa.ForeignKey("%s.id" % _TARGET_PARENT, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("indicators", sa.JSON(), nullable=False),
        sa.Column("economic_score", sa.Float(), nullable=False),
        sa.Column("social_score", sa.Float(), nullable=False),
        sa.Column("ecological_score", sa.Float(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=10), nullable=True),
        sa.Column("report_path", sa.String(length=500), nullable=True),
        sa.Column(
            "evaluated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("village_id", "year", name="uq_effectiveness_village_year"),
    )


def _rebuild_effectiveness_table(bind) -> bool:
    """重建表修正外键；已在正确状态则跳过。返回是否执行了重建。"""
    if not _table_exists(bind, _TABLE):
        return False
    targets = _fk_targets(bind)
    if _LEGACY_PARENT not in targets and _TARGET_PARENT in targets:
        return False
    if not _table_exists(bind, _TARGET_PARENT):
        # 理论上不可达（supported_villages 自 baseline 起就存在）；保守跳过避免破坏数据
        logger.warning("r34: supported_villages 不存在，跳过 effectiveness 表重建")
        return False

    rebuilt = _rebuilt_table()
    with op.batch_alter_table(_TABLE, copy_from=rebuilt, recreate="always"):
        # 结构完全由 copy_from 决定；旧 villages 外键随重建消失，数据由 batch 复制
        pass

    for index_name, columns in _REBUILD_INDEXES:
        if not _index_exists(bind, index_name):
            op.create_index(index_name, _TABLE, columns)
    return True


def _ensure_missing_indexes(bind) -> None:
    """保守补建模型声明但升级库缺失的索引（不存在才建，失败记录不中断）。"""
    inspector = sa.inspect(bind)
    for table, index_name, columns in _MISSING_INDEXES:
        if not _table_exists(bind, table):
            logger.info("r34: 跳过索引 %s（表 %s 不存在）", index_name, table)
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        missing_columns = [col for col in columns if col not in existing_columns]
        if missing_columns:
            logger.warning(
                "r34: 跳过索引 %s（表 %s 缺列 %s）", index_name, table, missing_columns
            )
            continue
        if _index_exists(bind, index_name):
            continue
        try:
            op.create_index(index_name, table, columns)
        except Exception as exc:  # noqa: BLE001 - 单条索引失败不阻断迁移，必须记录
            logger.error("r34: 创建索引 %s 失败（已记录，不阻断迁移）: %s", index_name, exc)
            raise RuntimeError(
                "r34 迁移创建索引 %s 失败（%s）；请排查后重试，禁止静默跳过" % (index_name, exc)
            ) from exc


def _assert_foreign_keys_clean(bind) -> None:
    """迁移后断言全库外键检查为空（fail-loud，防止带病上线）。"""
    violations = bind.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            "r34 迁移后 PRAGMA foreign_key_check 仍有 %d 条违规（前 5 条: %r）；"
            "数据库存在未修复的引用完整性问题，已中止迁移。"
            % (len(violations), violations[:5])
        )


def upgrade() -> None:
    bind = op.get_bind()
    orphan_count = _archive_and_delete_orphans(bind)
    rebuilt = _rebuild_effectiveness_table(bind)
    _ensure_missing_indexes(bind)
    _assert_foreign_keys_clean(bind)
    logger.info(
        "r34 迁移完成：孤儿评估搬移 %d 条，effectiveness 表重建=%s",
        orphan_count,
        rebuilt,
    )


def downgrade() -> None:
    raise NotImplementedError(
        "r34_effectiveness_fk_rebuild_001 不可逆：legacy 父表 villages 已不存在，"
        "无法恢复指向它的外键。如需回退请用升级前的数据库备份恢复（见 OFFLINE_UPGRADE 文档）。"
    )
