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
            "/api/v1/machine-code/reset-password-with-machine-code",
            json={
                "username": username,
                "machine_code": "MC001",
                "verification_code": "VC001",
            },
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
            "/api/v1/machine-code/reset-password-with-machine-code",
            json={
                "username": "testuser",
                "machine_code": "MC001",
                "verification_code": "VC001",
            },
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


class TestFactoryAdminRecovery:
    """管理员出厂恢复端点（ADR-0008 扩展 2026-08-30）的安全边界。

    仅"从未激活"的管理员账号可恢复（must_change_password=True 且
    login_attempts 无成功登录记录）；重置目标为文档化出厂密码。
    """

    URL = "/api/v1/machine-code/recover-admin-factory-password"

    def _post(self, client_admin, username="admin"):
        return client_admin.post(
            self.URL,
            json={
                "username": username,
                "machine_code": "MC001",
                "verification_code": "VC001",
            },
        )

    @staticmethod
    def _admin_user(must_change=True):
        u = MagicMock()
        u.id = 1
        u.username = "admin"
        u.role = "admin"
        u.is_superuser = True
        u.must_change_password = must_change
        return u

    def test_never_activated_admin_recovers_to_factory_password(self, client_admin, mock_db):
        """从未激活的管理员：重置为出厂密码 + 清除锁定 + 审计留痕。"""
        user = self._admin_user()
        mock_db.query.return_value.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True), \
             patch("app.api.v1.machine_code.get_password_hash", return_value="$2b$12$hashed"), \
             patch("app.api.v1.machine_code.safe_commit") as safe_commit_mock, \
             patch("app.services.lockout_service.get_lockout_service") as gls, \
             patch("app.api.v1.machine_code.write_work_log") as wwl:
            resp = self._post(client_admin)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["factory_password"] == "Admin@2026"
        assert user.hashed_password == "$2b$12$hashed"
        assert user.must_change_password is True
        assert safe_commit_mock.called, "必须经 safe_commit 提交"
        assert gls.return_value.clear.called, "必须清除锁定状态"
        assert wwl.called, "必须 write_work_log 留痕"

    def test_activated_admin_without_must_change_rejected(self, client_admin, mock_db):
        """已激活（完成过首登改密）的管理员恒 403，防静默接管。"""
        user = self._admin_user(must_change=False)
        mock_db.query.return_value.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin)

        assert resp.status_code == 403

    def test_admin_with_successful_login_history_rejected(self, client_admin, mock_db):
        """存在成功登录记录即视为已激活，恒 403。"""
        user = self._admin_user(must_change=True)
        mock_db.query.return_value.first.return_value = user
        mock_db.query.return_value.count.return_value = 1

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin)

        assert resp.status_code == 403

    def test_non_admin_user_directed_to_normal_channel(self, client_admin, mock_db):
        """普通账号不可用本端点，指向既有自助重置通道。"""
        user = MagicMock()
        user.role = "user"
        user.is_superuser = False
        user.must_change_password = True
        mock_db.query.return_value.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin, "zhangsan")

        assert resp.status_code == 400
        assert "重置密码" in resp.json()["detail"]

    def test_unknown_user_404(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin, "ghost")

        assert resp.status_code == 404

    def test_machine_code_mismatch_rejected(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = self._admin_user()

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService",
                   return_value=_make_service(machine_code="OTHER")), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin)

        assert resp.status_code == 400

    def test_bad_verification_code_rejected(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = self._admin_user()

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService",
                   return_value=_make_service(verify_ok=False)), \
             patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            resp = self._post(client_admin)

        assert resp.status_code == 400

    def test_remote_request_rejected(self, client_admin):
        """非 loopback 来源直接拒绝（TestClient 默认 host 非本机）。"""
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)), \
             patch("app.api.v1.machine_code.MachineCodeService", return_value=_make_service()):
            resp = self._post(client_admin)

        assert resp.status_code == 403

    def test_rate_limited_429(self, client_admin):
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=False)):
            resp = self._post(client_admin)

        assert resp.status_code == 429
