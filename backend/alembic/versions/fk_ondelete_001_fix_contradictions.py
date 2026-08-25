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


def upgrade():
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
    insp = sa.inspect(op.get_bind())
    fks = {
        fk["name"] or f"fk_{i}": fk for i, fk in enumerate(
            insp.get_foreign_keys("policy_favorites")
        )
    }
    needs_cascade = any(
        fk["referred_table"] == "policies"
        and (fk.get("ondelete") or "").upper() != "CASCADE"
        for fk in fks.values()
    )
    if needs_cascade:
        with op.batch_alter_table("policy_favorites") as batch:
            for name, fk in fks.items():
                if fk["referred_table"] == "policies":
                    batch.drop_constraint(name, type_="foreignkey")
            batch.create_foreign_key(
                "uq_fk_policy_favorites_policy_cascade",
                "policies",
                ["policy_id"],
                ["id"],
                ondelete="CASCADE",
            )


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
