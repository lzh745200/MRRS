"""supported_village.py 软删路径覆盖率测试（9.5.6）

补充覆盖 delete / batch-delete / detail 端点的边界场景：
    - 批量删除空 ID 列表 → 400
    - 批量删除有效 ID → 成功
    - 批量删除含跨组织 ID → 仅删本组织记录（数据隔离）
    - 删除不存在的帮扶村 → 404
    - 跨组织删除 → 403
    - 查看不存在的帮扶村详情 → 404
    - 跨组织查看详情 → 403

参考：AGENTS.md → "软删除模式" → "Cross-org access returns 403 (not 404)"
"""
import pytest
from unittest.mock import Mock

from app.core.security import hash_password

# 批量删除二次确认测试密码（模块级计算一次）
_BATCH_PW = "Smoke@123456"
_BATCH_PW_HASH = hash_password(_BATCH_PW)


def _make_user(role="admin", is_superuser=False, org_id=1):
    """构造用户 Mock。"""
    user = Mock()
    user.id = 1
    user.username = f"test_{role}"
    user.role = role
    user.is_superuser = is_superuser
    user.is_active = True
    user.organization_id = org_id
    user.permissions_list = ["*"]
    user.failed_login_count = 0
    user.locked_until = None
    user.hashed_password = _BATCH_PW_HASH
    return user


def _set_user(client, user):
    """切换 TestClient 的 get_current_user 依赖覆盖，返回原始覆盖。"""
    from app.core.security import get_current_user

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    return original


def _restore(client, original):
    """恢复 dependency_overrides。"""
    client.app.dependency_overrides = original


def _create_village(client, name="覆盖率测试村"):
    """创建帮扶村并返回 ID，失败时 pytest.skip。"""
    resp = client.post("/api/v1/supported-villages", json={
        "village_name": name,
        "province": "贵州省",
        "county": "测试县",
    })
    if resp.status_code not in (200, 201):
        pytest.skip(f"创建帮扶村失败: {resp.status_code} {resp.text[:200]}")
    village_id = resp.json().get("data", {}).get("id") or resp.json().get("id")
    if not village_id:
        pytest.skip("无法获取帮扶村ID")
    return village_id


class TestBatchDeleteCoverage:
    """批量软删端点的边界场景覆盖。"""

    def test_batch_delete_empty_ids_returns_400(self, client):
        """批量删除空 ID 列表应返回 400。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            resp = client.post("/api/v1/supported-villages/batch-delete", json={"ids": []})
            assert resp.status_code == 400, (
                f"空 ID 列表应返回 400，实际 {resp.status_code}"
            )
        finally:
            _restore(client, original)

    def test_batch_delete_valid_ids(self, client):
        """批量删除有效 ID 应成功。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            vid1 = _create_village(client, "批量删除测试村A")
            vid2 = _create_village(client, "批量删除测试村B")

            resp = client.post(
                "/api/v1/supported-villages/batch-delete",
                json={"ids": [vid1, vid2], "confirm_password": _BATCH_PW},
            )
            assert resp.status_code == 200, (
                f"批量删除应返回 200，实际 {resp.status_code}"
            )
            assert "已删除" in resp.json().get("message", "")

            # 验证记录已被软删（管理员 include_deleted=true 可见）
            resp_list = client.get("/api/v1/supported-villages?include_deleted=true")
            assert resp_list.status_code == 200
            items = resp_list.json().get("data", {}).get("items", [])
            for vid in [vid1, vid2]:
                found = any(item.get("id") == vid for item in items if isinstance(item, dict))
                assert found, f"软删记录 {vid} 应在 include_deleted=true 列表中可见"
        finally:
            _restore(client, original)

    def test_batch_delete_cross_org_only_deletes_own(self, client):
        """批量删除含跨组织 ID 时，仅删本组织记录（数据隔离）。

        使用 role="user"（OWN 数据域：仅本人记录），确保跨组织记录被过滤。
        admin 角色的数据域为 OWN_DEPT，在某些配置下可能包含跨组织记录。
        """
        if client is None:
            pytest.skip("client fixture unavailable")

        from app.core.security import get_current_user

        # org=1 管理员创建
        admin1 = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin1)
        try:
            vid1 = _create_village(client, "跨组织批量删除测试村")

            # org=2 普通用户尝试批量删除 org=1 的记录
            user2 = _make_user(role="user", org_id=2)
            user2.id = 2
            client.app.dependency_overrides[get_current_user] = lambda: user2

            resp = client.post(
                "/api/v1/supported-villages/batch-delete",
                json={"ids": [vid1], "confirm_password": _BATCH_PW},
            )
            # 不应报错（数据隔离过滤后 0 条匹配），但 deleted_count=0
            assert resp.status_code == 200, (
                f"跨组织批量删除应返回 200（0条），实际 {resp.status_code}"
            )
            # 普通用户（OWN 域）不应能删除其他组织/其他人的记录
            assert "已删除 0 条" in resp.json().get("message", ""), (
                f"跨组织批量删除应删除 0 条，实际: {resp.json().get('message')}"
            )

            # 验证记录仍然存在（未被跨组织删除）
            client.app.dependency_overrides[get_current_user] = lambda: admin1
            resp_list = client.get("/api/v1/supported-villages?include_deleted=true")
            items = resp_list.json().get("data", {}).get("items", [])
            found = any(item.get("id") == vid1 for item in items if isinstance(item, dict))
            assert found, "跨组织批量删除不应删除其他组织的记录"
        finally:
            _restore(client, original)


class TestDeleteEdgeCases:
    """单个删除端点的边界场景覆盖。"""

    def test_delete_nonexistent_returns_404(self, client):
        """删除不存在的帮扶村应返回 404。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            resp = client.delete("/api/v1/supported-villages/99999")
            assert resp.status_code == 404, (
                f"删除不存在的帮扶村应返回 404，实际 {resp.status_code}"
            )
        finally:
            _restore(client, original)

    def test_delete_cross_org_returns_403(self, client):
        """跨组织删除应返回 403（数据隔离）。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        from app.core.security import get_current_user

        # org=1 管理员创建
        admin1 = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin1)
        try:
            vid = _create_village(client, "跨组织删除测试村")

            # org=2 用户尝试删除
            user2 = _make_user(role="user", org_id=2)
            user2.id = 2
            client.app.dependency_overrides[get_current_user] = lambda: user2

            resp = client.delete(f"/api/v1/supported-villages/{vid}")
            assert resp.status_code == 403, (
                f"跨组织删除应返回 403，实际 {resp.status_code} — 数据隔离漏洞!"
            )
        finally:
            _restore(client, original)

    def test_delete_then_detail_shows_viewable_because(self, client):
        """软删后管理员查看详情应包含 viewableBecause='admin'。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, "viewableBecause测试村")

            # 软删
            resp_del = client.delete(f"/api/v1/supported-villages/{vid}")
            assert resp_del.status_code == 200

            # 查看详情 → viewableBecause="admin"
            resp_detail = client.get(f"/api/v1/supported-villages/{vid}")
            assert resp_detail.status_code == 200
            data = resp_detail.json().get("data", {})
            assert data.get("viewableBecause") == "admin", (
                f"软删后管理员详情应返回 viewableBecause='admin'，"
                f"实际 {data.get('viewableBecause')!r}"
            )
        finally:
            _restore(client, original)


class TestDetailEdgeCases:
    """详情端点的边界场景覆盖。"""

    def test_detail_nonexistent_returns_404(self, client):
        """查看不存在的帮扶村详情应返回 404。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            resp = client.get("/api/v1/supported-villages/99999")
            assert resp.status_code == 404, (
                f"查看不存在的帮扶村应返回 404，实际 {resp.status_code}"
            )
        finally:
            _restore(client, original)

    def test_detail_cross_org_returns_403(self, client):
        """跨组织查看详情应返回 403（区分"不存在"与"越权"）。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        from app.core.security import get_current_user

        # org=1 管理员创建
        admin1 = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin1)
        try:
            vid = _create_village(client, "跨组织详情测试村")

            # org=2 用户查看 → 403
            user2 = _make_user(role="user", org_id=2)
            user2.id = 2
            client.app.dependency_overrides[get_current_user] = lambda: user2

            resp = client.get(f"/api/v1/supported-villages/{vid}")
            assert resp.status_code == 403, (
                f"跨组织查看详情应返回 403（非 404），实际 {resp.status_code} — "
                f"应区分'不存在'与'越权'"
            )
        finally:
            _restore(client, original)

    def test_detail_active_record_viewable_because_none(self, client):
        """未软删记录的详情 viewableBecause 应为 null。"""
        if client is None:
            pytest.skip("client fixture unavailable")

        admin = _make_user(role="admin", org_id=1)
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, "活跃记录VB测试村")

            resp = client.get(f"/api/v1/supported-villages/{vid}")
            assert resp.status_code == 200
            data = resp.json().get("data", {})
            assert data.get("viewableBecause") is None, (
                f"未软删记录 viewableBecause 应为 null，"
                f"实际 {data.get('viewableBecause')!r}"
            )
        finally:
            _restore(client, original)
