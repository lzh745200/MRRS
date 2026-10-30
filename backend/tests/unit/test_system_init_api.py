"""
Tests for init.py — system initialization API.

首次运行门禁（本机 + 空库 + 可选令牌）由 TestFirstRunBootstrap 专门覆盖；
其余用例聚焦初始化下游步骤，autouse 跳过门禁，避免依赖 TestClient 的伪来源地址。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.system.init as init_mod

BASE = "/api/v1/system/init"


@pytest.fixture(autouse=True)
def _skip_first_run_gate(request):
    if "TestFirstRunBootstrap" in request.node.nodeid:
        yield
        return
    with patch.object(init_mod, "_ensure_first_run_bootstrap", lambda *a, **k: None):
        yield


class TestFirstRunBootstrap:
    """匿名首次初始化门禁：本机、空库、未初始化、可选令牌。"""

    def _request(self, host="127.0.0.1", headers=None):
        return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})

    def _db(self, first_value=None):
        db = MagicMock()
        db.query.return_value.first.return_value = first_value
        return db

    def _svc(self, initialized=False):
        svc = MagicMock()
        svc.is_initialized.return_value = initialized
        return svc

    def test_already_initialized_409(self):
        with pytest.raises(HTTPException) as ei:
            init_mod._ensure_first_run_bootstrap(
                self._request(), self._db(None), self._svc(initialized=True)
            )
        assert ei.value.status_code == 409
        assert "已完成初始化" in ei.value.detail

    def test_existing_user_or_org_409(self):
        with pytest.raises(HTTPException) as ei:
            init_mod._ensure_first_run_bootstrap(
                self._request(), self._db(first_value=1), self._svc()
            )
        assert ei.value.status_code == 409
        assert "已存在用户或组织" in ei.value.detail

    def test_non_loopback_403(self):
        with pytest.raises(HTTPException) as ei:
            init_mod._ensure_first_run_bootstrap(
                self._request(host="10.0.0.8"), self._db(None), self._svc()
            )
        assert ei.value.status_code == 403
        assert "仅允许在本机操作" in ei.value.detail

    def test_invalid_bootstrap_token_403(self, monkeypatch):
        monkeypatch.setenv("INIT_BOOTSTRAP_TOKEN", "expected-token")
        with pytest.raises(HTTPException) as ei:
            init_mod._ensure_first_run_bootstrap(
                self._request(headers={"X-Init-Token": "wrong"}),
                self._db(None),
                self._svc(),
            )
        assert ei.value.status_code == 403
        assert "令牌无效" in ei.value.detail

    def test_valid_bootstrap_token_passes(self, monkeypatch):
        monkeypatch.setenv("INIT_BOOTSTRAP_TOKEN", "expected-token")
        result = init_mod._ensure_first_run_bootstrap(
            self._request(headers={"X-Init-Token": "expected-token"}),
            self._db(None),
            self._svc(),
        )
        assert result is None

    def test_no_bootstrap_token_configured_passes(self, monkeypatch):
        monkeypatch.delenv("INIT_BOOTSTRAP_TOKEN", raising=False)
        result = init_mod._ensure_first_run_bootstrap(
            self._request(), self._db(None), self._svc()
        )
        assert result is None

    def test_loopback_helper_rejects_missing_and_malformed_host(self):
        assert init_mod._is_loopback_request(SimpleNamespace(client=None)) is False
        assert (
            init_mod._is_loopback_request(
                self._request(host="not-an-ip")
            )
            is False
        )


class TestGetInitChecklist:
    def test_returns_checklist(self, client):
        resp = client.get(f"{BASE}/checklist")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["checklist"]) >= 5


class TestCheckInitStatus:
    def test_not_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = False
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is False
        assert "version" in data

    def test_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = True
        mock_svc.get.side_effect = lambda key, default=None: {
            "organization_name": "测试单位",
                "organization_code": "520000",
            "system_name": "测试系统",
            "init_timestamp": "2024-01-01T00:00:00",
        }.get(key, default)
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is True
        assert data["organization_name"] == "测试单位"

    def test_exception_fallback(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is False
        # W1-T8：内部异常细节不出站
        assert data["error"] == "状态检查失败，请查看服务端日志"


class TestInitializeSystem:
    def test_success(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = False
        with (
            patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc),
            patch("app.core.security.get_password_hash", return_value="hashed"),
        ):
            resp = client.post(
                f"{BASE}/initialize",
                json={
                    "organization_name": "测试单位",
                "organization_code": "520000",
                    "admin_username": "admin",
                    "admin_password": "Str0ng!Passw0rd",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_already_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = True
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.post(
                f"{BASE}/initialize",
                json={
                    "organization_name": "测试单位",
                "organization_code": "520000",
                    "admin_username": "admin",
                    "admin_password": "Str0ng!Passw0rd",
                },
            )
        assert resp.status_code == 400
        assert "已" in resp.json()["detail"]


class TestResetInitialization:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/reset", json={"confirm": "RESET", "admin_password": "x"})
        assert resp.status_code == 401

    def test_requires_confirm_string(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/reset", json={"confirm": "wrong", "admin_password": "x"}
        )
        assert resp.status_code == 400
        assert "RESET" in resp.json()["detail"]

    def test_success(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        with (
            patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc),
            patch("app.core.security.verify_password", return_value=True),
        ):
            resp = client_with_mocked_auth.post(
                f"{BASE}/reset",
                json={"confirm": "RESET", "admin_password": "Str0ng!Pass"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_svc.set.assert_any_call("initialized", "false")
