"""Batch coverage tests for core modules."""
import pytest
from unittest.mock import MagicMock


class TestResponseModule:
    def test_ok_list_defaults(self):
        from app.core.response import ok_list
        r = ok_list(items=[], total=0)
        assert r["code"] == 200
        assert r["data"]["items"] == []
        assert r["data"]["total"] == 0

    def test_ok_list_custom(self):
        from app.core.response import ok_list
        r = ok_list(items=[{"a": 1}], total=50, page=3, page_size=10)
        assert r["data"]["total"] == 50

    def test_success_response(self):
        from app.core.response import success_response
        r = success_response(data={"k": "v"})
        assert r["code"] == 200
        assert r["data"] == {"k": "v"}

    def test_error_response(self):
        from app.core.response import error_response
        r = error_response(code=400, message="err", errors=["e1"], detail="d")
        assert r["code"] == 400
        assert r["success"] is False


    def test_not_found(self):
        from app.core.response import not_found_response
        assert not_found_response()["code"] == 404


    def test_forbidden(self):
        from app.core.response import forbidden_response
        assert forbidden_response()["code"] == 403

    def test_server_error(self):
        from app.core.response import server_error_response
        assert server_error_response()["code"] == 500

    def test_paginated_response(self):
        from app.core.response import paginated_response, PaginationMeta
        pm = PaginationMeta(page=2, page_size=10, total=25)
        r = paginated_response(data=[1, 2], pagination=pm)
        assert "meta" in r

    def test_pagination_meta_zero(self):
        from app.core.response import PaginationMeta
        pm = PaginationMeta.from_pagination(1, 0, 10)
        assert pm.total_pages == 0



class TestPasswordPolicy:
    def test_empty(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("")
        assert not v

    def test_too_short(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("Ab1!")
        assert not v

    def test_no_upper(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("abcdefgh1!klm")
        assert not v

    def test_no_lower(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("ABCDEFGH1!KLM")
        assert not v

    def test_no_digit(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("Abcdefgh!klm")
        assert not v

    def test_no_special(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("Abcdefgh1klm")
        assert not v

    def test_too_long(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("A" * 21 + "b1!")
        assert not v

    def test_valid(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("MyP@ssw0rd2024!")
        assert v

    def test_weak_prefix_admin(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate("adminXyz123!@#")
        assert not v

    def test_validate_username_empty(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate_username("")
        assert not v

    def test_validate_username_short(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate_username("ab")
        assert not v

    def test_validate_username_valid(self):
        from app.core.security import PasswordPolicy
        v, _ = PasswordPolicy.validate_username("test_user")
        assert v

    def test_hash_and_verify(self):
        from app.core.security import get_password_hash, verify_password
        h = get_password_hash("secret123")
        assert verify_password("secret123", h)
        assert not verify_password("wrong", h)


class TestAppErrors:
    def test_not_found_returns(self):
        from app.core.errors import AppError
        e = AppError.not_found("TestResource")
        assert hasattr(e, 'status_code')
        assert e.status_code == 404

    def test_forbidden_returns(self):
        from app.core.errors import AppError
        e = AppError.forbidden("no access")
        assert hasattr(e, 'status_code')
        assert e.status_code == 403

    def test_bad_request_returns(self):
        from app.core.errors import AppError
        e = AppError.bad_request("bad")
        assert hasattr(e, 'status_code')
        assert e.status_code == 400


class TestExceptions:
    def test_not_found(self):
        from app.core.exceptions import NotFoundException
        e = NotFoundException("not found")
        assert e.status_code == 404

    def test_authentication(self):
        from app.core.exceptions import AuthenticationException
        e = AuthenticationException("unauth")
        assert e.status_code == 401


class TestDataPermission:
    def test_is_admin_superuser(self):
        from app.core.data_permission import is_admin
        u = MagicMock(is_superuser=True, role="viewer")
        assert is_admin(u)

    def test_is_admin_role(self):
        from app.core.data_permission import is_admin
        u = MagicMock(is_superuser=False, role="admin")
        assert is_admin(u)

    def test_is_admin_normal(self):
        from app.core.data_permission import is_admin
        u = MagicMock(is_superuser=False, role="viewer")
        assert not is_admin(u)

    def test_require_admin(self):
        from app.core.data_permission import require_data_permission
        u = MagicMock(is_superuser=True)
        assert require_data_permission(u, organization_id=1, created_by=99) is True

    def test_require_denied_no_db(self):
        from app.core.data_permission import require_data_permission
        from fastapi import HTTPException
        u = MagicMock(is_superuser=False, role="viewer", id=1)
        with pytest.raises(HTTPException) as e:
            require_data_permission(u, organization_id=99, created_by=99, db=None)
        assert e.value.status_code == 403

    def test_filter_by_data_scope(self):
        from app.core.data_permission import filter_by_data_scope
        q = MagicMock()
        u = MagicMock(is_superuser=True)
        assert filter_by_data_scope(q, MagicMock(), u) == q


class TestConfig:
    def test_settings(self):
        from app.core.config import settings
        assert hasattr(settings, 'APP_NAME')
        assert hasattr(settings, 'SECRET_KEY')

    def test_database_url(self):
        from app.core.config import settings
        assert hasattr(settings, 'DATABASE_URL')


class TestMiddleware:
    def test_security_headers(self):
        from app.core.security import SecurityHeadersMiddleware
        mw = SecurityHeadersMiddleware(MagicMock())
        assert mw.app is not None





class TestCache:
    def test_exists(self):
        from app.core.cache import cache_manager
        assert cache_manager is not None


