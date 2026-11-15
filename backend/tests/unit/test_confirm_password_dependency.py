"""R63：高风险操作二次确认（X-Confirm-Password）依赖。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.v1.deps import require_confirm_password, verify_confirm_password_value
from app.core.config import settings
from app.core.security import get_password_hash


@pytest.fixture
def request_obj():
    return SimpleNamespace(url=SimpleNamespace(path="/api/v1/users/7"))


@pytest.fixture
def user():
    return SimpleNamespace(id=7, hashed_password=get_password_hash("Correct#123"))


@pytest.fixture(autouse=True)
def _force_production(monkeypatch):
    monkeypatch.setattr(settings, "CONFIRM_PASSWORD_ENFORCED", True, raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)


class TestVerifyConfirmPassword:
    def test_skips_when_disabled(self, monkeypatch, request_obj, user):
        monkeypatch.setattr(settings, "CONFIRM_PASSWORD_ENFORCED", False, raising=False)
        assert verify_confirm_password_value(request_obj, "", user) is None

    def test_skips_in_test_environment(self, monkeypatch, request_obj, user):
        monkeypatch.setattr(settings, "ENVIRONMENT", "testing", raising=False)
        assert verify_confirm_password_value(request_obj, "", user) is None

    def test_missing_password_requires_reauth(self, request_obj, user):
        with pytest.raises(HTTPException) as exc:
            verify_confirm_password_value(request_obj, "", user)
        assert exc.value.status_code == 428
        assert exc.value.detail == "REAUTH_REQUIRED"

    def test_rate_limited(self, request_obj, user):
        with patch(
            "app.services.resource_limiter.check_rate_limit", return_value=False
        ):
            with pytest.raises(HTTPException) as exc:
                verify_confirm_password_value(request_obj, "Correct#123", user)
        assert exc.value.status_code == 429

    def test_rate_limit_key_uses_user_and_path(self, request_obj, user):
        with patch(
            "app.services.resource_limiter.check_rate_limit", return_value=True
        ) as limit:
            verify_confirm_password_value(request_obj, "Correct#123", user)
        assert limit.call_args.kwargs["key"] == "confirm_pwd:7:/api/v1/users/7"
        assert limit.call_args.kwargs["limit"] == 5
        assert limit.call_args.kwargs["window"] == 60

    def test_wrong_password(self, request_obj, user):
        with patch("app.services.resource_limiter.check_rate_limit", return_value=True):
            with pytest.raises(HTTPException) as exc:
                verify_confirm_password_value(request_obj, "Wrong#123", user)
        assert exc.value.status_code == 400
        assert "密码不正确" in exc.value.detail

    def test_correct_password_passes(self, request_obj, user):
        with patch("app.services.resource_limiter.check_rate_limit", return_value=True):
            assert verify_confirm_password_value(request_obj, "Correct#123", user) is None

    def test_missing_path_is_tolerated(self, user):
        bare_request = SimpleNamespace(url=None)
        with patch("app.services.resource_limiter.check_rate_limit", return_value=True):
            assert verify_confirm_password_value(bare_request, "Correct#123", user) is None


class TestRequireConfirmPasswordDependency:
    def test_delegates(self, request_obj, user):
        with patch(
            "app.api.v1.deps.verify_confirm_password_value"
        ) as verify:
            require_confirm_password(
                request=request_obj,
                confirm_password="Correct#123",
                current_user=user,
            )
        verify.assert_called_once_with(request_obj, "Correct#123", user)

    def test_missing_password_propagates(self, request_obj, user):
        with pytest.raises(HTTPException) as exc:
            require_confirm_password(
                request=request_obj, confirm_password="", current_user=user
            )
        assert exc.value.status_code == 428


def test_permission_package_confirm_requires_password(monkeypatch, request_obj, user):
    """回归：权限包确认也必须在进入文件处理前触发二次确认。"""
    from app.api.v1.permission_package import confirm_import_permission_package
    from app.schemas.permission_package import PermissionPackageConfirmRequest

    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    with patch(
        "app.api.v1.permission_package._assert_package_import_principal",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            confirm_import_permission_package(
                file_name="x.zip",
                body=PermissionPackageConfirmRequest(),
                current_user=user,
                db=SimpleNamespace(),
                request=request_obj,
                force=False,
                confirm_password="",
            )
    assert exc.value.status_code == 428
