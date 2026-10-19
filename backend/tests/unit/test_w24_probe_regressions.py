"""R29 企业级深度探测回归测试（backend-probe 本次修复的缺陷）。

每条用例对应一处真实缺陷 + 最小修复，防止回归：

1. 帮扶村列表缓存键按用户隔离 —— 原键只含 organization_id，同一组织内
   admin 与 user/viewer 命中同一缓存键，普通用户/访客会读到管理员的整组织
   列表（数据权限绕过 / 跨角色数据泄漏）。
2. 学校列表缓存键按用户隔离 —— 同款缺陷（get_org_scope 下 admin 全量、
   普通用户组织子树）。
3. 组织列表缓存写入门禁 —— 读已按 _global_view 门禁、写漏了门禁，普通用户
   默认请求会把受限/空结果写进全局键 orgs:list，污染超管看到的数据。
4. GET /users 分页钳制 —— page_size 为裸 int，SQLite 语义下 limit=-1 等于
   不限量，一次拉全表（DoS / 信息暴露面）。
5. GET /machine-code/organization/list 分页钳制 —— 同款缺陷。
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.api.v1.auth.users as users_mod
import app.api.v1.machine_code as mc_mod
import app.api.v1.organization as org_mod
import app.api.v1.school as sch
import app.api.v1.supported_village as sv


def _query(**kw):
    """构造 SQLAlchemy Query 风格的链式 MagicMock。"""
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit", "options", "with_entities"):
        getattr(q, attr).return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


def _user(uid, role="user", org=1, su=False, username=None):
    return SimpleNamespace(
        id=uid, role=role, is_superuser=su, organization_id=org,
        username=username or f"user{uid}", data_scope=None,
    )


def _new_cache():
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


# ── 1. 帮扶村列表缓存键按用户隔离 ────────────────────────────────────────


def _run_village_list(current_user, cache):
    village = MagicMock()
    village.to_dict.return_value = {"id": 1, "villageName": "村A"}
    db = MagicMock()
    db.query.return_value = _query(all=[village], count=1)
    with (
        patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
        patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
        patch.object(sv, "apply_scope_filter", side_effect=lambda query, *a, **k: query),
    ):
        return asyncio.run(
            sv.list_villages(
                page=1, page_size=20, keyword=None, department=None, county=None,
                is_revitalization_tier=None, is_three_regions=None,
                is_ethnic_area=None, is_key_county=None, year_start=None,
                sort_by=None, sort_order=None, with_summary=False,
                isRevitalizationTier=None, include_deleted=False,
                current_user=current_user, db=db,
            )
        )


def test_village_list_cache_key_isolated_between_admin_and_user():
    """同组织内 admin 与 user 的缓存键必须不同（否则 user 会命中 admin 的整组织列表）。"""
    cache = _new_cache()
    admin = _user(1, role="admin", su=True)
    normal = _user(2, role="user", su=False)

    _run_village_list(admin, cache)
    admin_key = cache.get.call_args[0][0]
    _run_village_list(normal, cache)
    user_key = cache.get.call_args[0][0]

    assert admin_key != user_key, "同组织跨角色命中同一缓存键 = 数据权限绕过"
    assert admin_key.startswith("villages:list:1:"), admin_key
    assert user_key.startswith("villages:list:2:"), user_key
    assert cache.set.await_count == 2


def test_village_list_cache_key_isolated_between_users_same_role():
    """同组织同角色的两个用户也不得共用缓存键（数据域按 created_by 区分）。"""
    cache = _new_cache()
    user_a = _user(11, role="user")
    user_b = _user(12, role="user")

    _run_village_list(user_a, cache)
    key_a = cache.get.call_args[0][0]
    _run_village_list(user_b, cache)
    key_b = cache.get.call_args[0][0]

    assert key_a != key_b
    assert key_a.startswith("villages:list:11:")
    assert key_b.startswith("villages:list:12:")


# ── 2. 学校列表缓存键按用户隔离 ──────────────────────────────────────────


def _run_school_list(current_user, cache):
    db = MagicMock()
    q = _query(all=[], count=0)
    db.query.return_value = q
    scope = MagicMock()
    scope.filter_by_org_ids.return_value = q
    with (
        patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
        patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
    ):
        return asyncio.run(
            sch.list_schools(
                page=1, page_size=20, keyword=None, name=None, type=None,
                support_status=None, supportStatus=None, include_deleted=False,
                current_user=current_user, data_scope=scope, db=db,
            )
        )


def test_school_list_cache_key_isolated_between_admin_and_user():
    """同组织内 admin 与 user 的学校列表缓存键必须不同。"""
    cache = _new_cache()
    _run_school_list(_user(1, role="admin", su=True), cache)
    admin_key = cache.get.call_args[0][0]
    _run_school_list(_user(2, role="user"), cache)
    user_key = cache.get.call_args[0][0]

    assert admin_key != user_key, "学校列表缓存键跨角色碰撞 = 数据权限绕过"
    assert admin_key.startswith("schools:list:1:")
    assert user_key.startswith("schools:list:2:")


# ── 3. 组织列表缓存写入门禁 ──────────────────────────────────────────────


def _run_org_list(current_user, cache):
    db = MagicMock()
    db.query.return_value = _query(all=[], count=0)
    with (
        patch.object(org_mod, "cache_manager", cache),
        patch(
            "app.core.data_permission.apply_scope_filter",
            side_effect=lambda query, *a, **k: query,
        ),
    ):
        return asyncio.run(
            org_mod.get_organizations(
                page=1, page_size=20, org_type=None, parent_id=None,
                is_active=None, keyword=None, search=None,
                current_user=current_user, db=db, response=None,
            )
        )


def test_org_list_non_global_user_does_not_poison_shared_cache():
    """普通用户默认请求不得把受限结果写入全局键 orgs:list（缓存的读已门禁、写曾漏）。"""
    cache = _new_cache()
    _run_org_list(_user(2, role="user", org=1), cache)

    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()


def test_org_list_global_admin_can_read_and_write_shared_cache():
    """真正的全局管理员仍应读写共享缓存（原有加速语义不回归）。"""
    cache = _new_cache()
    _run_org_list(_user(1, role="super_admin", org=1, su=True), cache)

    assert cache.get.await_count == 1
    assert cache.set.await_count == 1
    assert cache.set.call_args[0][0] == "orgs:list"


# ── 4. GET /users 分页钳制 ───────────────────────────────────────────────


def _run_users_list(page, page_size):
    db = MagicMock()
    q = _query(all=[], count=0)
    db.query.return_value = q
    admin = _user(1, role="admin", su=True)
    with patch.object(users_mod, "_apply_user_data_scope", side_effect=lambda query, *a, **k: query):
        asyncio.run(
            users_mod.list_users(
                page=page, page_size=page_size, keyword=None, username=None,
                is_active=None, organization_id=None, role=None,
                current_user=admin, db=db,
            )
        )
    return q


def test_users_list_clamps_negative_page_size():
    """page_size=-1 在 SQLite 下等于不限量 → 必须被钳制为 1。"""
    q = _run_users_list(page=1, page_size=-1)
    assert q.limit.call_args[0][0] == 1
    assert q.offset.call_args[0][0] == 0


def test_users_list_clamps_oversized_page_size():
    """超大 page_size 必须被钳制到仓库上限 200（offset 深分页允许，但单页行数受限）。"""
    q = _run_users_list(page=3, page_size=10 ** 6)
    assert q.limit.call_args[0][0] == 200
    assert q.offset.call_args[0][0] == 2 * 10 ** 6


def test_users_list_clamps_negative_page():
    """page=0/负数产生的负偏移必须被钳制为 0。"""
    q = _run_users_list(page=-3, page_size=20)
    assert q.offset.call_args[0][0] == 0
    assert q.limit.call_args[0][0] == 20


# ── 5. GET /machine-code/organization/list 分页钳制 ──────────────────────


def _run_machine_list(page, page_size):
    db = MagicMock()
    admin = _user(1, role="admin", su=False)
    service = MagicMock()
    service.get_organization_pass_codes.return_value = ([], 0)
    with patch.object(mc_mod, "MachineCodeService", return_value=service):
        asyncio.run(
            mc_mod.list_organization_pass_codes(
                organization_id=None, status=None, page=page,
                page_size=page_size, db=db, current_user=admin,
            )
        )
    return service.get_organization_pass_codes.call_args


def test_machine_code_org_list_clamps_negative_page_size():
    """limit=-1 在 SQLite 下等于不限量（pass_code 批量暴露面）→ 必须钳制为 1。"""
    call = _run_machine_list(page=1, page_size=-1)
    assert call.kwargs["skip"] == 0
    assert call.kwargs["limit"] == 1


def test_machine_code_org_list_clamps_oversized_page_size():
    call = _run_machine_list(page=2, page_size=10 ** 6)
    assert call.kwargs["limit"] == 200
    assert call.kwargs["skip"] == 10 ** 6

# ── 6. 数据包列表：未绑定组织的全局超管回退（导出可用但列表恒空）─────────


def _run_data_package_list(current_user, service, perm):
    import app.api.v1.data.data.data_packages as dp

    return asyncio.run(
        dp.list_data_packages(
            page=1, page_size=20, org_id=None, status_filter=None,
            type_filter=None, current_user=current_user,
            service=service, permission_service=perm,
        )
    )


def test_data_package_list_orgless_superuser_falls_back_to_first_org():
    """未绑定组织的全局超管：导出走首组织回退，列表必须同口径（否则导出物不可见）。"""
    import app.api.v1.data.data.data_packages as dp

    service = MagicMock()
    service.get_packages_by_org.return_value = []
    service.count_packages_by_org.return_value = 0
    perm = MagicMock()
    perm.can_access_organization.return_value = True
    user = _user(1, role="super_admin", su=True)
    user.organization_id = None

    with patch.object(dp, "_get_first_active_org", return_value=7):
        res = _run_data_package_list(user, service, perm)

    assert res.total == 0
    service.get_packages_by_org.assert_called_once()
    assert service.get_packages_by_org.call_args[0][0] == 7


def test_data_package_list_orgless_normal_user_stays_empty():
    """普通用户/无组织用户不得借回退跨组织查看数据包。"""
    service = MagicMock()
    perm = MagicMock()
    perm.can_access_organization.return_value = True
    user = _user(2, role="user", su=False)
    user.organization_id = None

    res = _run_data_package_list(user, service, perm)

    assert res.total == 0
    service.get_packages_by_org.assert_not_called()
