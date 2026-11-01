# -*- coding: utf-8 -*-
"""SEC-3 回归：组织通行码 / 校验码链路必须受组织范围约束（2026-10-31 审计）。

历史缺陷：这些端点只判 ``is_admin`` 后直接查全表或按任意 org_id 生成校验码 →
部门级 admin 可读取、导出、删除其它组织的通行码（通行码可直接用于注册账号）。
本文件把「按组织收敛」的行为钉死，避免以后新增端点时又退回裸查询。
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import machine_code as mc_api
from app.services.machine_code_service import MachineCodeService

SUPER_ADMIN = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=1)
DEPT_ADMIN = SimpleNamespace(id=2, username="dept", role="admin", is_superuser=False, organization_id=10)
DEPT_ADMIN_NO_ORG = SimpleNamespace(id=3, username="dept2", role="admin", is_superuser=False, organization_id=None)


def _patch_subtree(monkeypatch, ids=(10, 11)):
    monkeypatch.setattr(
        "app.core.data_permission._get_org_subtree", lambda db, org_id: (list(ids), [])
    )


def test_scoped_org_ids_unrestricted_for_superuser():
    assert mc_api._scoped_org_ids(object(), SUPER_ADMIN) is None


def test_scoped_org_ids_uses_own_subtree_for_department_admin(monkeypatch):
    _patch_subtree(monkeypatch)
    assert mc_api._scoped_org_ids(object(), DEPT_ADMIN) == [10, 11]


def test_scoped_org_ids_fail_closed_without_organization(monkeypatch):
    _patch_subtree(monkeypatch)
    # 无组织归属 → 空列表（列表端点据此返回空集，绝不退化为全量）
    assert mc_api._scoped_org_ids(object(), DEPT_ADMIN_NO_ORG) == []


def test_org_verification_code_rejects_unreachable_org(monkeypatch):
    """部门级 admin 传其它组织 id → 403（校验码可换通行码，不得跨组织签发）。"""
    from app.core.data_permission import assert_org_reachable as real_guard

    monkeypatch.setattr(mc_api, "assert_org_reachable", real_guard)

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None  # 目标组织不可达

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.get_organization_verification_code(
                org_id=99, db=_Db(), current_user=DEPT_ADMIN
            )
        )
    assert exc.value.status_code == 403


def test_create_org_pass_code_checks_reachability(monkeypatch):
    called = {}

    def _guard(db, user, org_id, *, action):
        called["org_id"] = org_id
        raise HTTPException(status_code=403, detail="无权")

    monkeypatch.setattr(mc_api, "assert_org_reachable", _guard)
    request = SimpleNamespace(
        organization_id=99,
        verification_code="1234",
        allow_subordinate_generation=False,
        description=None,
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.create_organization_pass_code(
                request=request, db=object(), current_user=DEPT_ADMIN
            )
        )
    assert exc.value.status_code == 403
    assert called["org_id"] == 99


def test_list_passes_scoped_org_ids_to_service(monkeypatch):
    captured = {}

    def _list(self, **kwargs):
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr(MachineCodeService, "get_organization_pass_codes", _list)
    _patch_subtree(monkeypatch)

    result = asyncio.run(
        mc_api.list_organization_pass_codes(
            organization_id=None,
            status=None,
            page=1,
            page_size=20,
            db=object(),
            current_user=DEPT_ADMIN,
        )
    )
    assert captured["organization_ids"] == [10, 11]
    assert result["data"]["items"] == []


def test_list_rejects_foreign_organization_filter(monkeypatch):
    from app.core.data_permission import assert_org_reachable as real_guard

    monkeypatch.setattr(mc_api, "assert_org_reachable", real_guard)

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(
        MachineCodeService, "get_organization_pass_codes", lambda self, **kw: ([], 0)
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.list_organization_pass_codes(
                organization_id=99,
                status=None,
                page=1,
                page_size=20,
                db=_Db(),
                current_user=DEPT_ADMIN,
            )
        )
    assert exc.value.status_code == 403


def test_export_rejects_foreign_organization_filter(monkeypatch):
    """导出端点显式传外部 organization_id 时必须 403（SEC-3：导出与列表同口径）。

    该守卫是 CI 覆盖率缺口（machine_code.py:886）——只测了列表端点没测导出，
    会让「按组织导出」重新变成跨组织数据出口。
    """
    from app.core.data_permission import assert_org_reachable as real_guard

    monkeypatch.setattr(mc_api, "assert_org_reachable", real_guard)

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(
        MachineCodeService, "get_organization_pass_codes", lambda self, **kw: ([], 0)
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.export_organization_pass_codes(
                organization_id=99,
                status=None,
                db=_Db(),
                current_user=DEPT_ADMIN,
            )
        )
    assert exc.value.status_code == 403


def test_service_list_filters_by_organization_ids():
    """服务层：organization_ids 必须落到 SQL 过滤；空列表 = 无结果（fail-closed）。"""
    from app.models.machine_code import MachineCode

    filters = []

    class _Query:
        def filter(self, expr):
            filters.append(str(expr))
            return self

        def count(self):
            return 0

        def options(self, *a, **kw):
            return self

        def order_by(self, *a, **kw):
            return self

        def offset(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return self

        def all(self):
            return []

    class _Db:
        def query(self, model):
            assert model is MachineCode
            return _Query()

    service = MachineCodeService.__new__(MachineCodeService)
    service.db = _Db()
    records, total = service.get_organization_pass_codes(organization_ids=[10, 11])
    assert (records, total) == ([], 0)
    assert any("organization_id IN" in f for f in filters)
