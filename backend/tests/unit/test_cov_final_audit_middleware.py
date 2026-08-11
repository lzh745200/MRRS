"""覆盖 app.core.audit_middleware 缺口：JWT 解析成功路径（含 sub 非整数的兜底）。"""
from types import SimpleNamespace

import jwt

from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings


def _make_request(token: str):
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"})


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class TestExtractUserIdentity:
    """_extract_user_identity 行 69-74：decode 成功后的 sub/username 提取。"""

    def test_valid_token_with_int_sub(self):
        token = _encode({"sub": "123", "username": "alice"})
        user_id, username = AuditMiddleware._extract_user_identity(_make_request(token))
        assert user_id == 123
        assert username == "alice"

    def test_valid_token_with_non_int_sub_falls_back_to_none(self):
        # sub 无法转为 int → (None, username)，覆盖 except (TypeError, ValueError) 分支
        token = _encode({"sub": "not-an-int"})
        user_id, username = AuditMiddleware._extract_user_identity(_make_request(token))
        assert user_id is None
        assert username == "not-an-int"

    def test_no_bearer_header_returns_none_pair(self):
        request = SimpleNamespace(headers={})
        assert AuditMiddleware._extract_user_identity(request) == (None, None)
