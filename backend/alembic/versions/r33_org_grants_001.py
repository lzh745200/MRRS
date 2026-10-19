"""R33（v1.15.x）：单位授权矩阵 org_grants 建表 + 单位/权限包扩展字段

Revision ID: r33_org_grants_001
Revises: w22_household_media_consumption_001
Create Date: 2026-10-19

背景（R33 需求）：
- 下级单位**没有超级管理员**且**完全离线**，无法逐用户配置权限；授权必须以
  **单位**为粒度由上级生成、经离线授权包下发，下级导入后只读执行。
- 原「权限包」只能表达"菜单可见/不可见"（`permission_packs.menu_keys`），
  原「组织模块策略」虽按单位但仅前端生效（后端无消费方）。本迁移引入
  `org_grants` 作为**唯一授权事实源**，后端据此裁决菜单与写接口。

迁移策略：**零迁移（只做 DDL，不写业务数据）**
- 存量单位不产生 `org_grants` 记录 → 解析时回落到既有路径
  （`users.allowed_menus` > 用户权限包 > 角色默认），行为与升级前完全一致。
- 不物化默认包：物化取并集会把管理员菜单下放给普通用户（扩权）。
- 验收口径：`super_admin/admin=102`、`user=54`、`viewer=52` 四个角色默认可见
  key 数迁移前后必须相等。

两路径兼容（与项目既有迁移同一模式）：
- 空库初始化：baseline 按当前 metadata ``create_all`` 已建表 → 本迁移检测到即跳过；
- 老库升级：逐项补齐表/列，全部幂等。
"""

import sqlalchemy as sa
from alembic import op

revision = "r33_org_grants_001"
down_revision = "w22_household_media_consumption_001"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def _add_column_if_absent(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def _create_org_grants() -> None:
    if _table_exists("org_grants"):
        return
    op.create_table(
        "org_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
            comment="目标单位ID（organizations.id）",
        ),
        sa.Column(
            "module_key",
            sa.String(length=64),
            nullable=False,
            comment="模块/菜单标识（与 MENU_DEFINITIONS 的 key 同源）",
        ),
        sa.Column(
            "level",
            sa.String(length=8),
            nullable=False,
            server_default="none",
            comment="授权级别: edit-可写, view-只读, none-不可见",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sync_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "module_key", name="uq_org_grant"),
    )
    op.create_index("ix_org_grants_id", "org_grants", ["id"])
    op.create_index("ix_org_grants_organization_id", "org_grants", ["organization_id"])
    op.create_index("ix_org_grants_module_key", "org_grants", ["module_key"])


def upgrade() -> None:
    _create_org_grants()

    # ── organizations：授权元信息（矩阵本体在 org_grants） ──
    _add_column_if_absent(
        "organizations",
        sa.Column(
            "grant_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="已应用的授权包版本号（0=未授权，解析时回落 legacy）",
        ),
    )
    _add_column_if_absent(
        "organizations",
        sa.Column(
            "grant_signature",
            sa.Text(),
            nullable=True,
            comment="授权包签名（Ed25519 十六进制；空=未经签名/本地生成）",
        ),
    )
    _add_column_if_absent(
        "organizations",
        sa.Column(
            "grant_applied_at",
            sa.DateTime(),
            nullable=True,
            comment="授权包应用时间",
        ),
    )
    _add_column_if_absent(
        "organizations",
        sa.Column(
            "grant_source",
            sa.String(length=16),
            nullable=True,
            comment="授权来源: import-离线包导入, local-本机配置, default-内置默认",
        ),
    )
    _add_column_if_absent(
        "organizations",
        sa.Column(
            "inherit_from_parent",
            sa.Boolean(),
            nullable=False,
            server_default="1",
            comment="是否继承上级单位授权（0=独立授权，不向上合并）",
        ),
    )

    # ── permission_packs：可见性 → 授权矩阵（menu_keys 保留用于兼容/回滚） ──
    _add_column_if_absent(
        "permission_packs",
        sa.Column(
            "grants",
            sa.Text(),
            nullable=True,
            comment="模块授权矩阵(JSON对象: module_key -> edit/view/none)；空则由 menu_keys 派生",
        ),
    )


def downgrade() -> None:
    # SQLite 3.35+ 原生支持 DROP COLUMN；项目基线已要求该版本，
    # 故直接用 ALTER 而不走 batch_alter_table（后者会重建表，且对本表的自引用
    # 外键 organizations.parent_id 有反射风险）。
    if _table_exists("org_grants"):
        for idx in ("ix_org_grants_module_key", "ix_org_grants_organization_id", "ix_org_grants_id"):
            op.execute("DROP INDEX IF EXISTS %s" % idx)
        op.drop_table("org_grants")

    for col in ("grant_version", "grant_signature", "grant_applied_at", "grant_source", "inherit_from_parent"):
        if _has_column("organizations", col):
            op.execute("ALTER TABLE organizations DROP COLUMN %s" % col)

    if _has_column("permission_packs", "grants"):
        op.execute("ALTER TABLE permission_packs DROP COLUMN grants")
