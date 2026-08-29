"""
核心安全工具函数覆盖率测试

补充测试覆盖以下关键模块：
  - app/core/data_permission.py (filter_by_data_scope, check_record_access, get_data_scope)
  - app/core/response.py (ok_list, success_response, error_response)
  - app/api/v1/deps.py (require_manager_role)
  - app/core/transaction.py (safe_commit)

这些测试针对修复涉及的核心函数，确保权限逻辑的正确性。
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException


# ═══════════════════════════════════════════════════════════
#  data_permission.py 完整覆盖
# ═══════════════════════════════════════════════════════════


class TestDataScope:
    """测试 get_data_scope 函数"""

    def test_none_user_returns_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        assert get_data_scope(None) == DataScope.OWN

    def test_super_admin_returns_all(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        assert get_data_scope(user) == DataScope.ALL

    def test_admin_returns_own_dept(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_manager_returns_own_dept(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "manager"
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_approval_leader_returns_own_dept(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "approval_leader"
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_regular_user_returns_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        assert get_data_scope(user) == DataScope.OWN

    def test_viewer_returns_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "viewer"
        assert get_data_scope(user) == DataScope.OWN

    def test_empty_role_returns_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = ""
        assert get_data_scope(user) == DataScope.OWN

    def test_no_role_attr_returns_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock(spec=[])
        user.is_superuser = False
        assert get_data_scope(user) == DataScope.OWN


class TestApplyScopeToQuery:
    """测试 apply_scope_to_query 函数"""

    def _make_query_mock(self):
        """创建一个可链式调用的 query mock"""
        q = MagicMock()
        q.filter.return_value = q
        return q

    def test_all_scope_returns_query_unchanged(self):
        from app.core.data_permission import apply_scope_to_query
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        model = Mock()
        q = self._make_query_mock()
        result = apply_scope_to_query(q, model, user)
        assert result is q
        q.filter.assert_not_called()

    def test_own_dept_scope_filters_by_organization(self):
        from app.core.data_permission import apply_scope_to_query
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.organization_id = 5
        model = Mock()
        model.organization_id = Mock()
        q = self._make_query_mock()
        result = apply_scope_to_query(q, model, user)
        assert result is q
        q.filter.assert_called_once()

    def test_own_dept_no_org_falls_back_to_own(self):
        from app.core.data_permission import apply_scope_to_query
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.organization_id = None
        user.id = 3
        model = Mock()
        model.created_by = Mock()
        q = self._make_query_mock()
        result = apply_scope_to_query(q, model, user)
        assert result is q
        # 应回退到 OWN scope，按 created_by 过滤
        q.filter.assert_called_once()

    def test_own_scope_filters_by_owner(self):
        from app.core.data_permission import apply_scope_to_query
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 7
        model = Mock()
        model.created_by = Mock()
        q = self._make_query_mock()
        result = apply_scope_to_query(q, model, user)
        assert result is q
        q.filter.assert_called_once()


class TestCheckRecordAccess:
    """测试 check_record_access 函数"""

    def test_all_scope_allows_anything(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        user.organization_id = 1
        record = Mock()
        record.organization_id = 999
        record.created_by = 888
        assert check_record_access(record, user) is True

    def test_own_dept_same_org_allowed(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.organization_id = 5
        record = Mock()
        record.organization_id = 5
        record.created_by = 999
        assert check_record_access(record, user) is True

    def test_own_dept_diff_org_denied(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.organization_id = 5
        record = Mock()
        record.organization_id = 999
        record.created_by = 888
        assert check_record_access(record, user) is False

    def test_own_scope_own_record_allowed(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 7
        user.organization_id = 5
        record = Mock()
        record.organization_id = 999
        record.created_by = 7
        assert check_record_access(record, user) is True

    def test_own_scope_other_record_denied(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 7
        user.organization_id = 5
        record = Mock()
        record.organization_id = 999
        record.created_by = 888
        assert check_record_access(record, user) is False

    def test_custom_owner_field(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 7
        user.organization_id = 5
        record = Mock()
        record.organization_id = 999
        record.uploader_id = 7
        assert check_record_access(record, user, owner_field="uploader_id") is True

    def test_custom_dept_field(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.org_id = 5
        record = Mock()
        record.org_id = 5
        record.created_by = 999
        assert check_record_access(record, user, dept_field="org_id") is True


class TestFilterByDataScope:
    """测试 filter_by_data_scope 函数"""

    def test_admin_returns_query_unchanged(self):
        from app.core.data_permission import filter_by_data_scope
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        q = MagicMock()
        result = filter_by_data_scope(q, Mock(), user, db=None)
        assert result is q

    def test_non_admin_applies_filter(self):
        from app.core.data_permission import filter_by_data_scope
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 7
        user.organization_id = 5
        q = MagicMock()
        q.filter.return_value = q
        model = Mock()
        model.created_by = Mock()
        result = filter_by_data_scope(q, model, user, db=None)
        assert result is q
        q.filter.assert_called_once()


class TestRequireDataPermission:
    """测试 require_data_permission 函数"""

    def test_admin_passes(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        # 管理员应直接通过，不需要 db
        assert require_data_permission(user, organization_id=999) is True

    def test_created_by_match_passes(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 5
        db = Mock()
        assert require_data_permission(user, created_by=5, db=db) is True

    def test_no_match_raises_403(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 5
        db = Mock()
        with pytest.raises(HTTPException) as exc:
            require_data_permission(user, created_by=999, db=db)
        assert exc.value.status_code == 403

    def test_no_db_raises_403(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 5
        with pytest.raises(HTTPException) as exc:
            require_data_permission(user, created_by=999, db=None)
        assert exc.value.status_code == 403

    def test_custom_error_message(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 5
        db = Mock()
        with pytest.raises(HTTPException) as exc:
            require_data_permission(user, created_by=999, db=db, error_message="自定义错误")
        assert "自定义错误" in exc.value.detail


# ═══════════════════════════════════════════════════════════
#  response.py 完整覆盖
# ═══════════════════════════════════════════════════════════


class TestResponseHelpers:
    """测试响应工具函数"""

    def test_success_response_basic(self):
        from app.core.response import success_response
        r = success_response(data={"id": 1}, message="ok")
        assert r["code"] == 200
        assert r["success"] is True
        assert r["message"] == "ok"
        assert r["data"] == {"id": 1}

    def test_success_response_no_data(self):
        from app.core.response import success_response
        r = success_response()
        assert r["code"] == 200
        assert r["success"] is True
        assert "data" not in r

    def test_success_response_extra_kwargs(self):
        from app.core.response import success_response
        r = success_response(data={"x": 1}, extra_field="val")
        assert r["extra_field"] == "val"

    def test_error_response_basic(self):
        from app.core.response import error_response
        r = error_response(code=400, message="bad")
        assert r["code"] == 400
        assert r["success"] is False
        assert r["message"] == "bad"

    def test_error_response_with_errors_and_detail(self):
        from app.core.response import error_response
        r = error_response(code=422, message="val", errors=["e1"], detail="d1")
        assert r["errors"] == ["e1"]
        assert r["detail"] == "d1"

    def test_ok_list_basic(self):
        from app.core.response import ok_list
        r = ok_list(items=["a", "b"], total=2, page=1, page_size=20)
        assert r["code"] == 200
        assert r["data"]["items"] == ["a", "b"]
        assert r["data"]["total"] == 2
        assert r["data"]["page"] == 1
        assert r["data"]["page_size"] == 20

    def test_ok_list_custom_message(self):
        from app.core.response import ok_list
        r = ok_list(items=[], total=0, message="自定义")
        assert r["message"] == "自定义"

    def test_ok_list_extra_kwargs(self):
        from app.core.response import ok_list
        r = ok_list(items=[], total=0, meta="extra")
        assert r["meta"] == "extra"


    def test_not_found_response(self):
        from app.core.response import not_found_response
        r = not_found_response("找不到")
        assert r["code"] == 404


    def test_forbidden_response(self):
        from app.core.response import forbidden_response
        r = forbidden_response()
        assert r["code"] == 403

    def test_server_error_response(self):
        from app.core.response import server_error_response
        r = server_error_response(detail="boom")
        assert r["code"] == 500
        assert r["detail"] == "boom"








# ═══════════════════════════════════════════════════════════
#  transaction.py safe_commit 覆盖
# ═══════════════════════════════════════════════════════════


class TestSafeCommit:
    """测试 safe_commit 函数"""

    def test_successful_commit_returns_true(self):
        from app.core.transaction import safe_commit
        db = Mock()
        db.commit = Mock()
        result = safe_commit(db)
        assert result is True
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    def test_commit_failure_rolls_back_and_reraises(self):
        from app.core.transaction import safe_commit
        db = Mock()
        db.commit.side_effect = Exception("commit failed")
        with pytest.raises(Exception, match="commit failed"):
            safe_commit(db)
        db.rollback.assert_called_once()

    def test_successful_commit_with_logger(self):
        from app.core.transaction import safe_commit
        import logging
        db = Mock()
        logger = Mock(spec=logging.Logger)
        result = safe_commit(db, logger=logger)
        assert result is True
        logger.error.assert_not_called()

    def test_commit_failure_with_logger_logs_error(self):
        from app.core.transaction import safe_commit
        import logging
        db = Mock()
        db.commit.side_effect = RuntimeError("boom")
        logger = Mock(spec=logging.Logger)
        with pytest.raises(RuntimeError):
            safe_commit(db, logger=logger)
        logger.error.assert_called_once()
        db.rollback.assert_called_once()


# ═══════════════════════════════════════════════════════════
#  data_permission.is_admin 完整覆盖（角色归一化矩阵）
# ═══════════════════════════════════════════════════════════


class TestIsAdminFunction:
    """测试 data_permission.is_admin 角色判断与归一化"""

    @pytest.mark.parametrize(
        "role,is_superuser,expected",
        [
            ("super_admin", False, True),
            ("super_admin", True, True),
            ("admin", False, True),
            ("manager", False, True),          # 废弃角色归一化 → admin
            ("approval_leader", False, True),  # 废弃角色归一化 → admin
            ("operator", False, False),        # 废弃角色归一化 → user
            ("user", False, False),
            ("viewer", False, False),
            ("", False, False),
        ],
    )
    def test_role_matrix(self, role, is_superuser, expected):
        from app.core.data_permission import is_admin
        user = Mock()
        user.role = role
        user.is_superuser = is_superuser
        assert is_admin(user) is expected

    def test_none_user_returns_false(self):
        from app.core.data_permission import is_admin
        assert is_admin(None) is False

    def test_missing_role_attr(self):
        from app.core.data_permission import is_admin
        user = Mock(spec=[])
        user.is_superuser = False
        assert is_admin(user) is False

    def test_superuser_any_role(self):
        from app.core.data_permission import is_admin
        user = Mock()
        user.role = "viewer"
        user.is_superuser = True
        assert is_admin(user) is True


class TestDataScopeWithNormalization:
    """废弃角色的 data_scope 归一化"""

    def test_manager_gets_own_dept(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "manager"
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_approval_leader_gets_own_dept(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "approval_leader"
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_operator_normalizes_to_user_own(self):
        from app.core.data_permission import get_data_scope, DataScope
        user = Mock()
        user.is_superuser = False
        user.role = "operator"
        assert get_data_scope(user) == DataScope.OWN


class TestRequireDataPermissionOrgPath:
    """require_data_permission 组织归属匹配分支"""

    def test_org_match_passes_without_created_by(self):
        """同组织记录即使非本人创建也放行"""
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.id = 5
        user.organization_id = 7
        user.is_superuser = False
        assert require_data_permission(user, organization_id=7, created_by=None, db=Mock()) is True

    def test_org_mismatch_and_creator_mismatch_raises_403(self):
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.id = 5
        user.organization_id = 7
        user.is_superuser = False
        with pytest.raises(HTTPException) as exc:
            require_data_permission(user, organization_id=999, created_by=888, db=Mock())
        assert exc.value.status_code == 403

    def test_none_org_id_ignored(self):
        """organization_id=None 时跳过组织检查，直接走 403"""
        from app.core.data_permission import require_data_permission
        user = Mock()
        user.id = 5
        user.organization_id = None
        user.is_superuser = False
        with pytest.raises(HTTPException):
            require_data_permission(user, organization_id=None, created_by=999, db=Mock())


class TestCheckRecordAccessEdgeCases:
    """check_record_access 缺失字段场景"""

    def test_record_without_dept_attr_returns_false_for_admin_dept(self):
        """admin 访问 organization_id 字段缺失的记录 → 比较结果依赖 getattr 默认值"""
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "admin"
        user.organization_id = 5
        record = object()  # 无任何属性 → getattr 返回 None != 5
        assert check_record_access(record, user) is False

    def test_record_without_owner_attr_denies_own_user(self):
        from app.core.data_permission import check_record_access
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        user.id = 5
        record = object()  # 无 created_by 属性 → None != 5
        assert check_record_access(record, user) is False


# ═══════════════════════════════════════════════════════════
#  deps.py 辅助函数覆盖
# ═══════════════════════════════════════════════════════════


class TestRequireFundsOperatorRole:
    """经费操作权限：viewer 只读，user 及以上可操作"""

    def test_viewer_denied(self):
        from app.api.v1.deps import require_funds_operator_role
        user = Mock()
        user.role = "viewer"
        user.is_superuser = False
        with pytest.raises(HTTPException) as exc:
            require_funds_operator_role(user)
        assert exc.value.status_code == 403

    def test_viewer_but_superuser_allowed(self):
        from app.api.v1.deps import require_funds_operator_role
        user = Mock()
        user.role = "viewer"
        user.is_superuser = True
        require_funds_operator_role(user)  # 不抛异常

    def test_user_allowed(self):
        from app.api.v1.deps import require_funds_operator_role
        user = Mock()
        user.role = "user"
        user.is_superuser = False
        require_funds_operator_role(user)

    def test_operator_normalized_to_user_allowed(self):
        from app.api.v1.deps import require_funds_operator_role
        user = Mock()
        user.role = "operator"  # 废弃角色，归一化为 user
        user.is_superuser = False
        require_funds_operator_role(user)

    def test_admin_allowed(self):
        from app.api.v1.deps import require_funds_operator_role
        user = Mock()
        user.role = "admin"
        user.is_superuser = False
        require_funds_operator_role(user)


class TestBuildViewableBecause:
    """软删记录可见性元数据生成"""

    def test_none_record_returns_none(self):
        from app.api.v1.deps import build_viewable_because
        assert build_viewable_because(Mock(), None) is None

    def test_none_user_returns_none(self):
        from app.api.v1.deps import build_viewable_because
        record = Mock()
        record.is_active = False
        assert build_viewable_because(None, record) is None

    def test_active_record_returns_none(self):
        from app.api.v1.deps import build_viewable_because
        user = Mock()
        user.is_superuser = True
        record = Mock()
        record.is_active = True
        assert build_viewable_because(user, record) is None

    def test_missing_is_active_treated_as_active(self):
        from app.api.v1.deps import build_viewable_because
        user = Mock()
        record = object()  # 无 is_active 属性 → 默认视为活跃
        assert build_viewable_because(user, record) is None

    def test_admin_views_soft_deleted_returns_admin(self):
        from app.api.v1.deps import build_viewable_because
        user = Mock()
        user.is_superuser = True
        user.role = "super_admin"
        record = Mock()
        record.is_active = False
        assert build_viewable_because(user, record) == "admin"

    def test_non_admin_views_soft_deleted_returns_none(self):
        from app.api.v1.deps import build_viewable_because
        user = Mock()
        user.is_superuser = False
        user.role = "user"
        record = Mock()
        record.is_active = False
        assert build_viewable_because(user, record) is None
