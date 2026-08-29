"""W1-T1 安全回归：公开密码重置链路（工单 .scratch/w1-security-redline/001）

覆盖三项修复的验收标准：
1. 限流真实生效（check_rate_limit 参数顺序历史缺陷）
2. /get-machine-code 对非 loopback 客户端隐藏校验码
3. 重置端点拒绝管理员账号（防提权）+ 审计留痕
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import security as core_security
from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    """与既有 machine-code 测试保持一致：关闭驼峰转换中间件干扰。"""
    with patch("app.middleware.camel_to_snake._convert_keys",
               side_effect=lambda obj, converter: (obj, False)):
        yield


@pytest.fixture
def mock_db():
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.first.return_value = None
    db.query.return_value = q
    return db


@pytest.fixture
def admin_user_mock():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    return u


@pytest.fixture
def client_admin(mock_db, admin_user_mock):
    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_user_mock
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


@pytest.fixture(autouse=True)
def _isolate_rate_store():
    """隔离内存限流存储，避免用例间污染。"""
    core_security._rate_limit_store.clear()
    yield
    core_security._rate_limit_store.clear()


class TestRateLimitSignature:
    """check_rate_limit 签名收紧：key 为首参，缺 key/request 必须 fail-closed。"""

    @staticmethod
    def _req():
        from types import SimpleNamespace

        return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    def test_positional_string_binds_to_key(self):
        """位置传参字符串必须绑定到 key（历史 bug：绑到 request 形参静默放行）。"""
        ok = asyncio.run(
            core_security.check_rate_limit("w1t1-key", request=self._req(), limit=1, window=60)
        )
        assert ok is True
        blocked = asyncio.run(
            core_security.check_rate_limit("w1t1-key", request=self._req(), limit=1, window=60)
        )
        assert blocked is False

    def test_missing_key_fails_closed(self):
        """无 key 时必须抛错拒绝，而非返回 True 放行。"""
        with pytest.raises(ValueError):
            asyncio.run(core_security.check_rate_limit())

    def test_missing_request_fails_closed(self):
        """W1-T2：缺 request 时必须抛错拒绝（2026-08-29 收紧）。"""
        with pytest.raises(ValueError):
            asyncio.run(core_security.check_rate_limit(key="w1t1-noreq", limit=5, window=60))

    def test_keyword_key_still_works(self):
        ok = asyncio.run(
            core_security.check_rate_limit(key="w1t1-kw", request=self._req(), limit=5, window=60)
        )
        assert ok is True


class TestLoopbackDetection:
    """loopback 判定基于 request.client.host，不受 X-Forwarded-For 伪造影响。"""

    def test_loopback_hosts_detected(self):
        from app.api.v1.machine_code import _client_is_loopback

        req = MagicMock()
        for host in ("127.0.0.1", "::1", "localhost"):
            req.client.host = host
            assert _client_is_loopback(req) is True, host

    def test_remote_host_rejected_even_with_spoofed_xff(self):
        from app.api.v1.machine_code import _client_is_loopback

        req = MagicMock()
        req.client.host = "203.0.113.9"
        req.headers = {"X-Forwarded-For": "127.0.0.1"}
        assert _client_is_loopback(req) is False

    def test_missing_client_treated_as_remote(self):
        from app.api.v1.machine_code import _client_is_loopback

        req = MagicMock()
        req.client = None
        assert _client_is_loopback(req) is False


class TestGetMachineCodeVerificationCodeHidden:
    """非 loopback 客户端不得获取校验码。"""

    def test_verification_code_hidden_for_remote_client(self, client_admin):
        svc = MagicMock()
        svc.get_machine_code.return_value = "MACHINE001"
        svc.generate_verification_code.return_value = "VERIFY001"
        svc.get_machine_info.return_value = {"os": "windows"}
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/get-machine-code")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["machine_code"] == "MACHINE001"
        assert "verification_code" not in body

    def test_verification_code_present_for_loopback(self, client_admin):
        svc = MagicMock()
        svc.get_machine_code.return_value = "MACHINE001"
        svc.generate_verification_code.return_value = "VERIFY001"
        svc.get_machine_info.return_value = {"os": "windows"}
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            with patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
                resp = client_admin.get("/api/v1/machine-code/get-machine-code")
        assert resp.json()["data"]["verification_code"] == "VERIFY001"


def _make_service(machine_code="MC001", verify_ok=True):
    svc = MagicMock()
    svc.get_machine_code.return_value = machine_code
    svc.verify_machine_code.return_value = verify_ok
    return svc


class TestResetRejectsPrivilegedAccounts:
    """管理员/superuser 账号禁止走公开自助重置（防静默提权）。"""

    def _post(self, client_admin, username):
        return client_admin.post(
            "/api/v1/machine-code/reset-password-with-machine-code"
            f"?username={username}&machine_code=MC001&verification_code=VC001",
        )

    def test_admin_role_rejected(self, client_admin, mock_db):
        user = MagicMock()
        user.role = "admin"
        user.is_superuser = False
        mock_db.query.return_value.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin, "admin")
        assert resp.status_code == 403
        assert "管理员" in resp.json()["detail"]

    def test_superuser_flag_rejected(self, client_admin, mock_db):
        user = MagicMock()
        user.role = "user"
        user.is_superuser = True
        mock_db.query.return_value.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin, "root")
        assert resp.status_code == 403

    def test_remote_request_rejected(self, client_admin):
        """非 loopback 来源直接拒绝（默认 TestClient host=testclient 即非本机）。"""
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()):
            resp = self._post(client_admin, "someone")
        assert resp.status_code == 403


class TestResetAuditTrail:
    """重置成功必须写审计日志；破窗语义仅限 loopback 保留。"""

    @staticmethod
    def _setup(mock_db):
        user = MagicMock()
        user.id = 7
        user.username = "testuser"
        user.role = "user"
        user.is_superuser = False
        mock_db.query.return_value.first.return_value = user
        return user

    def _post(self, client_admin):
        return client_admin.post(
            "/api/v1/machine-code/reset-password-with-machine-code"
            "?username=testuser&machine_code=MC001&verification_code=VC001",
        )

    def test_success_writes_audit_log(self, client_admin, mock_db):
        self._setup(mock_db)
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService",
                   return_value=_make_service(verify_ok=True)), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True), \
             patch("app.core.security.generate_password", return_value="NewPwd123!"), \
             patch("app.api.v1.machine_code.write_work_log") as wwl:
            resp = self._post(client_admin)
        assert resp.status_code == 200
        assert wwl.called, "重置成功后必须调用 write_work_log 留痕"

    def test_reset_still_returns_password_over_loopback(self, client_admin, mock_db):
        """破窗恢复语义保留：仅限 loopback 的本次响应中返回一次性密码。"""
        self._setup(mock_db)
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService",
                   return_value=_make_service(verify_ok=True)), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True), \
             patch("app.core.security.generate_password", return_value="NewPwd123!"):
            resp = self._post(client_admin)
        assert resp.status_code == 200
        assert resp.json()["data"]["new_password"] == "NewPwd123!"
