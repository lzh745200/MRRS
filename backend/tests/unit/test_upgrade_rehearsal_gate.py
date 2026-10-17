# -*- coding: utf-8 -*-
"""升级排练脚本（`backend/scripts/upgrade_rehearsal.py`）的回归测试。

为什么给"一个 CI 脚本"写单测：这套排练逻辑在 2026-10-17 首次跑通前，
**连续两次**因为自身缺陷给出错误结论 ——

1. 行数基线在"播种之前"取值，导致每张表都被判成"升级后数据丢了"（假红）；
2. 非自增主键（字符串/UUID 主键，如 `file_blobs.sha256`、`rbac_*.id`）被
   当成"主键一律跳过"，9 张表插不进去 → 那些表的数据安全根本没被验到（假绿）。

一个会给出错误结论的门禁，比没有门禁更危险（真出问题时它说 OK）。所以这些
规则在此钉死：播种覆盖率、类型占位值、旧标签解析、退出码语义。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "upgrade_rehearsal.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("upgrade_rehearsal_under_test", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reh = _load_script()


def _table(*columns):
    from sqlalchemy import MetaData, Table

    return Table("probe", MetaData(), *columns)


# ==================== 占位值 ====================


class TestDummyValue:
    def test_scalar_types(self):
        from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, JSON, Numeric, String, Text

        assert reh.dummy_value(Column("c", Integer)) == 1
        assert reh.dummy_value(Column("c", Float)) == 1.0
        assert reh.dummy_value(Column("c", Numeric(10, 2))) == 1.0
        assert reh.dummy_value(Column("c", Boolean)) is True
        assert reh.dummy_value(Column("c", DateTime)).year == 2026
        assert reh.dummy_value(Column("c", Date)).isoformat() == "2026-01-01"
        assert reh.dummy_value(Column("c", JSON)) == {}
        assert reh.dummy_value(Column("c", String(32))) == "rehearsal"
        assert reh.dummy_value(Column("c", Text)) == "rehearsal"

    def test_unsupported_type_raises(self):
        from sqlalchemy import Column, LargeBinary

        with pytest.raises(TypeError):
            reh.dummy_value(Column("c", LargeBinary))


# ==================== 主键判定（第二次假绿的根因） ====================


class TestNeedsValue:
    def test_single_integer_pk_is_auto(self):
        from sqlalchemy import Column, Integer

        table = _table(Column("id", Integer, primary_key=True))
        assert reh._needs_value(table, table.c.id) is False

    def test_string_pk_needs_explicit_value(self):
        from sqlalchemy import Column, String

        table = _table(Column("sha256", String(64), primary_key=True))
        assert reh._needs_value(table, table.c.sha256) is True

    def test_composite_integer_pk_needs_explicit_value(self):
        from sqlalchemy import Column, Integer

        table = _table(Column("a", Integer, primary_key=True), Column("b", Integer, primary_key=True))
        assert reh._needs_value(table, table.c.a) is True

    def test_nullable_skipped(self):
        from sqlalchemy import Column, String

        table = _table(Column("id", String(32), primary_key=True), Column("note", String(32), nullable=True))
        assert reh._needs_value(table, table.c.note) is False

    def test_python_side_default_skipped(self):
        from sqlalchemy import Column, Integer, String

        table = _table(
            Column("id", Integer, primary_key=True),
            Column("status", String(16), nullable=False, default="active"),
        )
        assert reh._needs_value(table, table.c.status) is False

    def test_server_default_skipped(self):
        from sqlalchemy import Column, Integer, String

        table = _table(
            Column("id", Integer, primary_key=True),
            Column("created_at", String(32), nullable=False, server_default="now()"),
        )
        assert reh._needs_value(table, table.c.created_at) is False


# ==================== 基线标签解析 ====================


class TestResolveOldRef:
    def test_explicit_passthrough(self):
        assert reh.resolve_old_ref("v1.2.3") == "v1.2.3"

    def test_picks_latest_v_tag(self, monkeypatch):
        monkeypatch.setattr(reh, "run", lambda *a, **k: (0, "v1.12.17\nv1.12.9\nv1.12.16\n"))
        assert reh.resolve_old_ref(None) == "v1.12.17"

    def test_no_v_tag_raises(self, monkeypatch):
        monkeypatch.setattr(reh, "run", lambda *a, **k: (0, "nightly\nlatest\n"))
        with pytest.raises(RuntimeError):
            reh.resolve_old_ref(None)

    def test_git_failure_raises(self, monkeypatch):
        monkeypatch.setattr(reh, "run", lambda *a, **k: (128, "not a git repository"))
        with pytest.raises(RuntimeError):
            reh.resolve_old_ref(None)


# ==================== 播种 / 状态快照（真实 sqlite） ====================


class TestSeedingOnRealDb:
    def test_seeds_string_pk_and_auto_pk_tables(self, tmp_path):
        from sqlalchemy import create_engine, text

        engine = create_engine("sqlite:///" + (tmp_path / "probe.db").as_posix())
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alpha (sha256 TEXT NOT NULL PRIMARY KEY, note TEXT NOT NULL)"))
            conn.execute(text("CREATE TABLE beta (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"))
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('rev_old')"))
        try:
            seeded, skipped = reh.seed_all_tables(engine)
            assert skipped == {}
            assert {"alpha", "beta"} <= seeded
            assert "alembic_version" not in seeded  # 迁移版本表不播种
            state = reh.table_state(engine)
            assert state["counts"]["alpha"] == 1
            assert state["counts"]["beta"] == 1
            assert state["integrity"] == "ok"
            assert state["version"] == "rev_old"
        finally:
            engine.dispose()

    def test_unsupported_column_type_is_skipped_with_reason(self, tmp_path):
        from sqlalchemy import create_engine, text

        engine = create_engine("sqlite:///" + (tmp_path / "probe2.db").as_posix())
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE blob_holder (id INTEGER PRIMARY KEY AUTOINCREMENT, payload BLOB NOT NULL)"))
            conn.execute(text("CREATE TABLE ok_table (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"))
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        try:
            seeded, skipped = reh.seed_all_tables(engine)
            assert "blob_holder" in skipped
            assert "TypeError" in skipped["blob_holder"]
            assert "ok_table" in seeded  # 一张表失败不影响其它表
        finally:
            engine.dispose()


# ==================== 子进程封装 ====================


class TestRun:
    def test_timeout_returns_124(self):
        code, out = reh.run([sys.executable, "-c", "import time; time.sleep(5)"], Path.cwd(), timeout=1)
        assert code == 124
        assert "TIMEOUT" in out


# ==================== 退出码语义 ====================


class TestReportAndExit:
    def test_success_is_zero(self, capsys):
        assert reh.report_and_exit({"steps": []}, [], [], 0.0) == 0
        assert "OK" in capsys.readouterr().out

    def test_failure_is_one_and_prints_warnings(self, capsys):
        code = reh.report_and_exit({"steps": []}, ["data"], ["跳过播种 x（TypeError）"], 0.0)
        out = capsys.readouterr().out
        assert code == 1
        assert "排练失败" in out
        assert "跳过播种 x" in out
