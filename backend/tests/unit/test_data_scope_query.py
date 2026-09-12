# -*- coding: utf-8 -*-
"""B1（架构评估 2026-09-12）：服务层统一数据域入口 scoped_query / scoped_filter / scoped_count。

语义必须与 core.data_permission.filter_by_data_scope 完全一致：
- super_admin / is_superuser → 不过滤（ALL）
- admin（部门级）→ 仅本组织（S2 红线，不放行）
- 普通用户 → 仅本人创建
"""

from unittest.mock import MagicMock, patch

from app.services.data_scope_query import scoped_count, scoped_filter, scoped_query


def _make_db():
    db = MagicMock()
    base_query = MagicMock()
    db.query.return_value = base_query
    return db, base_query


def _admin_user(org_id=7):
    user = MagicMock()
    user.is_superuser = False
    user.role = "admin"
    user.id = 1
    user.organization_id = org_id
    return user


class TestScopedQuery:
    def test_super_admin_unfiltered(self):
        db, base_query = _make_db()
        user = MagicMock()
        user.is_superuser = True
        user.role = "super_admin"
        result = scoped_query(db, MagicMock(), user)
        assert result is base_query
        base_query.filter.assert_not_called()

    def test_admin_scoped_to_own_org(self):
        db, base_query = _make_db()
        model = MagicMock()
        model.organization_id = MagicMock()
        result = scoped_query(db, model, _admin_user(7))
        assert result is not base_query
        base_query.filter.assert_called_once()

    def test_plain_user_scoped_to_owner(self):
        db, base_query = _make_db()
        user = MagicMock()
        user.is_superuser = False
        user.role = "user"
        user.id = 42
        model = MagicMock()
        model.created_by = MagicMock()
        result = scoped_query(db, model, user)
        assert result is not base_query
        base_query.filter.assert_called_once()

    def test_delegates_to_core_single_source(self):
        db, base_query = _make_db()
        user = _admin_user(7)
        with patch("app.core.data_permission.filter_by_data_scope", wraps=None) as mock_core:
            mock_core.return_value = base_query
            scoped_query(db, MagicMock(), user)
        assert mock_core.called


class TestScopedFilter:
    def test_appends_to_existing_query(self):
        user = _admin_user(7)
        model = MagicMock()
        model.organization_id = MagicMock()
        query = MagicMock()
        with patch("app.core.data_permission.filter_by_data_scope") as mock_core:
            mock_core.return_value = query
            result = scoped_filter(query, model, user)
        assert result is query
        args = mock_core.call_args[0]
        assert args[0] is query and args[1] is model and args[2] is user


class TestScopedCount:
    def test_counts_filtered_query(self):
        db, base_query = _make_db()
        user = MagicMock()
        user.is_superuser = True
        base_query.count.return_value = 5
        assert scoped_count(db, MagicMock(), user) == 5
        base_query.count.assert_called_once()
