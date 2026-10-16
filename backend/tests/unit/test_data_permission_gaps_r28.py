"""R28：data_permission 收口后补齐的行/分支覆盖（.coveragerc fail_under=100）。

R27-H8/M40 修改了 app/core/data_permission.py，改动后以下防御分支必须重新被真实
驱动（否则全量覆盖率门禁从 100% 掉到 97.5%）：

* :func:`apply_scope_to_query` OWN 分支 —— 模型连 owner 字段都没有时 fail-closed
  返回空集（`sa_false()`），而不是放行全量或抛 AttributeError→500；
* :func:`_apply_org_filter` 的"缺组织字段"不可达防御 —— 直接调用时抛
  :class:`DataScopeFilterError`；
* :func:`check_record_access` 组织归属缺失时的告警分支。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, select
from sqlalchemy.orm import declarative_base

import app.core.data_permission as dp
from app.core.data_permission import DataScope, DataScopeFilterError

Base = declarative_base()


class OwnerlessModel(Base):
    """有组织字段、没有 owner 字段的模型（apply_scope_to_query OWN 分支用）。"""

    __tablename__ = "ownerless_model_r28"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer)


def _user(**kwargs):
    defaults = {"is_superuser": False, "data_scope": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestApplyScopeToQueryOwnerlessFailClosed:
    def test_ownerless_model_returns_empty_set_not_full_scan(self):
        q = MagicMock(name="query")
        user = _user(id=11, role="user")
        with patch.object(dp, "logger") as mock_logger:
            result = dp.apply_scope_to_query(q, OwnerlessModel, user)
        # fail-closed：过滤成空集，而不是原样返回（原样返回=全量泄漏）
        q.filter.assert_called_once()
        assert result is q.filter.return_value
        mock_logger.warning.assert_called_once()

    def test_ownerless_model_real_query_compiles_to_false(self):
        """真实 Query 上确认过滤条件恒假（不是"没加条件"）。"""
        stmt = select(OwnerlessModel)
        user = _user(id=11, role="user")
        result = dp.apply_scope_to_query(stmt, OwnerlessModel, user)
        assert result is not stmt
        assert "WHERE" in str(result)

    def test_owner_present_filters_by_owner_id(self):
        class OwnedModel(Base):
            __tablename__ = "owned_model_r28"
            id = Column(Integer, primary_key=True)
            organization_id = Column(Integer)
            created_by = Column(Integer)

        stmt = select(OwnedModel)
        result = dp.apply_scope_to_query(stmt, OwnedModel, _user(id=11, role="user"))
        assert 11 in list(result.compile().params.values())


class TestApplyOrgFilterDefensive:
    def test_missing_org_field_raises(self):
        """不可达防御：调用方绕过 _has_field 前置检查时抛错拒绝，绝不静默全量。"""
        with pytest.raises(DataScopeFilterError):
            dp._apply_org_filter(MagicMock(), OwnerlessModel, "no_such_field", [1, 2])

    def test_select_and_query_styles(self):
        q = MagicMock(name="query")
        dp._apply_org_filter(q, OwnerlessModel, "organization_id", [3, 4])
        q.filter.assert_called_once()
        stmt = select(OwnerlessModel)
        filtered = dp._apply_org_filter(stmt, OwnerlessModel, "organization_id", [3, 4])
        assert filtered is not stmt


class TestCheckRecordAccessLogging:
    def test_missing_org_logs_warning_and_denies(self):
        user = _user(id=12, role="admin", organization_id=10)
        record = SimpleNamespace(organization_id=None, created_by=12)
        with patch.object(dp, "logger") as mock_logger:
            assert dp.check_record_access(record, user) is False
        mock_logger.warning.assert_called_once()

    def test_own_scope_uses_owner_field(self):
        user = _user(id=12, role="user")
        assert dp.check_record_access(SimpleNamespace(created_by=12), user) is True

    def test_unknown_scope_degrades_to_owner_check(self):
        """未知 scope 不 fail-open：退回 OWN 语义（只认 created_by == user.id）。"""
        with patch.object(dp, "get_data_scope", return_value="not-a-scope"):
            assert dp.check_record_access(SimpleNamespace(created_by=1), _user(id=1)) is True
            assert dp.check_record_access(SimpleNamespace(created_by=99), _user(id=1)) is False


class TestGetDataScopeMatrix:
    """get_data_scope 角色矩阵（收口后的权威口径）。"""

    def test_none_user_is_own(self):
        assert dp.get_data_scope(None) == DataScope.OWN

    def test_super_admin_is_all(self):
        assert dp.get_data_scope(_user(id=1, role="super_admin")) == DataScope.ALL

    def test_admin_with_org_is_own_dept(self):
        assert dp.get_data_scope(_user(id=1, role="admin", organization_id=3)) == DataScope.OWN_DEPT

    def test_admin_without_org_degrades_to_own(self):
        assert dp.get_data_scope(_user(id=1, role="admin", organization_id=None)) == DataScope.OWN

    def test_plain_user_is_own(self):
        assert dp.get_data_scope(_user(id=1, role="user", organization_id=3)) == DataScope.OWN
