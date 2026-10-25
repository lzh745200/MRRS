"""Tests for app/core/constants.py — 目标 100% 覆盖。"""
from app.core.constants import (
    ADMIN_ROLES,
    ALL_ROLES,
    ANALYTICS_CACHE_PREFIX,
    DEFAULT_PAGE_SIZE,
    HTTP_CLIENT_CLOSED_REQUEST,
    MAX_PAGE_SIZE,
    ROLE_ADMIN,
    ROLE_APPROVAL_LEADER,
    ROLE_MANAGER,
    ROLE_OPERATOR,
    ROLE_SUPER_ADMIN,
    ROLE_VIEWER,
    UserRole,
)


class TestConstants:
    def test_analytics_cache_prefix(self):
        assert ANALYTICS_CACHE_PREFIX == "analytics:"

    def test_page_size_constants(self):
        assert DEFAULT_PAGE_SIZE == 20
        assert MAX_PAGE_SIZE == 200

    def test_http_client_closed_request(self):
        assert HTTP_CLIENT_CLOSED_REQUEST == 499

    def test_role_constants(self):
        assert ROLE_SUPER_ADMIN == "super_admin"
        assert ROLE_ADMIN == "admin"
        assert ROLE_APPROVAL_LEADER == "approval_leader"
        assert ROLE_MANAGER == "manager"
        assert ROLE_OPERATOR == "operator"
        assert ROLE_VIEWER == "viewer"

    def test_admin_roles(self):
        assert ADMIN_ROLES == {"super_admin", "admin"}

    def test_all_roles(self):
        expected = [
            "super_admin", "admin", "user", "viewer",
        ]
        assert ALL_ROLES == expected


class TestUserRole:
    def test_attributes_match_constants(self):
        assert UserRole.SUPER_ADMIN == ROLE_SUPER_ADMIN
        assert UserRole.ADMIN == ROLE_ADMIN
        assert UserRole.APPROVAL_LEADER == ROLE_APPROVAL_LEADER
        assert UserRole.MANAGER == ROLE_MANAGER
        assert UserRole.OPERATOR == ROLE_OPERATOR
        assert UserRole.VIEWER == ROLE_VIEWER
