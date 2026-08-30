"""app.core.data_scope_adapter 全覆盖测试（a24，该模块此前无测试文件）

覆盖 get_accessible_org_ids / apply_scope_filter 全部角色与范围分支，
以及 _apply_org_filter / _apply_owner_filter 的 Select/Query 两种风格与缺字段防御分支。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, select
from sqlalchemy.orm import declarative_base

import app.core.data_scope_adapter as adapter
from app.core.data_permission import DataScope
from app.core.data_scope_adapter import apply_scope_filter, get_accessible_org_ids

Base = declarative_base()


class TinyModel(Base):
    __tablename__ = "tiny_scope_a24"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer)
    created_by = Column(Integer)


class BareModel:
    """没有任何权限字段的模型"""


class OrgOnlyModel:
    """只有组织字段、没有所有者字段的模型"""

    organization_id = TinyModel.organization_id


def _user(**kwargs):
    defaults = {"is_superuser": False}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


ADMIN = _user(id=1, role="admin")
SUPERUSER = _user(id=2, role="viewer", is_superuser=True)
SCOPE_ALL = _user(id=3, role="viewer", data_scope="all")
SCOPE_SELF = _user(id=4, role="viewer", data_scope="self")
MANAGER = _user(id=5, role="manager", organization_id=10)
MANAGER_ORG_ID_ATTR = _user(id=6, role="manager", org_id=20)
MANAGER_NO_ORG = _user(id=7, role="manager", organization_id=None)
VIEWER = _user(id=8, role="viewer")


class TestGetAccessibleOrgIds:
    def test_none_user_returns_empty(self):
        assert get_accessible_org_ids(None) == []

    def test_admin_returns_none(self):
        assert get_accessible_org_ids(ADMIN) is None
        assert get_accessible_org_ids(SUPERUSER) is None

    def test_data_scope_all_returns_none(self):
        assert get_accessible_org_ids(SCOPE_ALL) is None

    def test_data_scope_self_returns_empty(self):
        assert get_accessible_org_ids(SCOPE_SELF) == []

    def test_scope_all_returns_none(self):
        # is_admin=False 但 get_data_scope=ALL（正常路径不可达，打补丁构造）
        with patch("app.core.data_permission.get_data_scope", return_value=DataScope.ALL):
            assert get_accessible_org_ids(VIEWER) is None

    def test_own_dept_without_db_returns_own_org(self):
        assert get_accessible_org_ids(MANAGER) == [10]

    def test_own_dept_uses_org_id_fallback_attr(self):
        assert get_accessible_org_ids(MANAGER_ORG_ID_ATTR) == [20]

    def test_own_dept_with_db_expands_subtree(self):
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([10, 11, 12], ["总部", "分部", "小组"])) as mock_sub:
            assert get_accessible_org_ids(MANAGER, db=MagicMock()) == [10, 11, 12]
        mock_sub.assert_called_once()

    def test_own_dept_with_db_empty_subtree_falls_back_to_org(self):
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([], [])):
            assert get_accessible_org_ids(MANAGER, db=MagicMock()) == [10]

    def test_own_dept_without_org_returns_empty(self):
        assert get_accessible_org_ids(MANAGER_NO_ORG) == []

    def test_own_scope_returns_empty(self):
        assert get_accessible_org_ids(VIEWER) == []


class TestApplyScopeFilter:
    def test_admin_query_unchanged(self):
        q = MagicMock()
        assert apply_scope_filter(q, ADMIN, TinyModel) is q
        q.filter.assert_not_called()

    def test_data_scope_all_query_unchanged(self):
        q = MagicMock()
        assert apply_scope_filter(q, SCOPE_ALL, TinyModel) is q
        q.filter.assert_not_called()

    def test_data_scope_self_applies_owner_filter_query(self):
        q = MagicMock()
        result = apply_scope_filter(q, SCOPE_SELF, TinyModel)
        q.filter.assert_called_once()
        assert result is q.filter.return_value

    def test_scope_all_query_unchanged(self):
        q = MagicMock()
        with patch("app.core.data_permission.get_data_scope", return_value=DataScope.ALL):
            assert apply_scope_filter(q, VIEWER, TinyModel) is q
        q.filter.assert_not_called()

    def test_own_dept_org_ids_none_returns_query(self):
        q = MagicMock()
        with patch.object(adapter, "get_accessible_org_ids", return_value=None):
            assert apply_scope_filter(q, MANAGER, TinyModel) is q
        q.filter.assert_not_called()

    def test_own_dept_applies_org_filter_query(self):
        q = MagicMock()
        result = apply_scope_filter(q, MANAGER, TinyModel)
        q.filter.assert_called_once()
        assert result is q.filter.return_value

    def test_own_dept_applies_org_filter_select(self):
        stmt = select(TinyModel)
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([10, 11], ["总部", "分部"])):
            result = apply_scope_filter(stmt, MANAGER, TinyModel, db=MagicMock())
        assert result is not stmt
        assert "WHERE" in str(result)

    def test_own_dept_without_org_falls_back_to_owner(self):
        q = MagicMock()
        result = apply_scope_filter(q, MANAGER_NO_ORG, TinyModel)
        q.filter.assert_called_once()
        assert result is q.filter.return_value

    def test_own_scope_applies_owner_filter_query(self):
        q = MagicMock()
        result = apply_scope_filter(q, VIEWER, TinyModel)
        q.filter.assert_called_once()
        assert result is q.filter.return_value

    def test_own_scope_applies_owner_filter_select(self):
        stmt = select(TinyModel)
        result = apply_scope_filter(stmt, VIEWER, TinyModel)
        assert result is not stmt
        assert "WHERE" in str(result)

    def test_model_without_any_scope_field_raises(self):
        """缺组织+缺 owner 字段 fail-closed（ADR-0002）：抛错拒绝，绝不静默放行全量"""
        from app.core.data_scope_adapter import DataScopeFilterError

        q = MagicMock()
        with pytest.raises(DataScopeFilterError):
            apply_scope_filter(q, MANAGER, BareModel)

    def test_model_without_owner_field_raises(self):
        """缺 owner 字段 fail-closed（ADR-0002）：抛 DataScopeFilterError 拒绝放行"""
        from app.core.data_scope_adapter import DataScopeFilterError

        q = MagicMock()
        with pytest.raises(DataScopeFilterError):
            apply_scope_filter(q, VIEWER, OrgOnlyModel)

    def test_custom_field_names(self):
        q = MagicMock()
        model = SimpleNamespace(dept_id=TinyModel.organization_id, owner_id=TinyModel.created_by)
        apply_scope_filter(q, MANAGER, model, org_id_field="dept_id", owner_field="owner_id")
        q.filter.assert_called_once()
