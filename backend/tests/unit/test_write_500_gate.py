# -*- coding: utf-8 -*-
"""write_500 门禁自测（纯函数 + 探测循环 + 豁免清单契约）。

真实扫描要起实例，成本高，放在 slow 档门禁里跑；这里只锁住「什么算违规」的判定口径，
防止有人为了让门禁变绿而去放宽白名单或漏判。
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_write_500.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_write_500_under_test", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass / 类型注解在装饰期要回查 sys.modules，先登记再执行
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


class _StubResponse:
    def __init__(self, status):
        self.status = status


class _StubClient:
    """按路径返回预设状态码；"boom" 表示连接层失败。"""

    def __init__(self, statuses):
        self.statuses = dict(statuses)
        self.calls = []

    def request(self, method, path, payload=None, timeout=30.0):
        self.calls.append((method, path, payload, timeout))
        outcome = self.statuses[path]
        if outcome == "boom":
            raise gate.cs.SmokeFailure("connection reset by peer")
        return _StubResponse(outcome)


def test_sample_value_marks_ids_as_missing():
    assert gate.sample_value("village_id") == gate.MISSING_ID
    assert gate.sample_value("id") == gate.MISSING_ID
    assert gate.sample_value("rid") == gate.MISSING_ID


def test_sample_value_keeps_year_plausible():
    assert gate.sample_value("year") == gate.SAMPLE_YEAR
    assert gate.sample_value("annual_year") == gate.SAMPLE_YEAR


def test_sample_value_falls_back_to_slug():
    assert gate.sample_value("slug") == gate.MISSING_SLUG


def test_sample_value_ignores_path_converter_suffix():
    assert gate.sample_value("year:int") == gate.SAMPLE_YEAR
    assert gate.sample_value("item_id:int") == gate.MISSING_ID


def test_expand_path_substitutes_every_param():
    assert gate.expand_path("/api/v1/villages/{village_id}/files/{file_id}") == (
        "/api/v1/villages/999999/files/999999"
    )


def test_expand_path_keeps_year_params():
    assert gate.expand_path("/api/v1/reports/{year}/export") == "/api/v1/reports/2025/export"


def test_skip_reason_flags_destructive_endpoints():
    assert gate.skip_reason("/api/v1/system/shutdown")
    assert gate.skip_reason("/api/v1/system/backup/restore")
    assert "catch-all" in gate.skip_reason("/api/v1/{full_path:path}")


def test_skip_reason_allows_ordinary_write_endpoints():
    assert gate.skip_reason("/api/v1/supported-villages") is None


def test_sample_body_only_path_methods_have_no_body():
    assert gate.sample_body("POST") == {}
    assert gate.sample_body("PUT") == {}
    assert gate.sample_body("DELETE") is None


def test_classify_accepts_4xx_and_maintenance():
    for status in (200, 201, 204, 400, 403, 404, 409, 422, 429, 503):
        assert gate.classify(status) is None, status


def test_classify_rejects_unexpected_status():
    assert gate.classify(500) == "HTTP 500"
    assert gate.classify(502) == "HTTP 502"
    assert gate.classify(501) == "HTTP 501"


def test_classify_flags_token_rejection_and_connection_failure():
    assert "401" in gate.classify(401)
    assert gate.classify(-1) == "连接失败"


def test_entry_key_defaults_to_post():
    assert gate.entry_key({"path": "/api/v1/x", "status": 500}) == ("POST", "/api/v1/x", 500)


def test_partition_violations_splits_known_from_fresh():
    known = [{"method": "POST", "path": "/api/v1/offline-map/download", "status": 501}]
    fresh, excused = gate.partition_violations(
        [("POST", "/api/v1/offline-map/download", 501), ("DELETE", "/api/v1/x", 500)], known
    )
    assert excused == [("POST", "/api/v1/offline-map/download", 501)]
    assert fresh == [("DELETE", "/api/v1/x", 500)]


def test_filter_write_routes_keeps_only_api_write_endpoints():
    routes = [
        SimpleNamespace(methods={"POST"}, path="/api/v1/policies"),
        SimpleNamespace(methods={"GET"}, path="/api/v1/policies"),
        SimpleNamespace(methods={"GET", "POST"}, path="/health"),
        SimpleNamespace(methods={"DELETE"}, path="/api/v1/policies/{policy_id}"),
        SimpleNamespace(methods={"PUT"}, path="/api/v1/system/shutdown"),
        SimpleNamespace(methods={"POST"}, path="/api/v1/{full_path:path}"),
    ]
    kept, skipped = gate.filter_write_routes(routes)
    assert kept == [("DELETE", "/api/v1/policies/999999"), ("POST", "/api/v1/policies")]
    assert len(skipped) == 2
    assert all("shutdown" in item or "catch-all" in item for item in skipped)


def test_probe_all_records_status_and_connection_failures():
    client = _StubClient({"/api/v1/a": 500, "/api/v1/b": 422, "/api/v1/c": "boom"})
    violations = gate.probe_all(
        client,
        [("POST", "/api/v1/a"), ("PUT", "/api/v1/b"), ("DELETE", "/api/v1/c")],
    )
    assert violations == [("POST", "/api/v1/a", 500), ("DELETE", "/api/v1/c", -1)]
    assert [call[0] for call in client.calls] == ["POST", "PUT", "DELETE"]
    assert client.calls[2][2] is None


def test_scratch_dir_lives_under_project_scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    scratch = gate.scratch_dir()
    try:
        assert scratch.parent == tmp_path / ".scratch"
        assert scratch.is_dir()
        assert scratch.name.startswith("write500-")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_isolated_env_points_at_throwaway_database(tmp_path):
    env = gate.isolated_env(tmp_path)
    expected = "sqlite:///" + (tmp_path / "data" / "write500.db").as_posix()
    assert env["DATABASE_URL"] == expected
    db_path = env["DATABASE_URL"][len("sqlite:///"):]
    # 跨平台：Windows 是 C:/... 带盘符冒号，Linux 是 /tmp/... 无冒号，只校验绝对路径与库名
    assert Path(db_path).is_absolute()
    assert Path(db_path).name == "write500.db"
    assert Path(env["DATA_DIR"]).is_dir()
    assert Path(env["CACHE_DIR"]).is_dir()


def test_database_file_roundtrips_isolated_env(tmp_path):
    env = gate.isolated_env(tmp_path)
    assert gate.database_file(env) == tmp_path / "data" / "write500.db"


def test_baseline_only_excuses_declared_explicit_501():
    entries = json.loads(gate.BASELINE.read_text(encoding="utf-8"))
    assert entries, "豁免清单不应为空（至少登记 offline-map 的显式 501）"
    for entry in entries:
        assert set(entry) >= {"method", "path", "status", "reason"}
        assert entry["reason"].strip()
    keys = {(e["method"], e["path"], e["status"]) for e in entries}
    assert ("POST", "/api/v1/offline-map/download", 501) in keys
