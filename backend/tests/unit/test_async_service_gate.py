# -*- coding: utf-8 -*-
"""AsyncSession 服务棘轮门禁的单测（含负向用例）。"""

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_GATE = _REPO / "scripts" / "check_async_service_usage.py"
_spec = importlib.util.spec_from_file_location("check_async_service_usage", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _sandbox(tmp_path, monkeypatch):
    app = tmp_path / "backend" / "app" / "services"
    app.mkdir(parents=True)
    baseline = tmp_path / "backend" / "scripts" / "gate_baselines" / "async_services.json"
    monkeypatch.setattr(gate, "APP", tmp_path / "backend" / "app")
    monkeypatch.setattr(gate, "BASELINE", baseline)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    return app, baseline


def test_detects_async_service(tmp_path, monkeypatch):
    """import AsyncSession + db: AsyncSession → 被识别。"""
    app, _ = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "class FooService:\n"
        "    def __init__(self, db: AsyncSession):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    items = gate.find_async_services()
    assert len(items) == 1
    assert items[0]["classes"] == ["FooService"]


def test_sync_service_not_detected(tmp_path, monkeypatch):
    """同步 Session 服务 → 不计入。"""
    app, _ = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        "from sqlalchemy.orm import Session\n"
        "class BarService:\n"
        "    def __init__(self, db: Session):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    assert gate.find_async_services() == []


def test_docstring_mention_is_not_detected(tmp_path, monkeypatch):
    """只在注释/docstring 里提到 AsyncSession（如历史说明）→ 不计入。"""
    app, _ = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        '"""历史：将 AsyncSession 修正为同步 Session。"""\n'
        "# db: AsyncSession 曾是构造参数\n"
        "from sqlalchemy.orm import Session\n"
        "class BazService:\n"
        "    def __init__(self, db: Session):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    assert gate.find_async_services() == []


def test_new_async_service_fails_against_baseline(tmp_path, monkeypatch, capsys):
    """负向：基线外新增 AsyncSession 服务必须失败。"""
    app, _ = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "class NewService:\n"
        "    def __init__(self, db: AsyncSession):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    assert gate.main([]) == 1
    out = capsys.readouterr().out  # 只读一次（readouterr 会消费缓冲）
    assert "svc.py" in out, out


def test_baselined_passes(tmp_path, monkeypatch):
    """已登记基线 → 通过（棘轮：只拦新增）。"""
    app, baseline = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "class OldService:\n"
        "    def __init__(self, db: AsyncSession):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    gate._save_baseline({gate.find_async_services()[0]["file"]})
    assert gate.main([]) == 0


def test_json_mode(tmp_path, monkeypatch, capsys):
    """--json 输出纯 JSON。"""
    app, _ = _sandbox(tmp_path, monkeypatch)
    (app / "svc.py").write_text(
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "class JService:\n"
        "    def __init__(self, db: AsyncSession):\n"
        "        self.db = db\n",
        encoding="utf-8",
    )
    rc = gate.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["count"] == 1
    assert len(payload["added"]) == 1


def test_real_repo_baseline_matches():
    """真实仓库：基线必须与实测一致（否则基线过期）。"""
    files = {i["file"] for i in gate.find_async_services()}
    known = gate._load_baseline()
    assert files == known, (sorted(files - known), sorted(known - files))
