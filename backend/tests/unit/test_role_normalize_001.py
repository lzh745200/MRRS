"""role_normalize_001 数据迁移自证：旧库里的历史角色/数据范围被清洗。"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "role_normalize_001.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("role_normalize_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _legacy_db():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, username VARCHAR(20), "
                "role VARCHAR(20), data_scope VARCHAR(20))"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO users (id, username, role, data_scope) VALUES "
                "(1, 'a', 'approval_leader', 'own'),"
                "(2, 'b', 'manager', 'all'),"
                "(3, 'c', 'operator', NULL),"
                "(4, 'd', NULL, 'own_dept'),"
                "(5, 'e', '', ''),"
                "(6, 'f', 'admin', 'self'),"
                "(7, 'g', 'mystery', 'own')"
            )
        )
    return engine


def test_upgrade_normalizes_legacy_roles_and_scopes():
    module = _load_migration_module()
    engine = _legacy_db()
    with engine.begin() as conn:
        module.apply_normalization(conn)
        rows = {
            username: (role, scope)
            for username, role, scope in conn.execute(
                sa.text("SELECT username, role, data_scope FROM users")
            ).fetchall()
        }
    assert rows["a"] == ("admin", "self")
    assert rows["b"] == ("admin", "all")
    assert rows["c"] == ("user", "org")
    assert rows["d"] == ("user", "own_dept")
    assert rows["e"] == ("user", "org")
    assert rows["f"] == ("admin", "self")
    # 未知角色不静默改写，保留原值供人工核查
    assert rows["g"] == ("mystery", "self")


def test_upgrade_is_idempotent_and_tolerates_missing_table():
    module = _load_migration_module()
    engine = _legacy_db()
    with engine.begin() as conn:
        module.apply_normalization(conn)
        module.apply_normalization(conn)
        count = conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one()
    assert count == 7

    empty = sa.create_engine("sqlite:///:memory:")
    with empty.begin() as conn:
        module.apply_normalization(conn)  # 表不存在：直接返回，不抛错


def test_downgrade_is_noop():
    module = _load_migration_module()
    assert module.downgrade() is None  # 角色归一化不可逆：降级不抛错也不改数据
