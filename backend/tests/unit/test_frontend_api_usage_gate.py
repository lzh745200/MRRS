# -*- coding: utf-8 -*-
"""前端 API 使用率棘轮门禁的单测（含负向用例）。"""
import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_GATE = _REPO / "scripts" / "check_frontend_api_usage.py"
_spec = importlib.util.spec_from_file_location("check_frontend_api_usage", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    src = tmp_path / "frontend" / "src"
    api = src / "api"
    views = src / "views"
    api.mkdir(parents=True)
    views.mkdir(parents=True)
    (tmp_path / "backend" / "scripts" / "gate_baselines").mkdir(parents=True)
    monkeypatch.setattr(gate, "FE_SRC", src)
    monkeypatch.setattr(gate, "API_DIR", api)
    baseline = tmp_path / "backend" / "scripts" / "gate_baselines" / "frontend_api_usage.json"
    monkeypatch.setattr(gate, "BASELINE", baseline)
    return api, views


def test_detects_function_only_tests_use(sandbox):
    """定义了但 src 不用（也不经聚合对象暴露）→ 计为未使用。"""
    api, views = sandbox
    (api / "demo.ts").write_text("export async function orphanApi() { return 1 }\n", encoding="utf-8")
    (views / "Page.vue").write_text("<script setup>const x = 1</script>\n", encoding="utf-8")
    unused = gate.find_unused()
    assert [u["name"] for u in unused] == ["orphanApi"]


def test_used_in_page_is_not_reported(sandbox):
    """页面直接引用 → 不算未使用。"""
    api, views = sandbox
    (api / "demo.ts").write_text("export async function usedApi() { return 1 }\n", encoding="utf-8")
    (views / "Page.vue").write_text(
        '<script setup>import { usedApi } from "@/api/demo"\nusedApi()</script>\n',
        encoding="utf-8",
    )
    assert gate.find_unused() == []


def test_exposed_via_aggregate_object_is_not_reported(sandbox):
    """经 export const xxxApi = { foo } 暴露 → 不算未使用（页面写 xxxApi.foo()）。"""
    api, views = sandbox
    (api / "demo.ts").write_text(
        "export async function viaObj() { return 1 }\n"
        "export const demoApi = { viaObj }\n",
        encoding="utf-8",
    )
    (views / "Page.vue").write_text("<script setup>demoApi.viaObj()</script>\n", encoding="utf-8")
    assert gate.find_unused() == []


def test_new_unused_fails_against_baseline(sandbox, capsys):
    """负向：基线外的**新增**未使用函数必须让门禁失败。"""
    api, views = sandbox
    (api / "demo.ts").write_text("export async function freshOrphan() { return 1 }\n", encoding="utf-8")
    (views / "Page.vue").write_text("<script setup>const x = 1</script>\n", encoding="utf-8")
    # 基线为空 → 必然新增
    assert gate.main([]) == 1
    out = capsys.readouterr().out
    assert "freshOrphan" in out


def test_baselined_unused_passes(sandbox):
    """已登记基线的未使用函数 → 门禁通过（棘轮：只拦新增）。"""
    api, views = sandbox
    (api / "demo.ts").write_text("export async function knownOrphan() { return 1 }\n", encoding="utf-8")
    (views / "Page.vue").write_text("<script setup>const x = 1</script>\n", encoding="utf-8")
    gate._save_baseline({"knownOrphan"})
    assert gate.main([]) == 0


def test_json_mode_machine_readable(sandbox, capsys):
    """--json 输出纯 JSON（供 CI/其它门禁解析）。"""
    api, views = sandbox
    (api / "demo.ts").write_text("export async function orphanApi() { return 1 }\n", encoding="utf-8")
    (views / "Page.vue").write_text("<script setup>const x = 1</script>\n", encoding="utf-8")
    rc = gate.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["added"] == ["orphanApi"]


def test_real_repo_baseline_matches():
    """真实仓库：基线必须与实测一致（否则说明基线过期）。"""
    unused = {u["name"] for u in gate.find_unused()}
    known = gate._load_baseline()
    assert unused == known, (sorted(unused - known)[:10], sorted(known - unused)[:10])
