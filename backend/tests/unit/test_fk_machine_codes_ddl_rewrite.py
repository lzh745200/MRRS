# -*- coding: utf-8 -*-
"""补一条回归：整表 DDL 里别的外键带 ON DELETE 时，created_by 仍必须被改写。"""
import importlib.util
from pathlib import Path

_MIG = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "fk_machine_codes_created_by_001.py"
)
_spec = importlib.util.spec_from_file_location("fk_machine_codes_created_by_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)

# 真实开发库的 DDL 片段：user_id 已带 ON DELETE SET NULL，created_by 没有
REAL_DDL = """CREATE TABLE machine_codes (
	id INTEGER NOT NULL,
	created_by INTEGER,
	user_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by) REFERENCES users (id)
)"""


def test_rewrites_created_by_even_when_other_fk_has_on_delete():
    """2026-10-30 回归：其它外键带 ON DELETE 不得让 created_by 被误判为「已改过」。"""
    out = mig.rewrite_fk_ddl(REAL_DDL)
    assert out is not None, "必须改写（原实现会因全文搜到 ON DELETE SET NULL 而跳过）"
    assert "FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL" in out
    # 其它外键原样保留
    assert "FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL" in out


def test_noop_when_created_by_already_has_on_delete():
    """created_by 自己已有 ON DELETE → 不改（幂等）。"""
    ddl = REAL_DDL.replace(
        "FOREIGN KEY(created_by) REFERENCES users (id)",
        "FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL",
    )
    assert mig.rewrite_fk_ddl(ddl) is None


def test_returns_none_when_no_created_by_fk():
    """没有 created_by 外键 → 返回 None，不炸。"""
    ddl = "CREATE TABLE t (id INTEGER PRIMARY KEY, created_by INTEGER)"
    assert mig.rewrite_fk_ddl(ddl) is None
    assert mig.rewrite_fk_ddl("") is None
    assert mig.rewrite_fk_ddl(None) is None