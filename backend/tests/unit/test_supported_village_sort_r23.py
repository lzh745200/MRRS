# -*- coding: utf-8 -*-
"""R23 回归：帮扶村列表排序契约（默认最新在前 + 白名单排序）。

背景缺陷
--------
列表固定 ``order_by(SupportedVillage.id)`` **升序**，新建记录 id 最大、落在最后一页；
而前端新建成功后将分页重置到第 1 页 → 用户反馈"提交成功却看不到新记录"
（对比 ``projects.py`` 早已是 ``Project.id.desc()`` 默认）。

此外前端部门列 ``sortable="custom"`` 会下发 ``sort_by``/``sort_order``，但后端从未
声明这两个查询参数，排序被 FastAPI 静默丢弃。

修复后
------
- 默认（无有效 ``sort_by``）按 ``id`` 倒序 → 最新创建的记录排在首位，立即可见。
- ``sort_by``/``sort_order`` 经 ``_SORTABLE_COLUMNS`` 白名单解析后生效。
- 未知/非法 ``sort_by`` 安全回退为 ``id`` 倒序（不注入任意列）。
"""

from unittest.mock import Mock

from app.core.security import get_current_user

BASE = "/api/v1/supported-villages"


def _make_user(uid=1, org=1, role="admin"):
    user = Mock()
    user.id = uid
    user.username = f"user{uid}"
    user.role = role
    user.is_superuser = (role == "admin")
    user.is_active = True
    user.organization_id = org
    user.permissions_list = ["*"]
    user.data_scope = None
    return user


def _set_user(client):
    client.app.dependency_overrides[get_current_user] = lambda: _make_user()


def _create(client, name, department=None):
    payload = {"village_name": name, "province": "贵州省", "county": "测试县"}
    if department is not None:
        payload["department"] = department
    resp = client.post(BASE, json=payload)
    assert resp.status_code in (200, 201), resp.text[:300]
    return resp.json().get("data", {}).get("id")


def _items(resp):
    assert resp.status_code == 200, resp.text[:300]
    return resp.json().get("data", {}).get("items", [])


class TestVillageListOrdering:
    def test_default_newest_first(self, client_with_db):
        """新建 3 条后默认列表：最新创建（id 最大）必须排在最前。"""
        client, _db = client_with_db
        _set_user(client)

        a = _create(client, "排序村A")
        b = _create(client, "排序村B")
        c = _create(client, "排序村C")

        ids = [it.get("id") for it in _items(client.get(BASE))]
        assert ids[:3] == [c, b, a], f"默认应按 id 倒序（最新在前），实际 {ids}"

    def test_explicit_department_sort(self, client_with_db):
        """显式 sort_by=department&sort_order=asc：按部门升序。"""
        client, _db = client_with_db
        _set_user(client)

        _create(client, "部门村1", department="丙部门")
        _create(client, "部门村2", department="甲部门")
        _create(client, "部门村3", department="乙部门")

        deps = [it.get("department") for it in _items(client.get(f"{BASE}?sort_by=department&sort_order=asc"))]
        assert deps[:3] == sorted(deps[:3]), f"应按部门升序，实际 {deps[:3]}"

        deps_desc = [
            it.get("department")
            for it in _items(client.get(f"{BASE}?sort_by=department&sort_order=desc"))
        ]
        assert deps_desc[:3] == sorted(deps_desc[:3], reverse=True), f"应按部门降序，实际 {deps_desc[:3]}"

    def test_camelcase_prop_maps_to_column(self, client_with_db):
        """前端 el-table 的 camelCase prop（villageName）应能命中对应列。"""
        client, _db = client_with_db
        _set_user(client)

        _create(client, "丙村")
        _create(client, "甲村")
        _create(client, "乙村")

        names = [it.get("villageName") for it in _items(client.get(f"{BASE}?sort_by=villageName&sort_order=asc"))]
        assert names[:3] == sorted(names[:3]), f"应按村名升序，实际 {names[:3]}"

    def test_unknown_sort_falls_back_to_id_desc(self, client_with_db):
        """非法 sort_by 不得注入任意列，安全回退为 id 倒序。"""
        client, _db = client_with_db
        _set_user(client)

        a = _create(client, "回退村A")
        b = _create(client, "回退村B")

        ids = [it.get("id") for it in _items(client.get(f"{BASE}?sort_by=evil_column&sort_order=asc"))]
        assert ids[:2] == [b, a], f"未知排序应回退 id 倒序，实际 {ids}"
