# -*- coding: utf-8 -*-
"""check_frozen_smoke.py 的口径回归（P0-F1）。

只断言纯函数与「缺失即 SKIP」语义，不真的启动 35MB 冻结产物（那属于发布前置/nightly）。
"""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_frozen_smoke.py"
spec = spec_from_file_location("check_frozen_smoke", GATE_PATH)
gate = module_from_spec(spec)
spec.loader.exec_module(gate)


def test_missing_artifact_is_skip_not_fail(monkeypatch):
    """产物不存在必须 SKIP（退出 0），否则日常开发与无构建环境会被挡住。"""
    monkeypatch.setattr(gate, "FROZEN_EXE", Path("Z:/definitely/missing/assistance-backend.exe"))
    assert gate.main([]) == 0


def test_isolated_env_sets_writable_runtime_dirs(monkeypatch, tmp_path):
    """必须显式给 DATA_DIR/CACHE_DIR，且落点在可写目录（%TEMP% 在受限环境会 WinError 5）。"""
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    scratch = gate._scratch_dir()
    assert scratch.exists() and scratch.is_dir()
    assert str(tmp_path) in str(scratch), "落点必须在传入 ROOT 之下"
    env = gate._isolated_env(scratch)
    assert env["DATA_DIR"] == str(scratch / "data")
    assert env["CACHE_DIR"] == str(scratch / "cache")


def test_pick_free_port_is_in_range():
    port = gate._pick_free_port()
    assert 1024 <= port <= 65535


def test_health_probe_fails_loudly_when_never_ready(monkeypatch):
    """起不来时必须返回失败并带原因，不能静默成功。"""
    monkeypatch.setattr(gate, "_pick_free_port", lambda: 9)
    monkeypatch.setattr(gate, "_scratch_dir", lambda: Path("."))
    monkeypatch.setattr(gate, "_isolated_env", lambda scratch: {})

    def boom(url, timeout=5.0):
        raise RuntimeError("refused")

    monkeypatch.setattr(gate, "_http_get", boom)

    class _Proc:
        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(gate.subprocess, "Popen", lambda *a, **kw: _Proc())
    ok, detail = gate.run_health_probe(timeout_s=0.1)
    assert ok is False and "health" in detail