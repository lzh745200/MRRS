"""fix FK ondelete contradictions (W2-T5)

Revision ID: fk_ondelete_001
Revises: recycle_retention_001
Create Date: 2026-08-25 11:00:00

修复 SET NULL 与 nullable=False 的矛盾外键：
- policy_favorites.policy_id: SET NULL+NOT NULL → CASCADE（政策删除时收藏行级联清除）
- import_histories.user_id:   SET NULL+NOT NULL → SET NULL 且列改可空（导入历史留痕保留）
- approval_records.approver_id: 同上（审批留痕保留）

SQLite 不支持直接 ALTER COLUMN，使用 batch_alter_table 重建表。
幂等：先反射实际约束/可空性，已符合目标态则跳过。
"""
from alembic import op
import re
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fk_ondelete_001"
down_revision = "recycle_retention_001"
branch_labels = None
depends_on = None


def _column_nullable(table: str, column: str) -> bool | None:
    insp = sa.inspect(op.get_bind())
    for col in insp.get_columns(table):
        if col["name"] == column:
            return col["nullable"]
    return None


def _drop_orphan_batch_tmp(*tables: str) -> None:
    """清理前次中断遗留的 batch_alter_table 孤儿临时表（任务#6 风险3根因）。

    batch_alter_table 在 SQLite 下会先建 ``_alembic_tmp_<table>`` 影子表再做
    换名。若前次运行在本迁移后续步骤（如旧版 policy_favorites 正则缺陷）中断，
    影子表可能残留；下次 upgrade 重建同名影子表时立即抛
    ``table _alembic_tmp_<table> already exists``，使迁移永久卡死。此处在重建前
    主动清理残留影子表，令迁移可断点重跑（自愈、幂等）。
    """
    conn = op.get_bind()
    for t in tables:
        tmp = f"_alembic_tmp_{t}"
        found = conn.execute(
            sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": tmp},
        ).scalar()
        if found:
            conn.execute(sa.text(f'DROP TABLE "{tmp}"'))


def upgrade():
    # 0) 先清理前次中断遗留的孤儿影子表，避免 batch 重建时 "already exists" 卡死
    _drop_orphan_batch_tmp("import_histories", "approval_records")

    # 1) import_histories.user_id → 可空（历史留痕保留）
    if _column_nullable("import_histories", "user_id") is False:
        with op.batch_alter_table("import_histories") as batch:
            batch.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=True,
            )

    # 2) approval_records.approver_id → 可空（审批留痕保留）
    if _column_nullable("approval_records", "approver_id") is False:
        with op.batch_alter_table("approval_records") as batch:
            batch.alter_column(
                "approver_id",
                existing_type=sa.Integer(),
                nullable=True,
            )

    # 3) policy_favorites.policy_id: SET NULL → CASCADE（重建表外键）
    # 修复说明（2026-08-30）：SQLite 检查器不回传 ondelete（恒 None），原实现据此
    # 每次都误判 needs_cascade=True，且对匿名外键按合成名（fk_1）batch drop 必败
    # （"No such constraint"）——全新库迁移链在此中断。改为直读建表 DDL 判定，
    # 并用影子表舞步重建（匿名外键无法按名 drop）。
    # 修复说明（2026-09-02 任务#6）：原正则 ``( ON DELETE \w+)?`` 中 ``\w+`` 只匹配
    # 单个单词，遇到多词动作 ``SET NULL``/``NO ACTION``/``SET DEFAULT`` 时仅吞掉
    # ``SET``，遗留 `` NULL`` 导致重建 DDL 出现 ``ON DELETE CASCADE NULL`` 语法错误，
    # 使本迁移在既有 SET NULL 库上恒失败（并在步骤1遗留孤儿影子表）。改为枚举
    # SQLite 全部外键动作，正确整体替换。
    conn = op.get_bind()
    ddl = conn.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='policy_favorites'")
    ).scalar()
    if ddl and "REFERENCES policies (id) ON DELETE CASCADE" not in ddl:
        new_ddl, n = re.subn(
            r"FOREIGN KEY\(policy_id\) REFERENCES policies \(id\)"
            r"(?: ON DELETE (?:CASCADE|RESTRICT|SET NULL|SET DEFAULT|NO ACTION))?",
            "FOREIGN KEY(policy_id) REFERENCES policies (id) ON DELETE CASCADE",
            ddl,
            count=1,
        )
        if n != 1:
            raise RuntimeError("policy_favorites DDL 中未找到 policy_id 外键定义，请人工核查")
        new_ddl = new_ddl.replace(
            "CREATE TABLE policy_favorites", "CREATE TABLE policy_favorites_new_guard", 1
        )
        conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(sa.text(new_ddl))
            conn.execute(sa.text("INSERT INTO policy_favorites_new_guard SELECT * FROM policy_favorites"))
            conn.execute(sa.text("DROP TABLE policy_favorites"))
            conn.execute(sa.text("ALTER TABLE policy_favorites_new_guard RENAME TO policy_favorites"))
        finally:
            conn.execute(sa.text("PRAGMA foreign_keys=ON"))


def downgrade():
    """恢复原矛盾态（仅当无 NULL 值时可行；有 NULL 时保留现状避免破坏数据）"""
    bind = op.get_bind()
    has_null_user = bind.execute(
        sa.text("SELECT COUNT(*) FROM import_histories WHERE user_id IS NULL")
    ).scalar() or 0
    if has_null_user == 0 and _column_nullable("import_histories", "user_id") is True:
        with op.batch_alter_table("import_histories") as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
    has_null_approver = bind.execute(
        sa.text("SELECT COUNT(*) FROM approval_records WHERE approver_id IS NULL")
    ).scalar() or 0
    if has_null_approver == 0 and _column_nullable("approval_records", "approver_id") is True:
        with op.batch_alter_table("approval_records") as batch:
            batch.alter_column("approver_id", existing_type=sa.Integer(), nullable=False)
