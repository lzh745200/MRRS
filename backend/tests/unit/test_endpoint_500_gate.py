# -*- coding: utf-8 -*-
"""check_endpoint_500.py 的巡检口径回归（P0-F2）。

纯单元断言（不拉真服务进程），锁两件事：
1. 哪些状态码算违规 —— 5xx / 连接失败两态都红；匿名态 401 放行，带管理员令牌仍 401 必红；
2. 豁免清单按 (mode, path, status) 三元组抵扣 —— 同一路径两种登录态的结论互不顶替（棘轮只减不增）。
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_endpoint_500.py"
spec = spec_from_file_location("check_endpoint_500", GATE_PATH)
gate = module_from_spec(spec)
spec.loader.exec_module(gate)


def _patch_http(monkeypatch, mapping):
    def fake(url: str, timeout: float = 10.0, token=None):
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


def test_classify_5xx_is_violation_in_both_modes():
    assert gate.classify(500, gate.MODE_ANON) == "HTTP 500"
    assert gate.classify(500, gate.MODE_AUTH) == "HTTP 500"
    assert gate.classify(502, gate.MODE_ANON) == "HTTP 502"
    # 503 是维护窗口对写请求的合法降级响应，不算服务端错误
    assert gate.classify(503, gate.MODE_ANON) is None


def test_classify_anon_401_allowed_but_auth_401_flagged():
    assert gate.classify(401, gate.MODE_ANON) is None
    assert gate.classify(401, gate.MODE_AUTH)


def test_classify_ordinary_and_connection_states():
    for status in (200, 204, 302, 403, 404, 405, 422, 429):
        assert gate.classify(status, gate.MODE_AUTH) is None, status
    assert gate.classify(-1, gate.MODE_ANON)
    assert gate.classify(418, gate.MODE_ANON)


def test_probe_all_reports_5xx_only(monkeypatch):
    _patch_http(monkeypatch, {"/a": 401, "/b": 422, "/c": 503, "/bad": 500, "/oops": 502})
    violations = gate.probe_all("http://x", ["/a", "/b", "/c", "/bad", "/ok", "/oops"], gate.MODE_ANON)
    assert violations == [("/bad", 500, "anon"), ("/oops", 502, "anon")]


def test_probe_all_flags_401_only_when_authenticated(monkeypatch):
    _patch_http(monkeypatch, {"/me": 401})
    assert gate.probe_all("http://x", ["/me"], gate.MODE_ANON) == []
    assert gate.probe_all("http://x", ["/me"], gate.MODE_AUTH, token="t") == [("/me", 401, "auth")]


def test_probe_all_surfaces_connection_error(monkeypatch):
    def boom(url, timeout=10.0, token=None):
        raise RuntimeError("refused")

    monkeypatch.setattr(gate, "http_get", boom)
    with pytest.raises(RuntimeError, match="refused"):
        gate.probe_all("http://x", ["/boom"], gate.MODE_ANON)


def test_legacy_baseline_entry_without_mode_counts_as_anon():
    assert gate.entry_key({"path": "/api/v1/x", "status": 500}) == ("anon", "/api/v1/x", 500)


def test_known_exemptions_are_discounted_not_erased():
    """基线豁免只抵扣对应三元组，新的 5xx 不受其影响（棘轮只减不增）。"""
    known = [{"path": "/bad", "status": 500, "reason": "x"}]
    fresh, excused = gate.partition_violations(
        [("/bad", 500, "anon"), ("/worse", 500, "anon")], known
    )
    assert excused == [("/bad", 500, "anon")]
    assert fresh == [("/worse", 500, "anon")]


def test_same_path_different_mode_is_not_interchangeable():
    known = [{"mode": "anon", "path": "/api/v1/x", "status": 401}]
    fresh, excused = gate.partition_violations(
        [("/api/v1/x", 401, "anon"), ("/api/v1/x", 401, "auth")], known
    )
    assert excused == [("/api/v1/x", 401, "anon")]
    assert fresh == [("/api/v1/x", 401, "auth")]


def test_isolated_env_points_at_absolute_sqlite_url(tmp_path):
    env = gate.isolated_env(tmp_path)
    assert env["DATABASE_URL"].startswith("sqlite:///")
    db_path = gate.database_file(env)
    assert db_path.is_absolute()
    assert db_path.parent == tmp_path / "data"
    assert Path(env["DATA_DIR"]) == tmp_path / "data"
    assert Path(env["CACHE_DIR"]) == tmp_path / "cache"


def test_collect_get_paths_skips_parametrized_routes():
    paths = gate.collect_get_paths()
    assert "/health" in paths
    assert paths == sorted(set(paths))
    assert not [p for p in paths if "{" in p]


def test_expand_path_substitutes_sample_values():
    assert gate.expand_path("/api/v1/projects/{project_id}") == "/api/v1/projects/1"
    assert gate.expand_path("/api/v1/stats/year/{year}") == "/api/v1/stats/year/2025"
    assert gate.expand_path("/api/v1/x/{annual_year}/detail") == "/api/v1/x/2025/detail"
    assert gate.expand_path("/api/v1/plain") == "/api/v1/plain"


def test_collect_expanded_paths_skips_spa_catch_all():
    """路径参数扫描必须代入样例值，且不把 SPA catch-all 当 API。"""
    expanded = gate.collect_expanded_paths()
    assert expanded, "带路径参数的 GET 应当非空"
    assert expanded == sorted(set(expanded))
    assert not [p for p in expanded if "{" in p]
    assert not [p for p in expanded if "missing.txt" in p]


def test_classify_allows_400_only_for_path_param_sweep():
    """样例值不是合法枚举值时，400 是参数校验的主动拒绝，只在带参扫描里放行。"""
    assert gate.classify(400, gate.MODE_AUTH, allow_bad_request=True) is None
    assert gate.classify(400, gate.MODE_ANON, allow_bad_request=True) is None
    assert gate.classify(400, gate.MODE_AUTH) == "HTTP 400"
    # 放行 400 不能顺手放行 5xx
    assert gate.classify(500, gate.MODE_AUTH, allow_bad_request=True) == "HTTP 500"


def test_cleanup_scratch_removes_the_throwaway_dir(tmp_path):
    """一次性库目录必须真被删掉，不能静默留残骸（Windows 句柄释放慢，故重试）。"""
    scratch = tmp_path / "endpoint500-clean"
    (scratch / "data").mkdir(parents=True)
    (scratch / "data" / "endpoint500.db").write_text("x", encoding="utf-8")
    assert gate.cleanup_scratch(scratch, attempts=3, delay_s=0) is True
    assert not scratch.exists()


def test_probe_all_allow_bad_request_flag(monkeypatch):
    _patch_http(monkeypatch, {"/tier/1": 400, "/bad": 500})
    assert gate.probe_all(
        "http://x", ["/tier/1"], gate.MODE_ANON, allow_bad_request=True
    ) == []
    assert gate.probe_all("http://x", ["/bad"], gate.MODE_ANON, allow_bad_request=True) == [
        ("/bad", 500, "anon")
    ]
