# -*- coding: utf-8 -*-
"""check_crud_smoke 门禁自测：纯函数/客户端构造/运行器聚合，不需要起真实实例。

门禁本身（--slow）已在本地真实跑通；这里钉住那些「改动会让门禁变瞎」的细节：
信封解包、状态断言文案、CSRF 双提交头、失败不中断后续场景、隔离库落点。
"""

import importlib.util
import io
import sys
import urllib.error
from pathlib import Path

import pytest

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_crud_smoke.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_crud_smoke_gate_mod", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass 需要能按 __module__ 反查模块（模块未注册时 exec 阶段报 NoneType.__dict__）
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()


class _FakeHttpResponse:
    def __init__(self, status, body, headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _capture_urlopen(monkeypatch, response=None, error=None):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["request"] = request
        captured["timeout"] = timeout
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(gate.urllib.request, "urlopen", fake_urlopen)
    return captured


def _header(request, name):
    for key, value in list(request.headers.items()) + list(request.unredirected_hdrs.items()):
        if key.lower() == name.lower():
            return value
    return None


def test_expect_raises_smoke_failure():
    gate.expect(True, "不该抛")
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.expect(0, "值为假")
    assert "值为假" in str(excinfo.value)


def test_expect_status_accepts_allowed_and_reports_mismatch():
    resp = gate.Response(200, b'{"ok":true}', {})
    assert gate.expect_status(resp, (200, 204), "创建") is resp
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.expect_status(gate.Response(500, b'{"detail":"boom"}', {}), (200,), "创建")
    message = str(excinfo.value)
    assert "500" in message
    assert "boom" in message


def test_envelope_helpers_cover_three_shapes():
    assert gate.data_of(gate.Response(200, b'{"data":{"id":1}}', {})) == {"id": 1}
    assert gate.items_of(gate.Response(200, b'{"data":[{"id":1}]}', {})) == [{"id": 1}]
    assert gate.items_of(gate.Response(200, b'{"data":{"items":[{"id":2}]}}', {})) == [{"id": 2}]
    assert gate.items_of(gate.Response(200, b'{"items":[{"id":3}]}', {})) == [{"id": 3}]
    assert gate.items_of(gate.Response(200, b'{"data":{"total":0}}', {})) == []


def test_ids_of_ignores_items_without_id():
    assert gate.ids_of([{"id": 1}, {"id": None}, {}, "x"]) == [1]


def test_response_json_on_non_json_is_smoke_failure():
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.Response(200, b"<html>oops</html>", {}).json()
    assert "不是 JSON" in str(excinfo.value)


def test_created_id_requires_id():
    assert gate.created_id(gate.Response(200, b'{"data":{"id":7}}', {}), "帮扶村") == 7
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.created_id(gate.Response(200, b'{"data":{}}', {}), "帮扶村")
    assert "缺少 id" in str(excinfo.value)


def test_get_builds_authorized_request(monkeypatch):
    captured = _capture_urlopen(monkeypatch, _FakeHttpResponse(200, b'{"data":{}}'))
    client = gate.HttpClient("http://127.0.0.1:1", token="tok")
    resp = client.get("/api/v1/auth/me")
    request = captured["request"]
    assert resp.status == 200
    assert request.full_url == "http://127.0.0.1:1/api/v1/auth/me"
    assert request.get_method() == "GET"
    assert _header(request, "Authorization") == "Bearer tok"
    assert request.data is None
    assert _header(request, "X-CSRF-Token") is None


def test_post_sends_json_body(monkeypatch):
    captured = _capture_urlopen(monkeypatch, _FakeHttpResponse(200, b'{"data":{}}'))
    client = gate.HttpClient("http://127.0.0.1:1")
    client.post("/api/v1/x", {"a": 1})
    request = captured["request"]
    assert request.get_method() == "POST"
    assert request.data == b'{"a": 1}'
    assert _header(request, "Content-Type") == "application/json"


def test_http_error_is_returned_as_response(monkeypatch):
    error = urllib.error.HTTPError(
        "http://x/api/v1/y",
        403,
        "Forbidden",
        {"Content-Type": "application/json"},
        io.BytesIO(b'{"detail":"nope"}'),
    )
    _capture_urlopen(monkeypatch, error=error)
    response = gate.HttpClient("http://x").get("/api/v1/y")
    assert response.status == 403
    assert response.json()["detail"] == "nope"


def test_connection_error_is_smoke_failure(monkeypatch):
    _capture_urlopen(monkeypatch, error=urllib.error.URLError("connection refused"))
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.HttpClient("http://x").get("/api/v1/y")
    assert "连接失败" in str(excinfo.value)


def test_csrf_token_is_fetched_and_attached_to_writes(monkeypatch):
    responses = [
        _FakeHttpResponse(
            200,
            b'{"data":{"csrf_token":"1700000000.abc","csrf_signed_token":"sig"}}',
            {"Content-Type": "application/json", "Set-Cookie": "csrftoken=sig; Path=/; HttpOnly"},
        ),
        _FakeHttpResponse(200, b'{"data":{}}'),
    ]
    captured = []

    def fake_urlopen(request, timeout=None):
        captured.append(request)
        return responses[len(captured) - 1]

    monkeypatch.setattr(gate.urllib.request, "urlopen", fake_urlopen)
    client = gate.HttpClient("http://x")
    assert client.fetch_csrf() == "1700000000.abc"
    client.delete("/api/v1/system/config/crud_smoke_probe")
    write = captured[1]
    assert _header(write, "X-CSRF-Token") == "1700000000.abc"
    assert _header(write, "Cookie") == "csrftoken=sig"


def test_fetch_csrf_without_token_in_body_is_smoke_failure(monkeypatch):
    _capture_urlopen(monkeypatch, _FakeHttpResponse(200, b'{"data":{}}'))
    with pytest.raises(gate.SmokeFailure) as excinfo:
        gate.HttpClient("http://x").fetch_csrf()
    assert "csrf_token" in str(excinfo.value)


def test_upload_builds_multipart_body(monkeypatch):
    captured = _capture_urlopen(
        monkeypatch, _FakeHttpResponse(200, b'{"data":{"url":"/uploads/a.png"}}')
    )
    client = gate.HttpClient("http://x")
    response = client.upload(
        "/api/v1/files/upload", "a.png", gate.PNG_1X1, form={"category": "image"}
    )
    assert response.status == 200
    request = captured["request"]
    assert request.get_method() == "POST"
    assert _header(request, "Content-Type").startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="a.png"' in request.data
    assert b'name="category"' in request.data
    assert gate.PNG_1X1 in request.data


def test_run_scenarios_continues_after_failure():
    steps = []

    def broken(client, collected):
        raise gate.SmokeFailure("断言失败")

    def good(client, collected):
        collected.append(gate.Step("好场景", True))

    gate.run_scenarios(object(), steps, [("坏场景", broken), ("好场景", good)])
    assert [step.name for step in steps] == ["坏场景", "好场景"]
    assert steps[0].ok is False
    assert "断言失败" in steps[0].detail
    assert steps[1].ok is True


def test_isolated_env_points_at_absolute_isolated_db(tmp_path):
    env = gate.isolated_env(tmp_path / "scratch")
    assert env["DATABASE_URL"].startswith("sqlite:///")
    db_path = gate.database_file(env)
    assert db_path.is_absolute()
    assert db_path.name == "rural_revitalization.db"
    assert db_path.parent.name == "data"
    assert env["DATA_DIR"] == str(db_path.parent)
    assert Path(env["CACHE_DIR"]).is_dir()


def test_scratch_dir_creates_unique_writable_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "BACKEND", tmp_path / "backend")
    first = gate.scratch_dir()
    second = gate.scratch_dir()
    assert first.is_dir() and second.is_dir()
    assert first != second
    assert first.parent.name == ".scratch"
    assert first.name.startswith("crud-smoke-")


def test_print_report_marks_ok_and_failed_steps(capsys):
    steps = [gate.Step("登录", True), gate.Step("备份", False, "期望 200，实际 500")]
    gate.print_report(steps, verbose=False)
    concise = capsys.readouterr().out
    assert "[FAIL] 备份 — 期望 200，实际 500" in concise
    assert "[ok]" not in concise

    gate.print_report(steps, verbose=True)
    verbose = capsys.readouterr().out
    assert "[ok]   登录" in verbose
    assert "[FAIL] 备份" in verbose


def test_scenarios_cover_user_visible_capabilities_and_logout_is_last():
    names = [name for name, _scenario in gate.SCENARIOS]
    for keyword in ("登录", "设置", "帮扶村", "项目", "政策", "上传", "导出", "备份", "登出"):
        assert any(keyword in name for name in names), keyword
    assert "登出" in names
    assert gate.SCENARIOS[-1][0] == "登出", "登出会让令牌失效，必须最后执行"
