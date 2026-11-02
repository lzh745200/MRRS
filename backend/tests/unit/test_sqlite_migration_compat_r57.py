"""SQLite 旧版本迁移兼容助手（R57）。"""

from types import SimpleNamespace

import sqlite3

from app.utils import sqlite_migration as compat


class FakeBind:
    def __init__(self, dialect_name="sqlite"):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.executed = []

    def execute(self, stmt):
        self.executed.append(str(stmt))


class FakeBatch:
    def __init__(self):
        self.dropped = []
        self.renamed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def drop_column(self, column):
        self.dropped.append(column)

    def alter_column(self, column, new_column_name):
        self.renamed.append((column, new_column_name))


class FakeOp:
    def __init__(self):
        self.batch = FakeBatch()

    def batch_alter_table(self, table):
        self.table = table
        return self.batch


def test_drop_native_when_sqlite_supports(monkeypatch):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 0))
    bind = FakeBind()
    compat.drop_column(bind, "t", "c", FakeOp())
    assert 'ALTER TABLE "t" DROP COLUMN "c"' in bind.executed[0]


def test_drop_batch_when_sqlite_old(monkeypatch):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 34, 0))
    bind = FakeBind()
    op = FakeOp()
    compat.drop_column(bind, "t", "c", op)
    assert op.batch.dropped == ["c"]
    assert bind.executed == []


def test_drop_native_fallback_without_op(monkeypatch):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 34, 0))
    bind = FakeBind()
    compat.drop_column(bind, "t", "c", None)
    assert bind.executed


def test_rename_native_when_supported(monkeypatch):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 0))
    bind = FakeBind()
    compat.rename_column(bind, "t", "a", "b", FakeOp())
    assert 'RENAME COLUMN "a" TO "b"' in bind.executed[0]


def test_rename_batch_when_old(monkeypatch):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 20, 0))
    bind = FakeBind()
    op = FakeOp()
    compat.rename_column(bind, "t", "a", "b", op)
    assert op.batch.renamed == [("a", "b")]


def test_non_sqlite_uses_native():
    bind = FakeBind("postgresql")
    op = FakeOp()
    compat.drop_column(bind, "t", "c", op)
    compat.rename_column(bind, "t", "a", "b", op)
    assert len(bind.executed) == 2
    assert op.batch.dropped == []
