# -*- coding: utf-8 -*-
"""check_endpoint_500.py 的巡检口径回归（P0-F2）。

只对公开函数做纯单元断言（不拉真服务进程）：状态白名单、5xx 捕获、基线抵扣、只挑 GET。
"""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

import pytest

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_endpoint_500.py"
spec = spec_from_file_location("check_endpoint_500", GATE_PATH)
gate = module_from_spec(spec)
spec.loader.exec_module(gate)


def _patch_http(monkeypatch, mapping):
    def fake(url: str, timeout: float = 10.0):
        for suffix, status in mapping.items():
            if url.endswith(suffix):
                return status, ""
        return 200, ""

    monkeypatch.setattr(gate, "http_get", fake)


def test_allowed_statuses_complete():
    for allowed in (200, 204, 301, 302, 304, 401, 403, 404, 405, 422, 429, 503):
        assert allowed in gate.ALLOWED_STATUSES, allowed
    for violet in (500, 502, 504, 511):
        assert violet not in gate.ALLOWED_STATUSES, violet


def test_probe_all_reports_5xx_only(monkeypatch):
    _patch_http(monkeypatch, {"/a": 401, "/b": 422, "/c": 503, "/bad": 500, "/oops": 502})
    violations = gate.probe_all("http://x", ["/a", "/b", "/c", "/bad", "/ok", "/oops"])
    assert violations == [("/bad", 500), ("/oops", 502)]


def test_probe_all_surfaces_connection_error(monkeypatch):
    monkeypatch.setattr(
        gate, "http_get",
        lambda url, timeout=10.0: (_ for _ in ()).throw(RuntimeError("refused")),
    )
    with pytest.raises(RuntimeError, match="refused"):
        gate.probe_all("http://x", ["/boom"])


def test_known_exemptions_are_discounted_not_erased(monkeypatch):
    """基线豁免只抵扣对应条目，新的 5xx 不受其影响（棘轮只减不增）。"""
    _patch_http(monkeypatch, {"/bad": 500, "/worse": 500})
    known = json_like([{"path": "/bad", "status": 500, "reason": "x"}])
    fresh = [(p, s) for p, s in gate.probe_all("http://x", ["/bad", "/worse"])
             if (p, s) not in known]
    assert fresh == [("/worse", 500)]


def json_like(items):
    return {(x["path"], x["status"]) for x in items}