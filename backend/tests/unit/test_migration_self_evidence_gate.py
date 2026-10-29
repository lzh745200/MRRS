# -*- coding: utf-8 -*-
"""迁移自证门禁的负向用例（2026-10-29 审计项 C1 的可验证收口）。

对应 Critical「迁移基线自证」：`001_baseline` 用 `create_all()` 建库，导致 62 个迁移
在新库上从不被真正执行，B 轴门禁因此恒 0 漂移。本门禁要求"会改 schema 的迁移"
必须自带一个能独立构造旧库状态的测试 —— 下面验证它**真的会失败**，而不是永远绿。
"""
import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/unit/x.py -> 仓库根
_GATE = _REPO_ROOT / "scripts" / "check_migration_self_evidence.py"
_spec = importlib.util.spec_from_file_location("check_migration_self_evidence", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    versions = tmp_path / "versions"
    tests = tmp_path / "tests"
    baseline = tmp_path / "baseline.json"
    versions.mkdir()
    tests.mkdir()
    monkeypatch.setattr(gate, "VERSIONS", versions)
    monkeypatch.setattr(gate, "TESTS", tests)
    monkeypatch.setattr(gate, "BASELINE", baseline)
    return versions, tests, baseline


def _write_migration(versions: Path, filename: str, revision: str, body: str) -> None:
    (versions / filename).write_text(
        f'revision = "{revision}"\n\n\ndef upgrade():\n{body}\n',
        encoding="utf-8",
    )


def test_shape_changing_without_evidence_fails(sandbox):
    """新增一个改列的迁移但没有对应测试 → 门禁必须失败。"""
    versions, tests, _ = sandbox
    _write_migration(versions, "r99_alter_001.py", "r99_alter_001", "    op.alter_column('t', 'c')")
    data = gate.collect()
    assert [r["revision"] for r in data["missing"]] == ["r99_alter_001"]
    assert gate.main([]) == 1


def test_shape_changing_with_evidence_passes(sandbox):
    """有同名测试文件即视为有证据 → 通过。"""
    versions, tests, _ = sandbox
    _write_migration(versions, "r99_alter_001.py", "r99_alter_001", "    op.alter_column('t', 'c')")
    (tests / "test_r99_alter_001_evidence.py").write_text("def test_x(): pass\n", encoding="utf-8")
    assert gate.collect()["missing"] == []
    assert gate.main([]) == 0


def test_non_shape_changing_ignored(sandbox):
    """只改数据、不动 schema 的迁移不需要证据。"""
    versions, _tests, _ = sandbox
    _write_migration(versions, "r99_data_001.py", "r99_data_001", "    op.execute('UPDATE t SET c=1')")
    assert gate.collect()["missing"] == []
    assert gate.main([]) == 0


def test_exempt_baseline_suppresses(sandbox):
    """豁免清单里的历史迁移不追溯。"""
    versions, _tests, baseline = sandbox
    _write_migration(versions, "r99_alter_001.py", "r99_alter_001", "    op.drop_column('t', 'c')")
    baseline.write_text(json.dumps({"exempt": ["r99_alter_001"]}), encoding="utf-8")
    assert gate.collect()["missing"] == []
    assert gate.main([]) == 0


def test_json_mode_is_machine_readable(sandbox, capsys):
    """--json 必须输出纯 JSON（CI/其它门禁可能解析它）。"""
    versions, _tests, _ = sandbox
    _write_migration(versions, "r99_alter_001.py", "r99_alter_001", "    op.alter_column('t', 'c')")
    rc = gate.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["missing"][0]["revision"] == "r99_alter_001"


def test_real_repo_pii_migration_has_evidence():
    """真实仓库：pii_col_width_001 必须靠「证据」通过，而不是被豁免掉。"""
    data = gate.collect()
    pii = [r for r in data["shape_changing"] if "pii_col_width_001" in r["revision"]]
    assert pii, "未扫描到 pii_col_width_001 迁移"
    row = pii[0]
    assert row["evidence"] is True, "pii_col_width_001 必须有自证测试"
    assert row["exempt"] is False, "pii_col_width_001 不得依赖豁免通过"