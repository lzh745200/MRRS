"""组织模块策略闸门单测（短期改进第 5 项，2026-11-01）。

覆盖 backend/app/middleware/org_module_policy_gate.py 的全部分支：
- off / shadow / enforce 三种执行模式；GET 与非 HTTP 请求放行；
- 无策略 / full_edit / 用户无组织 / 无认证 / 未映射路径放行；
- 策略查询异常放行（fail-open：配置查询失败不能让全站写接口 500），shadow 与
  enforce 两种模式都锁住；
- 5 秒 TTL 缓存：命中不重复查库、"无策略"负缓存、过期后重查、手动清缓存后重查，
  且 off 模式在缓存/查库之前直接放行（零开销）；
- current_mode 合法/非法/空值归一；resolve_module_key 最长前缀与路径边界；
- resolve_user 令牌链路各失败分支；load_policy_edit_mode 有/无策略；
- _open_session 惰性打开会话；shadow 响应头在真实 ASGI 响应链上生效。
"""
import logging
from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.middleware import org_module_policy_gate as gate

LOGGER_NAME = "app.middleware.org_module_policy_gate"


# ════════════════════════════════════════════════════════════════
# 测试替身
# ════════════════════════════════════════════════════════════════
class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeDB:
    """只实现本中间件用到的 query(...).filter(...).first() 链。"""

    def __init__(self, result):
        self._result = result

    def query(self, model):
        return _FakeQuery(self._result)


def _scope(auth=None):
    headers = []
    if auth is not None:
        headers.append((b"authorization", auth.encode("latin-1")))
    return {"type": "http", "method": "POST", "path": "/api/v1/projects", "headers": headers}


def _patch_user_and_policy(
    monkeypatch,
    *,
    edit_mode="read_only",
    organization_id=7,
    user_present=True,
    error=False,
):
    """替换 _open_session / resolve_user / load_policy_edit_mode，返回 (db, 各 mock)。"""
    db = SimpleNamespace(close=mock.Mock())
    user = SimpleNamespace(organization_id=organization_id) if user_present else None
    resolve_user = mock.Mock(return_value=user)
    if error:
        load_policy = mock.Mock(side_effect=RuntimeError("db down"))
    else:
        load_policy = mock.Mock(return_value=edit_mode)
    monkeypatch.setattr(gate, "_open_session", lambda: db)
    monkeypatch.setattr(gate, "resolve_user", resolve_user)
    monkeypatch.setattr(gate, "load_policy_edit_mode", load_policy)
    return db, resolve_user, load_policy


@pytest.fixture(autouse=True)
def _reset_policy_cache():
    """每个用例前后清空进程内策略缓存，避免 (org, module) 键互相污染。"""
    gate.clear_policy_cache()
    yield
    gate.clear_policy_cache()


@pytest.fixture()
def client():
    """临时挂载中间件的独立 app：映射路径 + 未映射路径 + GET。"""
    app = FastAPI()

    @app.post("/api/v1/projects")
    def create_project():
        return {"ok": True}

    @app.get("/api/v1/projects")
    def list_projects():
        return {"ok": True}

    @app.api_route("/api/v1/projects", methods=["HEAD", "OPTIONS"])
    def probe_projects():
        return {"ok": True}

    @app.post("/api/v1/unmapped")
    def unmapped():
        return {"ok": True}

    app.add_middleware(gate.OrgModulePolicyGateMiddleware)
    return TestClient(app)


# ════════════════════════════════════════════════════════════════
# 模式裁决：off / shadow / enforce
# ════════════════════════════════════════════════════════════════
class TestModes:
    def test_off_never_blocks_and_skips_policy_lookup(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "off")
        db, resolve_user, load_policy = _patch_user_and_policy(monkeypatch)
        cache_get = mock.Mock(side_effect=AssertionError("off 模式不得触碰缓存"))
        monkeypatch.setattr(gate, "_cache_get", cache_get)
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        assert "x-org-module-policy" not in resp.headers
        resolve_user.assert_not_called()
        load_policy.assert_not_called()
        cache_get.assert_not_called()
        db.close.assert_not_called()

    def test_shadow_passes_and_adds_header(self, client, monkeypatch, caplog):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        db, _, _ = _patch_user_and_policy(monkeypatch, edit_mode="read_only")
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.headers["x-org-module-policy"] == "would-block"
        assert "module=projects organization_id=7 edit_mode=read_only" in caplog.text
        db.close.assert_called_once()

    def test_shadow_without_policy_passes_without_header(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        _patch_user_and_policy(monkeypatch, edit_mode=None)
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        assert "x-org-module-policy" not in resp.headers

    def test_enforce_read_only_blocks_403(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        _patch_user_and_policy(monkeypatch, edit_mode="read_only")
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == 403
        assert body["success"] is False
        assert "organization_id" not in body  # 不透传内部字段名
        for part in ("组织（ID=7）", "「projects」", "只读"):
            assert part in body["detail"]
        assert "x-org-module-policy" not in resp.headers

    def test_enforce_disabled_blocks_403(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        _patch_user_and_policy(monkeypatch, edit_mode="disabled")
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 403
        assert "禁用" in resp.json()["detail"]

    def test_enforce_full_edit_passes(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        _patch_user_and_policy(monkeypatch, edit_mode="full_edit")
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        assert "x-org-module-policy" not in resp.headers


# ════════════════════════════════════════════════════════════════
# 放行分支：读方法 / 未映射 / 无认证 / 无组织 / 判定异常
# ════════════════════════════════════════════════════════════════
class TestPassthrough:
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_read_methods_never_blocked(self, client, monkeypatch, method):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        _patch_user_and_policy(monkeypatch)
        resp = client.request(method, "/api/v1/projects")
        assert resp.status_code == 200

    def test_unmapped_path_passes_and_skips_lookup(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        _patch_user_and_policy(monkeypatch)
        evaluator = mock.Mock(side_effect=AssertionError("未映射路径不得查策略"))
        monkeypatch.setattr(gate, "evaluate_policy", evaluator)
        resp = client.post("/api/v1/unmapped")
        assert resp.status_code == 200
        evaluator.assert_not_called()

    def test_request_without_credentials_passes(self, client, monkeypatch):
        """真实 resolve_user + 真实 _open_session：无令牌直接放行、不查策略。"""
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        policy_query = mock.Mock(side_effect=AssertionError("无认证不得查策略"))
        monkeypatch.setattr(gate, "load_policy_edit_mode", policy_query)
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        policy_query.assert_not_called()

    def test_user_without_organization_passes(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "enforce")
        db, _, load_policy = _patch_user_and_policy(monkeypatch, organization_id=None)
        resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        load_policy.assert_not_called()
        db.close.assert_called_once()

    @pytest.mark.parametrize("mode", ["shadow", "enforce"])
    def test_policy_lookup_error_passes_with_warning(self, client, monkeypatch, caplog, mode):
        """策略查询异常必须放行（不得 500）：enforce 下也 fail-open。"""
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", mode)
        db, _, _ = _patch_user_and_policy(monkeypatch, error=True)
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            resp = client.post("/api/v1/projects")
        assert resp.status_code == 200
        assert "组织模块策略闸门判定异常，已放行" in caplog.text
        db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        called = False

        async def fake_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = gate.OrgModulePolicyGateMiddleware(fake_app)
        await middleware({"type": "websocket"}, None, None)
        assert called is True


# ════════════════════════════════════════════════════════════════
# 5 秒 TTL 策略缓存
# ════════════════════════════════════════════════════════════════
class _Clock:
    """可手动推进的 monotonic 替身（只 patch gate._monotonic）。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


class TestPolicyCache:
    def test_second_request_hits_cache(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        _, _, load_policy = _patch_user_and_policy(monkeypatch, edit_mode="read_only")
        first = client.post("/api/v1/projects")
        second = client.post("/api/v1/projects")
        assert first.headers["x-org-module-policy"] == "would-block"
        assert second.headers["x-org-module-policy"] == "would-block"
        load_policy.assert_called_once()

    def test_none_policy_is_cached(self, client, monkeypatch):
        """无策略（None）也要负缓存，避免每次写请求回查空结果。"""
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        _, _, load_policy = _patch_user_and_policy(monkeypatch, edit_mode=None)
        for _ in range(2):
            resp = client.post("/api/v1/projects")
            assert resp.status_code == 200
            assert "x-org-module-policy" not in resp.headers
        load_policy.assert_called_once()

    def test_expired_entry_is_requeried(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        _, _, load_policy = _patch_user_and_policy(monkeypatch, edit_mode="read_only")
        clock = _Clock()
        monkeypatch.setattr(gate, "_monotonic", clock)
        client.post("/api/v1/projects")
        clock.now += gate.CACHE_TTL_SECONDS - 0.1  # 仍在 TTL 内 → 命中
        client.post("/api/v1/projects")
        assert load_policy.call_count == 1
        clock.now += 1.0  # 越过过期时刻 → 重查
        resp = client.post("/api/v1/projects")
        assert resp.headers["x-org-module-policy"] == "would-block"
        assert load_policy.call_count == 2

    def test_clear_policy_cache_forces_requery(self, client, monkeypatch):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", "shadow")
        _, _, load_policy = _patch_user_and_policy(monkeypatch, edit_mode="read_only")
        client.post("/api/v1/projects")
        gate.clear_policy_cache()
        client.post("/api/v1/projects")
        assert load_policy.call_count == 2


# ════════════════════════════════════════════════════════════════
# 模式归一
# ════════════════════════════════════════════════════════════════
class TestCurrentMode:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("off", "off"),
            ("shadow", "shadow"),
            ("enforce", "enforce"),
            (" SHADOW ", "shadow"),
            ("Enforce", "enforce"),
        ],
    )
    def test_valid_values(self, monkeypatch, value, expected):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", value)
        assert gate.current_mode() == expected

    @pytest.mark.parametrize("value", ["bogus", "", None])
    def test_invalid_values_fall_back_to_shadow(self, monkeypatch, caplog, value):
        monkeypatch.setattr(settings, "ORG_MODULE_POLICY_MODE", value)
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            assert gate.current_mode() == "shadow"
        assert "非法" in caplog.text


# ════════════════════════════════════════════════════════════════
# 路径 → module_key
# ════════════════════════════════════════════════════════════════
class TestResolveModuleKey:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/api/v1/projects", "projects"),
            ("/api/v1/projects/12", "projects"),
            ("/api/v1/projects/12/", "projects"),
            ("/api/v1/supported-villages/export", "supported-villages"),
            ("/api/v1/fund-budgets/3", "funds"),
            ("/api/v1/fund-lifecycle/1", "funds"),
            ("/api/v1/villages/9", "villages"),
            ("/api/v1/households/rollup", "households"),
            ("/api/v1/media/photos/1", "media"),
            ("/api/v1/consumption/records", "consumption"),
            ("/api/v1/system/backup", "system"),
            ("/api/v1/notifications/preferences", "messages"),
            ("/api/v1/data-packages/incremental/export", "data-package"),
            # 前缀边界 / 不映射（含策略管理端点，避免自锁）
            ("/api/v1/projects-extra", None),
            ("/api/v1/org-policies/1", None),
            ("/api/v1/unmapped", None),
            ("/api/v1", None),
            ("", None),
            ("/", None),
        ],
    )
    def test_resolve(self, path, expected):
        assert gate.resolve_module_key(path) == expected


# ════════════════════════════════════════════════════════════════
# 令牌 → 用户
# ════════════════════════════════════════════════════════════════
class TestResolveUser:
    def test_missing_authorization(self):
        assert gate.resolve_user(_scope(), _FakeDB("user")) is None

    def test_non_bearer_scheme(self):
        assert gate.resolve_user(_scope("Basic abc"), _FakeDB("user")) is None

    def test_blank_bearer_token(self):
        assert gate.resolve_user(_scope("Bearer    "), _FakeDB("user")) is None

    def test_invalid_token(self, monkeypatch):
        monkeypatch.setattr("app.core.security.decode_token", lambda token: None)
        assert gate.resolve_user(_scope("Bearer bad"), _FakeDB("user")) is None

    def test_decode_token_raises(self, monkeypatch, caplog):
        def boom(token):
            raise RuntimeError("bad token")

        monkeypatch.setattr("app.core.security.decode_token", boom)
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            assert gate.resolve_user(_scope("Bearer bad"), _FakeDB("user")) is None
        # fail-open 旁路：解析/查库任何异常都只留 WARNING 并放行，绝不抛给写请求
        assert "用户解析异常" in caplog.text

    def test_payload_without_sub(self, monkeypatch):
        monkeypatch.setattr("app.core.security.decode_token", lambda token: {"role": "user"})
        assert gate.resolve_user(_scope("Bearer token"), _FakeDB("user")) is None

    def test_user_found(self, monkeypatch):
        sentinel = SimpleNamespace(organization_id=5)
        monkeypatch.setattr(
            "app.core.security.decode_token", lambda token: {"sub": "admin"}
        )
        assert gate.resolve_user(_scope("Bearer token"), _FakeDB(sentinel)) is sentinel

    def test_user_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.security.decode_token", lambda token: {"sub": "ghost"}
        )
        assert gate.resolve_user(_scope("Bearer token"), _FakeDB(None)) is None


# ════════════════════════════════════════════════════════════════
# 策略查询 / 会话
# ════════════════════════════════════════════════════════════════
class TestPolicyLookup:
    def test_returns_edit_mode_when_policy_exists(self):
        policy = SimpleNamespace(edit_mode="disabled")
        assert gate.load_policy_edit_mode(_FakeDB(policy), 3, "projects") == "disabled"

    def test_returns_none_when_policy_missing(self):
        assert gate.load_policy_edit_mode(_FakeDB(None), 3, "projects") is None

    def test_open_session_uses_lazy_session_local(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: sentinel)
        assert gate._open_session() is sentinel
