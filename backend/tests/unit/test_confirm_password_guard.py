"""P1：高风险操作二次确认依赖。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.deps import verify_confirm_password_value
from app.core.security import get_password_hash


def _request(path: str = "/api/v1/users/1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "PUT",
            "path": path,
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


@pytest.fixture
def production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "CONFIRM_PASSWORD_ENFORCED", True)


def test_missing_password_returns_428(production):
    user = SimpleNamespace(id=901, hashed_password=get_password_hash("Correct#12345"))
    with pytest.raises(HTTPException) as exc:
        verify_confirm_password_value(_request(), "", user)
    assert exc.value.status_code == 428
    assert exc.value.detail == "REAUTH_REQUIRED"


def test_wrong_password_returns_400(production):
    user = SimpleNamespace(id=902, hashed_password=get_password_hash("Correct#12345"))
    with pytest.raises(HTTPException) as exc:
        verify_confirm_password_value(_request(), "wrong", user)
    assert exc.value.status_code == 400
    assert "二次确认失败" in exc.value.detail


def test_correct_password_passes(production):
    user = SimpleNamespace(id=903, hashed_password=get_password_hash("Correct#12345"))
    assert verify_confirm_password_value(_request(), "Correct#12345", user) is None


def test_test_environment_is_noop(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    user = SimpleNamespace(id=904, hashed_password=get_password_hash("Correct#12345"))
    assert verify_confirm_password_value(_request(), "", user) is None
