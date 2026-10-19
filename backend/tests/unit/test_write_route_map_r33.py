# -*- coding: utf-8 -*-
"""R33：写接口 → 模块映射表（授权守卫的前置件）。

覆盖点：
- 写方法判定（大小写、非写方法）；
- 豁免的**路径边界**语义（`/auth/login` 不得顺带豁免 `/auth/login-audit`）；
- 最长前缀优先（单复数并存时不得被短规则抢走）；
- 未归属清单的筛选（GET 不算、豁免不算、缺 methods/path 的路由跳过）。
"""

from types import SimpleNamespace

from app.core.write_route_map import (
    MODULE_RULES,
    WRITE_METHODS,
    is_exempt,
    is_write_method,
    resolve_module,
    unmapped_write_routes,
)


class TestWriteMethod:
    def test_all_write_methods(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert is_write_method(method) is True
        assert WRITE_METHODS == {"POST", "PUT", "PATCH", "DELETE"}

    def test_read_methods_are_not_write(self):
        for method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            assert is_write_method(method) is False

    def test_case_insensitive(self):
        assert is_write_method("post") is True
        assert is_write_method("Delete") is True


class TestIsExempt:
    def test_exact_path(self):
        assert is_exempt("/api/v1/auth/login") is True

    def test_sub_path(self):
        assert is_exempt("/api/v1/auth/login/refresh") is True

    def test_trailing_slash_normalized(self):
        assert is_exempt("/api/v1/feedback/") is True

    def test_boundary_not_prefix_confused(self):
        """`/auth/login` 不得豁免 `/auth/login-audit` 这类无关路径。"""
        assert is_exempt("/api/v1/auth/login-audit") is False

    def test_ordinary_path_not_exempt(self):
        assert is_exempt("/api/v1/projects/1") is False

    def test_root(self):
        assert is_exempt("/") is False


class TestResolveModule:
    def test_exact_match(self):
        assert resolve_module("/api/v1/projects") == "projects"

    def test_sub_path_match(self):
        assert resolve_module("/api/v1/projects/12/edit") == "projects"

    def test_trailing_slash(self):
        assert resolve_module("/api/v1/projects/") == "projects"

    def test_longest_prefix_wins(self):
        """`/auth/users` 必须命中 users-orgs，而不是被更短的规则抢走。"""
        assert resolve_module("/api/v1/auth/users/5") == "users-orgs"
        assert resolve_module("/api/v1/auth/rbac/roles") == "roles"

    def test_plural_specific_rule(self):
        """实际路由是复数（pairings/donations），必须命中对应模块。"""
        assert resolve_module("/api/v1/pairings") == "pairing"
        assert resolve_module("/api/v1/donations/3") == "donation"

    def test_unknown_path_returns_none(self):
        assert resolve_module("/api/v1/not-a-real-module/x") is None

    def test_boundary_not_prefix_confused(self):
        assert resolve_module("/api/v1/projectszzz") is None


class TestUnmappedRoutes:
    def test_filters_and_reports(self):
        routes = [
            SimpleNamespace(methods={"GET"}, path="/api/v1/projects"),
            SimpleNamespace(methods={"POST"}, path="/api/v1/unknown/x"),
            SimpleNamespace(methods={"PUT", "GET"}, path="/api/v1/projects/1"),
            SimpleNamespace(methods={"DELETE"}, path="/api/v1/feedback/1"),
            SimpleNamespace(methods=None, path="/api/v1/whatever"),
            SimpleNamespace(methods={"POST"}, path=None),
        ]
        rows = unmapped_write_routes(routes)
        assert rows == [(["POST"], "/api/v1/unknown/x")]

    def test_empty_when_all_mapped(self):
        routes = [SimpleNamespace(methods={"POST"}, path="/api/v1/funds")]
        assert unmapped_write_routes(routes) == []


class TestRuleTable:
    def test_rules_are_unique_prefixes(self):
        prefixes = [p for p, _m in MODULE_RULES]
        assert len(prefixes) == len(set(prefixes)), "规则前缀不得重复"

    def test_all_rules_have_module_key(self):
        for prefix, module in MODULE_RULES:
            assert prefix.startswith("/api/v1/") or prefix.startswith("/")
            assert module and isinstance(module, str)
