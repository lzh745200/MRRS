# -*- coding: utf-8 -*-
"""外键索引棘轮门禁的单测（含负向用例）。"""
import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_GATE = _REPO / "scripts" / "check_fk_indexes.py"
_spec = importlib.util.spec_from_file_location("check_fk_indexes", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _meta_with(table_builder):
    """用独立 MetaData 造一个最小 schema，返回 find_uncovered 的结果。"""
    from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

    md = MetaData()
    parent = Table("parent_t", md, Column("id", Integer, primary_key=True))
    table_builder(md, parent, Column, ForeignKey, Integer, Table)
    return md


def _scan(md, monkeypatch):
    monkeypatch.setattr(gate, "_load_metadata", lambda: md)
    return gate.find_uncovered()


def test_uncovered_fk_is_reported(monkeypatch):
    """外键列无索引 → 报出。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id")))

    items = _scan(_meta_with(build), monkeypatch)
    assert [i["column"] for i in items] == ["parent_id"]
    assert items[0]["references"] == "parent_t.id"


def test_indexed_fk_is_covered(monkeypatch):
    """外键列有单列索引 → 不报。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id"), index=True))

    assert _scan(_meta_with(build), monkeypatch) == []


def test_composite_index_second_position_does_not_cover(monkeypatch):
    """复合索引 (a, b) 不能服务 WHERE b = ? —— b 仍算未覆盖（首列语义）。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        from sqlalchemy import Index

        t = Table("child_t", md,
                  Column("id", Integer, primary_key=True),
                  Column("other", Integer),
                  Column("parent_id", Integer, ForeignKey("parent_t.id")))
        Index("ix_child_other_parent", t.c.other, t.c.parent_id)

    items = _scan(_meta_with(build), monkeypatch)
    assert [i["column"] for i in items] == ["parent_id"]


def test_unique_constraint_covers(monkeypatch):
    """唯一约束首列覆盖 → 不报。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id"), unique=True))

    assert _scan(_meta_with(build), monkeypatch) == []


def test_no_fk_no_report(monkeypatch):
    """没有外键的表不产生条目。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("name", Integer))

    assert _scan(_meta_with(build), monkeypatch) == []


def test_new_uncovered_fails_against_baseline(monkeypatch, tmp_path, capsys):
    """负向：基线外的**新增**未覆盖外键必须让门禁失败。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id")))

    md = _meta_with(build)
    monkeypatch.setattr(gate, "_load_metadata", lambda: md)
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "fk_indexes.json")
    assert gate.main([]) == 1
    assert "child_t.parent_id" in capsys.readouterr().out


def test_baselined_passes(monkeypatch, tmp_path):
    """已登记基线 → 通过（棘轮：只拦新增）。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id")))

    md = _meta_with(build)
    monkeypatch.setattr(gate, "_load_metadata", lambda: md)
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "fk_indexes.json")
    gate._save_baseline({"child_t.parent_id"})
    assert gate.main([]) == 0


def test_json_mode_machine_readable(monkeypatch, tmp_path, capsys):
    """--json 输出纯 JSON。"""

    def build(md, parent, Column, ForeignKey, Integer, Table):
        Table("child_t", md, Column("id", Integer, primary_key=True),
              Column("parent_id", Integer, ForeignKey("parent_t.id")))

    md = _meta_with(build)
    monkeypatch.setattr(gate, "_load_metadata", lambda: md)
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "fk_indexes.json")
    rc = gate.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["added"] == ["child_t.parent_id"]


def test_real_repo_baseline_matches():
    """真实仓库：基线必须与实测一致（否则基线过期）。"""
    keys = gate._keys(gate.find_uncovered())
    known = gate._load_baseline()
    assert keys == known, (sorted(keys - known)[:8], sorted(known - keys)[:8])
