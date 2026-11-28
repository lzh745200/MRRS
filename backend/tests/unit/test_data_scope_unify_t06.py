"""T06：数据范围多入口语义统一（all 的跨组织豁免收口）。

历史口径：

* ``apply_scope_filter``（列表/详情/组织树）把 ``data_scope="all"`` 无条件
  当全量放行；
* ``get_org_scope`` 同样把 ``all`` 当全局管理员；
* ``get_accessible_org_ids`` 对任意 admin 返回 ``None``（不受组织限制）。

结果：同一「部门管理员 + 全部数据」在不同入口分别得到全量、本组织、403，
违背军审红线 S2 的隔离口径。本文件锁定 T06 新规则：

* 只有真正的超级管理员（``is_superuser`` 或 ``role=super_admin``）可跨组织全量；
* 部门级 admin 的 ``all`` 收敛为本组织及子树；
* 普通用户/只读角色的 ``all`` 收敛为仅本人；
* 三个入口（``apply_scope_filter`` / ``get_org_scope`` /
  ``get_accessible_org_ids``）在同一角色/范围组合下给出同一组织集合或同一
  「仅本人」口径。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

import app.core.data_permission as dp

Base = declarative_base()


class TinyModel(Base):
    __tablename__ = "tiny_scope_t06"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer)
    created_by = Column(Integer)


def _user(**kwargs):
    defaults = {"is_superuser": False, "role": "user", "id": 42, "organization_id": 10}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _patch_subtree(return_value=([10, 11, 12], ["本部", "下级", "小组"])):
    return patch("app.core.data_permission._get_org_subtree", return_value=return_value)


def _apply_filter_with_query(user, db=None):
    query = MagicMock()
    result = dp.apply_scope_filter(query, user, TinyModel, db=db)
    return query, result


def test_has_unrestricted_data_scope_only_superuser():
    assert dp.has_unrestricted_data_scope(_user(is_superuser=True)) is True
    assert dp.has_unrestricted_data_scope(_user(role="super_admin")) is True
    admin = _user(role="admin", data_scope="all")
    viewer = _user(role="viewer", data_scope="all")
    assert dp.has_unrestricted_data_scope(admin) is False
    assert dp.has_unrestricted_data_scope(viewer) is False
    assert dp.has_unrestricted_data_scope(None) is False


def test_superuser_all_entries_are_global():
    user = _user(is_superuser=True, role="super_admin", data_scope="all")
    query, result = _apply_filter_with_query(user)
    assert result is query
    query.filter.assert_not_called()

    assert dp.get_accessible_org_ids(user) is None

    query2 = MagicMock()
    assert dp.apply_scope_to_query(query2, TinyModel, user) is query2
    query2.filter.assert_not_called()


@pytest.mark.asyncio
async def test_department_admin_all_entries_agree_to_subtree():
    user = _user(role="admin", data_scope="all", organization_id=10)

    # 列表/组织树入口
    query, result = _apply_filter_with_query(user, db=MagicMock())
    with _patch_subtree():
        assert result is query.filter.return_value
    query.filter.assert_called_once()

    # 组织树端点
    with patch("app.core.data_permission.is_superuser", return_value=False), _patch_subtree():
        scope = await dp.get_org_scope(current_user=user, db=MagicMock())
    assert scope.is_admin is False
    assert scope.org_ids == [10, 11, 12]
    assert scope.self_only is False

    # 可访问组织 id 入口
    with _patch_subtree():
        assert dp.get_accessible_org_ids(user, db=MagicMock()) == [10, 11, 12]

    # 导出/列表底层入口：也必须过滤，而不是全量
    query2 = MagicMock()
    result2 = dp.apply_scope_to_query(query2, TinyModel, user)
    assert result2 == query2.filter.return_value
    query2.filter.assert_called_once()


@pytest.mark.asyncio
async def test_department_admin_org_entries_agree_to_subtree():
    user = _user(role="admin", data_scope="org", organization_id=10)

    query, result = _apply_filter_with_query(user, db=MagicMock())
    with _patch_subtree():
        assert result is query.filter.return_value
    query.filter.assert_called_once()

    with patch("app.core.data_permission.is_superuser", return_value=False), _patch_subtree():
        scope = await dp.get_org_scope(current_user=user, db=MagicMock())
    assert scope.is_admin is False
    assert scope.org_ids == [10, 11, 12]

    with _patch_subtree():
        assert dp.get_accessible_org_ids(user, db=MagicMock()) == [10, 11, 12]


def test_viewer_all_entries_agree_to_own_records():
    user = _user(role="viewer", data_scope="all", organization_id=10)

    query, result = _apply_filter_with_query(user, db=MagicMock())
    query.filter.assert_called_once()
    assert result is query.filter.return_value

    assert dp.get_accessible_org_ids(user, db=MagicMock()) == []

    query2 = MagicMock()
    result2 = dp.apply_scope_to_query(query2, TinyModel, user)
    query2.filter.assert_called_once()
    assert result2 is query2.filter.return_value


@pytest.mark.asyncio
async def test_viewer_all_org_scope_entry_is_self_only():
    user = _user(role="viewer", data_scope="all", organization_id=10, id=42)

    with patch("app.core.data_permission.is_superuser", return_value=False):
        scope = await dp.get_org_scope(current_user=user, db=None)
    assert scope.is_admin is False
    assert scope.self_only is True
    assert scope.user_id == 42


@pytest.mark.asyncio
async def test_super_admin_role_data_scope_all_is_global():
    user = _user(role="super_admin", data_scope="all", organization_id=10)

    query, result = _apply_filter_with_query(user)
    assert result is query
    query.filter.assert_not_called()

    with patch("app.core.data_permission.is_superuser", return_value=False):
        scope = await dp.get_org_scope(current_user=user, db=None)
    assert scope.is_admin is True
    assert dp.get_accessible_org_ids(user) is None


def test_organization_list_cache_only_for_true_superuser():
    """orgs:list 缓存键只对真正全局用户启用，避免部门级 admin 受限结果污染。

    T06 后 `data_scope=all` 不再让部门级 admin 进入全量缓存。
    """
    globals_ok = MagicMock(
        is_superuser=True,
        role="super_admin",
        data_scope="all",
        organization_id=1,
    )
    scoped_admin = MagicMock(
        is_superuser=False,
        role="admin",
        data_scope="all",
        organization_id=1,
    )
    assert dp.has_unrestricted_data_scope(scoped_admin) is False
    assert dp.has_unrestricted_data_scope(globals_ok) is True

@pytest.mark.asyncio
async def test_superuser_all_org_scope_entry_is_global():
    user = _user(is_superuser=True, role="super_admin", data_scope="all")
    scope = await dp.get_org_scope(current_user=user, db=MagicMock())
    assert scope.is_admin is True
