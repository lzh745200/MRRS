"""v1.12.9 覆盖率补口：app/api/v1/auth/two_factor.py（W15 深审 #5/#6）。

覆盖行（当前代码行号）：
- 67-72 `_enforce_two_factor_rate_limit`：超限 → 429（不再是静默放行）；
  verify / disable 两个动作独立计数，且限流拒绝时绝不触碰 TwoFactorService；
- 86-87 `_verify_second_factor` 动态码校验抛异常 → 记 warning 并视为失败（fail-closed）；
- 95-96 密码兜底校验抛异常 → 同样视为失败，绝不因异常放行关闭 2FA。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.api.v1.auth.two_factor import DisableTwoFactorRequest, _verify_second_factor

SVC_PATH = "app.services.two_factor_service.TwoFactorService"


@pytest.fixture
def tf_user():
    user = MagicMock(name="User")
    user.id = 11
    user.username = "tf_user"
    user.hashed_password = "hashed-pwd"
    return user


@pytest.fixture
def client(tf_user):
    """最小可用的 2FA 路由应用（依赖覆盖，不触碰真实鉴权）。"""
    app = FastAPI()
    app.dependency_overrides[deps.get_current_active_user] = lambda: tf_user
    app.dependency_overrides[deps.get_db] = lambda: MagicMock(name="Session")

    from app.api.v1.auth.two_factor import router

    app.include_router(router)
    return TestClient(app)


class TestTwoFactorRateLimit:
    """按用户维度限流，verify / disable 计数键互不挤占。"""

    def test_verify_429_when_limit_exhausted(self, client):
        limiter = AsyncMock(return_value=False)
        with patch("app.api.v1.auth.two_factor.check_rate_limit", new=limiter), patch(
            f"{SVC_PATH}.verify_and_enable"
        ) as m_verify:
            resp = client.post("/two-factor/verify", json={"token": "123456"})
        assert resp.status_code == 429
        assert "过于频繁" in resp.json()["detail"]
        m_verify.assert_not_called()

    def test_disable_429_when_limit_exhausted(self, client):
        limiter = AsyncMock(return_value=False)
        with patch("app.api.v1.auth.two_factor.check_rate_limit", new=limiter), patch(
            f"{SVC_PATH}.disable_two_factor"
        ) as m_disable:
            resp = client.post("/two-factor/disable", json={"code": "123456"})
        assert resp.status_code == 429
        m_disable.assert_not_called()

    def test_rate_limit_key_and_window(self, client, tf_user):
        limiter = AsyncMock(return_value=True)
        with patch("app.api.v1.auth.two_factor.check_rate_limit", new=limiter), patch(
            f"{SVC_PATH}.verify_and_enable", return_value=True
        ):
            resp = client.post("/two-factor/verify", json={"token": "123456"})
        assert resp.status_code == 200
        kwargs = limiter.await_args.kwargs
        assert kwargs["key"] == f"two_factor:verify:{tf_user.id}"
        assert kwargs["limit"] == 10
        assert kwargs["window"] == 60


class TestVerifySecondFactorFailClosed:
    """关闭 2FA 前的二次因子校验：任一通道异常都必须判为失败。"""

    def test_code_path_exception_returns_false(self):
        user = MagicMock(name="User")
        user.id = 3
        with patch(f"{SVC_PATH}.verify_login", side_effect=RuntimeError("totp backend down")):
            result = _verify_second_factor(MagicMock(), user, DisableTwoFactorRequest(code="123456"))
        assert result is False

    def test_code_exception_then_password_success(self):
        user = MagicMock(name="User")
        user.id = 4
        user.hashed_password = "hashed"
        with patch(f"{SVC_PATH}.verify_login", side_effect=RuntimeError("boom")), patch(
            "app.api.v1.auth.two_factor.verify_password", return_value=True
        ):
            result = _verify_second_factor(
                MagicMock(), user, DisableTwoFactorRequest(code="123456", password="pw")
            )
        assert result is True

    def test_password_path_exception_returns_false(self):
        user = MagicMock(name="User")
        user.id = 5
        user.hashed_password = "hashed"
        with patch(
            "app.api.v1.auth.two_factor.verify_password", side_effect=RuntimeError("bcrypt error")
        ):
            result = _verify_second_factor(MagicMock(), user, DisableTwoFactorRequest(password="pw"))
        assert result is False

    def test_code_exception_without_password_rejected_via_endpoint(self, client):
        with patch(f"{SVC_PATH}.verify_login", side_effect=RuntimeError("boom")), patch(
            f"{SVC_PATH}.disable_two_factor"
        ) as m_disable:
            resp = client.post("/two-factor/disable", json={"code": "123456"})
        assert resp.status_code == 401
        m_disable.assert_not_called()

    def test_password_exception_rejected_via_endpoint(self, client):
        with patch(
            "app.api.v1.auth.two_factor.verify_password", side_effect=RuntimeError("bcrypt error")
        ), patch(f"{SVC_PATH}.disable_two_factor") as m_disable:
            resp = client.post("/two-factor/disable", json={"password": "pw"})
        assert resp.status_code == 401
        m_disable.assert_not_called()
