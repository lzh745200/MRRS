"""R34 迁移回归测试：r34_effectiveness_fk_rebuild_001。

覆盖：
- 迁移链 revision 指向与 SingleHead 约束；
- 旧库结构（FK→legacy villages、含孤儿行）→ upgrade 后 FK 改指 supported_villages、
  孤儿行搬入审计表、数据保留、foreign_key_check 为空、写入/更新/唯一约束正常；
- 已是正确结构（全新库形态）→ upgrade 幂等跳过重建且不报错；
- 缺失索引的补建与「表不存在/列缺失」跳过分支；
- 其他表存在外键违规时迁移 fail-loud（raise）而不是带病上线；
- downgrade 显式 NotImplementedError（不可逆，父表已删）。
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION_PATH = _BACKEND / "alembic" / "versions" / "r34_effectiveness_fk_rebuild_001.py"
_REVISION = "r34_effectiveness_fk_rebuild_001"

_BASE_DDL = """
CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR(50));
CREATE TABLE supported_villages (id INTEGER NOT NULL PRIMARY KEY, village_name VARCHAR(100));
CREATE TABLE effectiveness_evaluations (
    id INTEGER NOT NULL,
    village_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    indicators JSON NOT NULL,
    economic_score FLOAT NOT NULL,
    social_score FLOAT NOT NULL,
    ecological_score FLOAT NOT NULL,
    total_score FLOAT NOT NULL,
    rank INTEGER,
    grade VARCHAR(10),
    report_path VARCHAR(500),
    evaluated_by INTEGER,
    evaluated_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(village_id) REFERENCES villages (id) ON DELETE CASCADE,
    FOREIGN KEY(evaluated_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_effectiveness_evaluations_id ON effectiveness_evaluations (id);
CREATE INDEX ix_effectiveness_evaluations_village_id ON effectiveness_evaluations (village_id);
CREATE INDEX ix_effectiveness_evaluations_year ON effectiveness_evaluations (year);
CREATE UNIQUE INDEX uq_effectiveness_village_year ON effectiveness_evaluations (village_id, year);
INSERT INTO users (id, username) VALUES (1, 'admin');
INSERT INTO supported_villages (id, village_name) VALUES (10, '村A');
INSERT INTO effectiveness_evaluations VALUES (
    1, 10, 2026, '{}', 1.5, 2.5, 3.5, 7.5, 1, 'A', NULL, 1,
    '2026-01-01', '2026-01-01', '2026-01-01'
);
INSERT INTO effectiveness_evaluations VALUES (
    2, 99, 2026, '{}', 1.0, 2.0, 3.0, 6.0, 2, 'B', NULL, 1,
    '2026-01-01', '2026-01-01', '2026-01-01'
);
"""


def _load_migration():
    spec = importlib.util.spec_from_file_location("r34_effectiveness_fk_rebuild", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_conn(extra_ddl: str = "", ddl: str = _BASE_DDL):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    conn = engine.connect()
    for statement in ddl.split(";"):
        sql = statement.strip()
        if sql:
            conn.exec_driver_sql(sql)
    if extra_ddl.strip():
        for statement in extra_ddl.split(";"):
            sql = statement.strip()
            if sql:
                conn.exec_driver_sql(sql)
    conn.commit()
    mod = _load_migration()
    mod.op = Operations(MigrationContext.configure(conn))
    return mod, conn


def _fk_targets(conn):
    return {row[2] for row in conn.exec_driver_sql(
        "PRAGMA foreign_key_list(effectiveness_evaluations)")}


def _index_names(conn, table="effectiveness_evaluations"):
    return {row[1] for row in conn.exec_driver_sql("PRAGMA index_list(%s)" % table)}


class TestRevisionChain:
    def test_revision_and_down_revision(self):
        mod = _load_migration()
        assert mod.revision == _REVISION
        assert mod.down_revision == "r33_org_grants_001"

    def test_single_head_is_this_migration(self):
        cfg = Config(str(_BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
        heads = list(ScriptDirectory.from_config(cfg).get_heads())
        assert heads == [_REVISION]


class TestUpgradeFixesLegacyForeignKey:
    def test_fk_rebuilt_orphans_archived_and_data_preserved(self):
        mod, conn = _make_conn()
        assert _fk_targets(conn) == {"villages", "users"}

        mod.upgrade()

        # 1) 外键改指 supported_villages，legacy villages 不再被引用
        targets = _fk_targets(conn)
        assert "supported_villages" in targets
        assert "villages" not in targets
        # 2) 全库外键检查为空（fail-loud 断言通过）
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        # 3) 合法行数据完整保留
        row = conn.exec_driver_sql(
            "SELECT id, village_id, year, total_score, grade FROM effectiveness_evaluations"
        ).fetchall()
        assert row == [(1, 10, 2026, 7.5, "A")]
        # 4) 孤儿行搬入审计表，主表删除
        orphan_rows = conn.exec_driver_sql(
            "SELECT id, village_id FROM r34_orphan_effectiveness_evaluations"
        ).fetchall()
        assert orphan_rows == [(2, 99)]
        # 5) 重建后模型索引齐全
        names = _index_names(conn)
        assert "ix_effectiveness_evaluations_id" in names
        assert "ix_effectiveness_evaluations_village_id" in names
        assert "ix_effectiveness_evaluations_year" in names
        # 6) 写入/更新恢复可用（旧库此前会 no such table: main.villages）
        conn.exec_driver_sql(
            "INSERT INTO effectiveness_evaluations (id, village_id, year, indicators,"
            " economic_score, social_score, ecological_score, total_score, evaluated_at,"
            " created_at, updated_at) VALUES (3, 10, 2027, '{}', 1, 1, 1, 3,"
            " '2027-01-01', '2027-01-01', '2027-01-01')"
        )
        conn.exec_driver_sql(
            "UPDATE effectiveness_evaluations SET total_score = 8.5 WHERE id = 1"
        )
        assert conn.exec_driver_sql(
            "SELECT total_score FROM effectiveness_evaluations WHERE id = 1"
        ).scalar() == 8.5
        # 7) 唯一约束（village_id, year）仍然生效
        with pytest.raises(sa.exc.IntegrityError):
            conn.exec_driver_sql(
                "INSERT INTO effectiveness_evaluations (id, village_id, year, indicators,"
                " economic_score, social_score, ecological_score, total_score, evaluated_at,"
                " created_at, updated_at) VALUES (4, 10, 2026, '{}', 1, 1, 1, 3,"
                " '2026-02-01', '2026-02-01', '2026-02-01')"
            )

    def test_upgrade_is_idempotent(self):
        mod, conn = _make_conn()
        mod.upgrade()
        mod.upgrade()  # 第二次不应重建/报错
        assert _fk_targets(conn) == {"supported_villages", "users"}
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        assert conn.exec_driver_sql(
            "SELECT COUNT(*) FROM effectiveness_evaluations"
        ).scalar() == 1

    def test_orphan_archive_append_branch(self):
        extra = (
            "CREATE TABLE r34_orphan_effectiveness_evaluations AS "
            "SELECT * FROM effectiveness_evaluations WHERE 0"
        )
        mod, conn = _make_conn(extra_ddl=extra)
        mod.upgrade()
        assert conn.exec_driver_sql(
            "SELECT COUNT(*) FROM r34_orphan_effectiveness_evaluations"
        ).scalar() == 1

    def test_downgrade_is_explicitly_irreversible(self):
        mod, conn = _make_conn()
        with pytest.raises(NotImplementedError):
            mod.downgrade()


class TestAlreadyMigratedDatabase:
    _NEW_DDL = """
CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY);
CREATE TABLE supported_villages (id INTEGER NOT NULL PRIMARY KEY);
CREATE TABLE effectiveness_evaluations (
    id INTEGER NOT NULL PRIMARY KEY,
    village_id INTEGER NOT NULL REFERENCES supported_villages (id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    indicators JSON NOT NULL,
    economic_score FLOAT NOT NULL,
    social_score FLOAT NOT NULL,
    ecological_score FLOAT NOT NULL,
    total_score FLOAT NOT NULL,
    rank INTEGER, grade VARCHAR(10), report_path VARCHAR(500),
    evaluated_by INTEGER REFERENCES users (id) ON DELETE SET NULL,
    evaluated_at DATETIME NOT NULL, created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE (village_id, year)
);
INSERT INTO supported_villages (id) VALUES (10);
INSERT INTO effectiveness_evaluations (id, village_id, year, indicators, economic_score,
  social_score, ecological_score, total_score, evaluated_at, created_at, updated_at)
  VALUES (1, 10, 2026, '{}', 1, 1, 1, 3, '2026-01-01', '2026-01-01', '2026-01-01');
"""

    def test_upgrade_skips_rebuild_when_fk_already_correct(self):
        mod, conn = _make_conn(ddl=self._NEW_DDL)
        mod.upgrade()
        assert "supported_villages" in _fk_targets(conn)
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        assert conn.exec_driver_sql(
            "SELECT COUNT(*) FROM effectiveness_evaluations"
        ).scalar() == 1

    def test_upgrade_without_effectiveness_table(self):
        ddl = "CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY);"
        mod, conn = _make_conn(ddl=ddl)
        mod.upgrade()  # 不应因缺表报错
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


class TestMissingIndexes:
    def test_creates_indexes_and_skips_missing_table_or_column(self):
        extra = """
CREATE TABLE households (
    id INTEGER NOT NULL PRIMARY KEY,
    organization_id INTEGER,
    supported_village_id INTEGER
);
CREATE TABLE policy_favorites (
    id INTEGER NOT NULL PRIMARY KEY,
    policy_id INTEGER
);
"""
        mod, conn = _make_conn(extra_ddl=extra)
        mod.upgrade()
        households_indexes = _index_names(conn, "households")
        assert "ix_households_org" in households_indexes
        assert "ix_households_village" in households_indexes
        # policy_favorites 缺 user_id 列 → 只建可建的 id 索引，缺列索引跳过且不报错
        favorites_indexes = _index_names(conn, "policy_favorites")
        assert "ix_policy_favorites_id" in favorites_indexes
        assert "ix_policy_favorites_user_id" not in favorites_indexes
        assert "ix_policy_favorites_policy_id" in favorites_indexes
        # 表不存在的索引全部跳过（minimal DB 中 photo_archives 等不存在）
        assert not _index_names(conn, "photo_archives")


class TestFailLoudForeignKeys:
    def test_upgrade_raises_when_other_fk_violation_remains(self):
        extra = (
            "CREATE TABLE ghost_parent (id INTEGER NOT NULL PRIMARY KEY);"
            "CREATE TABLE broken_child (id INTEGER NOT NULL PRIMARY KEY,"
            " parent_id INTEGER REFERENCES ghost_parent (id));"
            "INSERT INTO broken_child (id, parent_id) VALUES (1, 12345);"
        )
        mod, conn = _make_conn(extra_ddl=extra)
        # 注意：SQLite 在未开启 foreign_keys 时允许写入悬空引用，foreign_key_check 仍能查出
        with pytest.raises(RuntimeError) as exc_info:
            mod.upgrade()
        assert "foreign_key_check" in str(exc_info.value)
