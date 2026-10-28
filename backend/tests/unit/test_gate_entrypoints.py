# -*- coding: utf-8 -*-
"""门禁统一入口 / no-print / dist 体积棘轮 的元测试。

三件事分别对应 2026-10-28 体检结论：
1. 29 道门禁调用方式各异，必须有唯一入口（run_gates.py），且**不能漏跑** ——
   本文件比对 CI workflow 里出现的每个 check_*.py 都已在注册表中；
2. 生产代码 print 在桌面端不可见，门禁要能区分"允许的启动/日志兜底"与"新增 print"；
3. 前端产物体积需要棘轮，防无意膨胀。
"""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PR_CHECKS = ROOT / ".github" / "workflows" / "pr-checks.yml"


def _load(name: str, rel: str):
    # 必须先注册进 sys.modules：run_gates.py 用了 @dataclass，dataclasses 在解析
    # 注解时需要 sys.modules[cls.__module__].__dict__，否则 AttributeError。
    import sys

    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_ci_check_scripts_are_all_registered():
    """CI 里出现的每个 check_*.py 都必须在 run_gates 注册表中（防漏跑）。"""
    runner = _load("run_gates", "scripts/run_gates.py")
    workflow = PR_CHECKS.read_text(encoding="utf-8")
    referenced = set(re.findall(r"((?:\.\./)?scripts/check_[a-z0-9_]+\.py)", workflow))
    assert referenced, "未能从 pr-checks.yml 解析出任何 check_*.py（正则失效？）"

    registered = " ".join(" ".join(gate.argv) for gate in runner.GATES)
    missing = [script for script in sorted(referenced) if script not in registered]
    assert not missing, "这些 CI 门禁没有进统一入口: %s" % missing


def test_every_registered_gate_script_exists():
    runner = _load("run_gates2", "scripts/run_gates.py")
    missing = []
    for gate in runner.GATES:
        script = gate.argv[0]
        if script.startswith("-"):
            continue
        path = (gate.cwd / script).resolve()
        if not path.is_file():
            missing.append("%s -> %s" % (gate.name, script))
    assert not missing, "注册的门禁脚本不存在: %s" % missing


def test_gate_names_unique_and_backend_cwd_correct():
    runner = _load("run_gates3", "scripts/run_gates.py")
    names = [gate.name for gate in runner.GATES]
    assert len(names) == len(set(names)), "门禁名重复"
    for gate in runner.GATES:
        if gate.argv[0].startswith("../scripts/"):
            assert gate.cwd == runner.BACKEND, "%s 必须在 backend 下运行" % gate.name


class TestNoPrintGate:
    def test_repo_has_no_violations(self):
        gate = _load("check_no_print", "scripts/check_no_print.py")
        assert gate.scan() == []

    def test_detects_new_print_but_skips_allowlisted_file(self, tmp_path):
        app = tmp_path / "app"
        (app / "core").mkdir(parents=True)
        (app / "main.py").write_text("print('boot', flush=True)\n", encoding="utf-8")
        (app / "core" / "logging_config.py").write_text("print('fallback')\n", encoding="utf-8")
        (app / "services").mkdir()
        (app / "services" / "x.py").write_text("def f():\n    print('debug')\n", encoding="utf-8")

        gate = _load("check_no_print2", "scripts/check_no_print.py")
        problems = gate.scan(app)

        assert len(problems) == 1
        assert problems[0]["file"].endswith("services/x.py")
        assert problems[0]["line"] == 2

    def test_identifier_named_print_is_not_matched(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        (app / "x.py").write_text(
            "setup_print(ws)\nfingerprint = key_fingerprint()\n", encoding="utf-8"
        )

        gate = _load("check_no_print3", "scripts/check_no_print.py")

        assert gate.scan(app) == []


class TestDistSizeGate:
    def test_measure_and_compare_detects_growth(self, tmp_path):
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "assets" / "a.js").write_bytes(b"x" * 100)
        (dist / "assets" / "a.js.br").write_bytes(b"x" * 10)

        gate = _load("check_dist_size", "scripts/check_dist_size.py")
        current = gate.measure(dist)
        baseline = {"total_bytes": 110, "file_count": 2, "br_count": 1}

        assert current["file_count"] == 2
        assert current["br_count"] == 1
        assert gate.compare(current, baseline) == []

        grown = dict(current, total_bytes=int(110 * 1.5))
        problems = gate.compare(grown, baseline)
        assert any("total_bytes" in item for item in problems)

    def test_tolerance_allows_small_jitter(self):
        gate = _load("check_dist_size2", "scripts/check_dist_size.py")
        baseline = {"total_bytes": 1000, "file_count": 3, "br_count": 1}

        assert gate.compare({"total_bytes": 1020, "file_count": 3, "br_count": 1}, baseline) == []
        assert gate.compare({"total_bytes": 1100, "file_count": 3, "br_count": 1}, baseline)

class TestBenchCompare:
    """性能基线只报警不阻断：阈值 50%，rows 不参与比较。"""

    def test_compare_flags_only_beyond_threshold(self):
        bench = _load("bench", "scripts/bench.py")
        baseline = {"rows": 5000, "xlsx_parse_s": 1.0, "csv_export_s": 0.1, "template_build_s": 0.5}

        assert bench.compare({"rows": 5000, "xlsx_parse_s": 1.4, "csv_export_s": 0.1,
                              "template_build_s": 0.5}, baseline) == []

        problems = bench.compare({"rows": 5000, "xlsx_parse_s": 1.6, "csv_export_s": 0.1,
                                  "template_build_s": 0.5}, baseline)
        assert len(problems) == 1 and "xlsx_parse_s" in problems[0]

    def test_rows_key_is_never_compared(self):
        bench = _load("bench2", "scripts/bench.py")
        assert bench.compare({"rows": 999999, "xlsx_parse_s": 1.0}, {"xlsx_parse_s": 1.0}) == []
