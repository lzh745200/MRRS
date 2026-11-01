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


def test_delete_skips_guard_when_target_missing(monkeypatch):
    """目标记录不存在时必须跳过组织守卫并返回 404（分支覆盖 machine_code.py:965）。

    该分支是 CI 覆盖率缺口：DELETE 端点先按 id 取归属组织再做可达性校验，
    「取不到记录」这一侧此前没有用例走过，等于删除路径的守卫短路行为未被钉住。
    """
    guard_calls = []
    monkeypatch.setattr(
        mc_api, "assert_org_reachable", lambda *a, **kw: guard_calls.append(a)
    )

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(
        MachineCodeService, "delete_organization_pass_code", lambda self, pass_code_id: False
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.delete_organization_pass_code(
                pass_code_id=123456,
                db=_Db(),
                current_user=DEPT_ADMIN,
            )
        )
    assert exc.value.status_code == 404
    assert guard_calls == []


# ---------------------------------------------------------------------------
#  立即项 2026-11-01：/admin/list 与 /admin/revoke 的组织收敛
#  历史缺陷：两处只判角色即查全表 / 按 id 撤销，机器码携带通行码与绑定用户名，
#  部门级 admin 可读到其它组织的通行码并使其失效。
# ---------------------------------------------------------------------------


def test_admin_list_passes_scoped_org_ids(monkeypatch):
    captured = {}

    class _Svc:
        def __init__(self, db):
            pass

        def list_machine_codes(self, **kwargs):
            captured.update(kwargs)
            return [], 0

    monkeypatch.setattr(mc_api, "MachineCodeService", _Svc)
    monkeypatch.setattr(mc_api, "_scoped_org_ids", lambda db, user: [10, 11])

    result = asyncio.run(
        mc_api.admin_list_machine_codes(
            status_filter=None, skip=0, limit=100, db=object(), current_user=DEPT_ADMIN
        )
    )
    assert captured["organization_ids"] == [10, 11]
    assert result["data"]["items"] == []
    assert result["data"]["total"] == 0


def test_service_list_machine_codes_org_filter_and_fail_closed():
    from unittest.mock import MagicMock

    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.options.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 0

    service = MachineCodeService(db)
    assert service.list_machine_codes(organization_ids=[]) == ([], 0)  # fail-closed 空集

    service.list_machine_codes(organization_ids=[10, 11])
    assert q.filter.called
    assert "organization_id IN" in str(q.filter.call_args[0][0])


def test_admin_revoke_rejects_unreachable_org(monkeypatch):
    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return SimpleNamespace(organization_id=99)

    def _deny(db, user, org_id, *, action):
        raise HTTPException(status_code=403, detail="无权撤销其它组织的机器码")

    monkeypatch.setattr(mc_api, "assert_org_reachable", _deny)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.admin_revoke_machine_code(
                machine_code_id=7, db=_Db(), current_user=DEPT_ADMIN
            )
        )
    assert exc.value.status_code == 403


def test_admin_revoke_unknown_record_returns_404_and_skips_guard(monkeypatch):
    guard_calls = []
    monkeypatch.setattr(mc_api, "assert_org_reachable", lambda *a, **kw: guard_calls.append(a))

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(MachineCodeService, "revoke_machine_code", lambda self, mid: False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.admin_revoke_machine_code(
                machine_code_id=7, db=_Db(), current_user=DEPT_ADMIN
            )
        )
    assert exc.value.status_code == 404
    assert guard_calls == []


def test_admin_revoke_same_org_allowed(monkeypatch):
    guard_calls = []
    monkeypatch.setattr(
        mc_api, "assert_org_reachable", lambda db, user, org_id, *, action: guard_calls.append(org_id)
    )

    class _Db:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return SimpleNamespace(organization_id=10)

    monkeypatch.setattr(MachineCodeService, "revoke_machine_code", lambda self, mid: True)
    result = asyncio.run(
        mc_api.admin_revoke_machine_code(
            machine_code_id=7, db=_Db(), current_user=DEPT_ADMIN
        )
    )
    assert result["success"] is True
    assert guard_calls == [10]


def test_admin_list_requires_admin():
    outsider = SimpleNamespace(id=9, username="u", role="user", is_superuser=False, organization_id=10)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.admin_list_machine_codes(
                db=object(), current_user=outsider
            )
        )
    assert exc.value.status_code == 403


def test_admin_revoke_requires_admin():
    outsider = SimpleNamespace(id=9, username="u", role="user", is_superuser=False, organization_id=10)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mc_api.admin_revoke_machine_code(db=object(), current_user=outsider, machine_code_id=1)
        )
    assert exc.value.status_code == 403
