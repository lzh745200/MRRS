"""normalize historical users.role / users.data_scope values

Revision ID: role_normalize_001
Revises: perf_facet_indexes_001

背景（2026-11-28 RBAC 精简）：系统角色已固定为 super_admin / admin / user / viewer，
但历史库、备份恢复、外部导入仍可能留下 approval_leader / manager / operator，
以及旧口径 data_scope='own'。读路径虽然会在写入入口归一化，历史行不会自动改变，
导致同一账号在前端显示与后端 is_admin 判定之间出现分裂。本迁移只做数据清洗，
不改表结构；未知 role 不静默改写（保留原值，交由人工核查），避免把脏数据"洗成"
合法角色而扩大权限。
"""

from alembic import op
import sqlalchemy as sa

revision = "role_normalize_001"
down_revision = "perf_facet_indexes_001"
branch_labels = None
depends_on = None

_ROLE_MAP = {
    "approval_leader": "admin",
    "manager": "admin",
    "operator": "user",
}


def _table_exists(bind, table: str) -> bool:
    return table in set(sa.inspect(bind).get_table_names())


def _columns(bind, table: str) -> set:
    try:
        return {col["name"] for col in sa.inspect(bind).get_columns(table)}
    except Exception:  # pragma: no cover - 表不存在时由调用方先判断
        return set()


def upgrade() -> None:
    apply_normalization(op.get_bind())


def apply_normalization(bind) -> None:
    """纯数据清洗，可单测：不依赖 Alembic op，只依赖一个 Connection/Engine。"""
    if not _table_exists(bind, "users"):
        return
    cols = _columns(bind, "users")
    if "role" in cols:
        users = sa.table("users", sa.column("role", sa.String))
        for legacy, canonical in _ROLE_MAP.items():
            bind.execute(
                sa.update(users).where(users.c.role == legacy).values(role=canonical)
            )
        bind.execute(
            sa.update(users)
            .where(sa.or_(users.c.role.is_(None), users.c.role == ""))
            .values(role="user")
        )
    if "data_scope" in cols:
        users = sa.table("users", sa.column("data_scope", sa.String))
        bind.execute(
            sa.update(users)
            .where(users.c.data_scope == "own")
            .values(data_scope="self")
        )
        bind.execute(
            sa.update(users)
            .where(sa.or_(users.c.data_scope.is_(None), users.c.data_scope == ""))
            .values(data_scope="org")
        )


def downgrade() -> None:
    # 数据归一化不可逆：无法区分原始 approval_leader 与 manager，也无法判断
    # 一条 admin 是否由历史值迁移而来。回滚保持数据不变（幂等）。
    pass
