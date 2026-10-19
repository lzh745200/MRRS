"""add code column to rbac_roles

Revision ID: rbac_code_001
Revises: ocr2_schema_001
Create Date: 2026-10-14 12:20:00

角色编码（code）此前只存在于前端：Role.vue 用「名称大写去空格」派生展示，
与后端无任何关系 —— 名称一改编码就漂移，也无法作为对外对接的稳定标识。
本迁移把 code 落到后端：加列 + 唯一索引 + 用现有名称回填（保证不出现 NULL 空洞）。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "rbac_code_001"
down_revision = "ocr2_schema_001"
branch_labels = None
depends_on = None


def upgrade():
    """Add code column to rbac_roles（幂等：已存在则跳过）."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("rbac_roles"):
        return
    cols = {c["name"] for c in insp.get_columns("rbac_roles")}
    if "code" not in cols:
        op.add_column(
            "rbac_roles",
            sa.Column("code", sa.String(50), nullable=True, comment="角色编码（唯一，可空）"),
        )
    # 用现有名称回填（大写、非字母数字转下划线），与前端此前的派生规则一致，
    # 避免升级后前端"编码"列由有值变空白。
    op.execute(
        "UPDATE rbac_roles "
        "SET code = UPPER(REPLACE(REPLACE(name, ' ', '_'), '-', '_')) "
        "WHERE code IS NULL OR code = ''"
    )
    # 唯一索引（可空列允许多行 NULL，SQLite 语义）
    idx = {i["name"] for i in insp.get_indexes("rbac_roles")}
    if "ix_rbac_roles_code" not in idx:
        op.create_index("ix_rbac_roles_code", "rbac_roles", ["code"], unique=True)


def downgrade():
    """Remove code column from rbac_roles table."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("rbac_roles"):
        return
    idx = {i["name"] for i in insp.get_indexes("rbac_roles")}
    if "ix_rbac_roles_code" in idx:
        op.drop_index("ix_rbac_roles_code", table_name="rbac_roles")
    with op.batch_alter_table("rbac_roles") as batch_op:
        batch_op.drop_column("code")
