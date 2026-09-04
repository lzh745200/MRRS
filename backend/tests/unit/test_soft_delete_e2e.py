"""端到端软删流程集成测试（9.5.5）

完整链路验证：
    1. 管理员创建帮扶村
    2. 管理员软删帮扶村
    3. 管理员 list?include_deleted=true → 可见软删记录
    4. 管理员详情 → viewableBecause="admin"
    5. 非管理员 list?include_deleted=true → 静默降级，不可见
    6. 非管理员详情 → 403（跨组织数据隔离）

参考安全基线：AGENTS.md → "软删除模式" 章节。
"""
from unittest.mock import Mock


def _make_admin():
    """org=1 管理员用户。"""
    user = Mock()
    user.id = 1
    user.username = "admin1"
    user.role = "admin"
    user.is_superuser = False
    user.is_active = True
    user.organization_id = 1
    user.permissions_list = ["*"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _make_regular():
    """org=2 普通用户。"""
    user = Mock()
    user.id = 2
    user.username = "user2"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.organization_id = 2
    user.permissions_list = ["read"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _set_user(client, user):
    """切换 TestClient 的 get_current_user 依赖覆盖，返回原始覆盖便于恢复。"""
    from app.core.security import get_current_user

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    return original


def _restore(client, original):
    """恢复 dependency_overrides。"""
    client.app.dependency_overrides = original


class TestSoftDeleteE2E:
    """端到端软删流程：创建→软删→管理员可见→普通用户不可见。

    使用 supported-villages 端点作为代表（4 个软删端点共用同一
    enforce_admin_include_deleted 依赖，权限收敛逻辑已在 9.5.4
    参数化回归测试中覆盖）。
    """

    def test_full_soft_delete_lifecycle(self, client):
        """完整软删生命周期：创建→软删→管理员可见→普通用户不可见。"""

        from app.core.security import get_current_user

        admin = _make_admin()
        regular = _make_regular()
        original = client.app.dependency_overrides.copy()

        try:
            # ── 阶段 1：管理员创建帮扶村 ──
            client.app.dependency_overrides[get_current_user] = lambda: admin
            resp_create = client.post("/api/v1/supported-villages", json={
                "village_name": "E2E软删测试村",
                "province": "贵州省",
                "county": "测试县",
            })
            assert resp_create.status_code in (200, 201), (
                f"前置条件失败：创建帮扶村应成功，实际 {resp_create.status_code} "
                f"{resp_create.text[:200]}"
            )
            village_id = (
                resp_create.json().get("data", {}).get("id")
                or resp_create.json().get("id")
            )
            assert village_id, f"前置条件失败：无法获取帮扶村ID，响应 {resp_create.text[:200]}"

            # ── 阶段 2：验证未软删时管理员可见 ──
            resp_list_before = client.get(
                "/api/v1/supported-villages?include_deleted=true"
            )
            assert resp_list_before.status_code == 200
            before_data = resp_list_before.json().get("data", {})
            before_items = before_data.get("items", []) if isinstance(before_data, dict) else before_data
            # 管理员应能看到新建的帮扶村
            found_before = any(
                item.get("id") == village_id
                for item in before_items
                if isinstance(item, dict)
            )
            assert found_before, (
                f"管理员应在列表中看到新建的帮扶村 (id={village_id})"
            )

            # ── 阶段 3：管理员软删帮扶村 ──
            resp_delete = client.delete(f"/api/v1/supported-villages/{village_id}")
            assert resp_delete.status_code == 200, (
                f"软删应返回 200，实际 {resp_delete.status_code} — "
                f"{resp_delete.text[:200]}"
            )

            # ── 阶段 4：管理员 list?include_deleted=true → 可见软删记录 ──
            resp_list_deleted = client.get(
                "/api/v1/supported-villages?include_deleted=true"
            )
            assert resp_list_deleted.status_code == 200
            deleted_data = resp_list_deleted.json().get("data", {})
            deleted_items = (
                deleted_data.get("items", [])
                if isinstance(deleted_data, dict)
                else deleted_data
            )
            # 管理员带 include_deleted=true 应能看到软删记录
            found_deleted = any(
                item.get("id") == village_id
                for item in deleted_items
                if isinstance(item, dict)
            )
            assert found_deleted, (
                "管理员 list?include_deleted=true 应包含软删记录"
            )
            # 确认该记录 is_active=False
            for item in deleted_items:
                if isinstance(item, dict) and item.get("id") == village_id:
                    assert item.get("is_active") is False or \
                        item.get("isActive") is False or \
                        item.get("isDeleted") is True, (
                        "软删记录应有 is_active=False / isDeleted=True 标记"
                    )

            # ── 阶段 5：管理员 list（不带 include_deleted）→ 不见软删记录 ──
            resp_list_normal = client.get("/api/v1/supported-villages")
            assert resp_list_normal.status_code == 200
            normal_data = resp_list_normal.json().get("data", {})
            normal_items = (
                normal_data.get("items", [])
                if isinstance(normal_data, dict)
                else normal_data
            )
            found_normal = any(
                item.get("id") == village_id
                for item in normal_items
                if isinstance(item, dict)
            )
            assert not found_normal, (
                "管理员不带 include_deleted 时不应看到软删记录 — "
                "默认过滤未生效!"
            )

            # ── 阶段 6：管理员详情 → viewableBecause="admin" ──
            resp_detail = client.get(
                f"/api/v1/supported-villages/{village_id}"
            )
            assert resp_detail.status_code == 200, (
                f"管理员查看软删记录详情应返回 200，"
                f"实际 {resp_detail.status_code}"
            )
            detail_data = resp_detail.json().get("data", {})
            assert detail_data.get("viewableBecause") == "admin", (
                f"管理员查看软删记录详情应返回 viewableBecause='admin'，"
                f"实际 {detail_data.get('viewableBecause')!r}"
            )

            # ── 阶段 7：非管理员 list?include_deleted=true → 静默降级 ──
            client.app.dependency_overrides[get_current_user] = lambda: regular
            resp_list_user = client.get(
                "/api/v1/supported-villages?include_deleted=true"
            )
            assert resp_list_user.status_code == 200, (
                "非管理员 include_deleted=true 应静默降级返回 200，"
                f"实际 {resp_list_user.status_code} — 不应抛 403/500"
            )
            user_data = resp_list_user.json().get("data", {})
            user_items = (
                user_data.get("items", [])
                if isinstance(user_data, dict)
                else user_data
            )
            # 非管理员不应看到该软删记录（权限降级 + 数据隔离）
            found_user = any(
                item.get("id") == village_id
                for item in user_items
                if isinstance(item, dict)
            )
            assert not found_user, (
                "非管理员不应看到软删记录 — include_deleted 权限收敛"
                "或数据隔离失效!"
            )

            # ── 阶段 8：非管理员详情 → 403（跨组织数据隔离）──
            resp_detail_user = client.get(
                f"/api/v1/supported-villages/{village_id}"
            )
            assert resp_detail_user.status_code == 403, (
                f"非管理员跨组织访问软删记录详情应返回 403，"
                f"实际 {resp_detail_user.status_code} — 数据隔离漏洞!"
            )

        finally:
            client.app.dependency_overrides = original


class TestSoftDeleteE2EFunds:
    """经费模块软删流程验证。

    funds 端点使用 require_manager_role 来限制写操作（与 supported-villages 不同），
    但 include_deleted 权限收敛逻辑完全一致（共用 enforce_admin_include_deleted 依赖）。
    本测试验证 funds 软删链路在管理员身份下正常工作。
    """

    def test_admin_funds_soft_delete_lifecycle(self, client):
        """管理员经费软删流程：创建→软删→include_deleted 可见→默认不可见。"""

        from app.core.security import get_current_user

        admin = _make_admin()
        original = client.app.dependency_overrides.copy()

        try:
            client.app.dependency_overrides[get_current_user] = lambda: admin

            # 尝试创建一条经费记录
            resp_create = client.post("/api/v1/funds", json={
                "name": "E2E软删测试经费",
                "amount": 10000.00,
                "fund_type": "support",
                "fund_source": "military",
            })
            assert resp_create.status_code in (200, 201), (
                f"前置条件失败：创建经费应成功，实际 {resp_create.status_code} "
                f"{resp_create.text[:200]}"
            )
            fund_id = (
                resp_create.json().get("data", {}).get("id")
                or resp_create.json().get("id")
            )
            assert fund_id, f"前置条件失败：无法获取经费ID，响应 {resp_create.text[:200]}"

            # 软删
            resp_delete = client.delete(f"/api/v1/funds/{fund_id}")
            if resp_delete.status_code != 200:
                # 某些模块可能返回 204 或其他状态码
                assert resp_delete.status_code in (200, 204), (
                    f"软删经费应返回 200/204，"
                    f"实际 {resp_delete.status_code} — {resp_delete.text[:200]}"
                )

            # 管理员 include_deleted=true → 可见
            resp_list = client.get("/api/v1/funds?include_deleted=true")
            assert resp_list.status_code == 200
            list_data = resp_list.json().get("data", {})
            list_items = (
                list_data.get("items", [])
                if isinstance(list_data, dict)
                else list_data
            )
            found = any(
                item.get("id") == fund_id
                for item in list_items
                if isinstance(item, dict)
            )
            assert found, "管理员 funds?include_deleted=true 应包含软删记录"

            # 管理员不带 include_deleted → 不可见
            resp_normal = client.get("/api/v1/funds")
            assert resp_normal.status_code == 200
            normal_data = resp_normal.json().get("data", {})
            normal_items = (
                normal_data.get("items", [])
                if isinstance(normal_data, dict)
                else normal_data
            )
            found_normal = any(
                item.get("id") == fund_id
                for item in normal_items
                if isinstance(item, dict)
            )
            assert not found_normal, (
                "管理员 funds 不带 include_deleted 时不应看到软删记录"
            )

            # 详情 → viewableBecause="admin"
            resp_detail = client.get(f"/api/v1/funds/{fund_id}")
            assert resp_detail.status_code == 200
            detail_data = resp_detail.json().get("data", {})
            assert detail_data.get("viewableBecause") == "admin", (
                f"管理员查看软删经费详情应返回 viewableBecause='admin'，"
                f"实际 {detail_data.get('viewableBecause')!r}"
            )

        finally:
            client.app.dependency_overrides = original
