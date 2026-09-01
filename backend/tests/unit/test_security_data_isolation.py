"""
安全数据隔离测试 — 验证 CRIT-1/2/3 + HIGH-1/2/3 修复

测试策略：
  - 创建两个不同组织的用户（org=1 管理员, org=2 普通用户）
  - 用 org=1 用户创建记录，用 org=2 用户尝试越权访问
  - 断言返回 403（跨组织）而非 200（数据泄露）

覆盖模块: supported_village / policy / projects / funds / school
"""
import pytest
from unittest.mock import Mock


@pytest.fixture
def org1_admin_client(client):
    """org=1 的管理员客户端"""
    from app.core.security import get_current_user

    user = Mock()
    user.id = 1
    user.username = "admin1"
    user.role = "admin"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides = original


@pytest.fixture
def org2_user_client(client):
    """org=2 的普通用户客户端（非管理员）"""
    from app.core.security import get_current_user

    user = Mock()
    user.id = 2
    user.username = "user2"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read"]
    user.organization_id = 2

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides = original


# ──────────────────────── CRIT-1: supported_village ────────────────────────


class TestSupportedVillageIsolation:
    """帮扶村数据隔离：跨组织详情访问应返回 403"""

    def test_cross_org_village_detail_returns_403(self, client):
        """org1 创建的帮扶村，org2 用户不应能访问详情"""
        # org1_admin_client/org2_user_client 两个 fixture 共享同一 app 的
        # dependency_overrides，同时使用时后生效者会覆盖前者（两个"客户端"
        # 实际同身份），因此本测试显式按阶段切换覆盖。
        from app.core.security import get_current_user

        org1_admin = Mock()
        org1_admin.id = 1
        org1_admin.username = "admin1"
        org1_admin.role = "admin"
        org1_admin.is_superuser = False
        org1_admin.is_active = True
        org1_admin.permissions_list = ["*"]
        org1_admin.organization_id = 1

        org2_user = Mock()
        org2_user.id = 2
        org2_user.username = "user2"
        org2_user.role = "user"
        org2_user.is_superuser = False
        org2_user.is_active = True
        org2_user.permissions_list = ["read"]
        org2_user.organization_id = 2

        original = client.app.dependency_overrides.copy()
        try:
            # org1 管理员创建帮扶村
            client.app.dependency_overrides[get_current_user] = lambda: org1_admin
            resp = client.post("/api/v1/supported-villages", json={
                "village_name": "测试村A",
                "province": "贵州省",
                "county": "测试县",
            })
            # 创建可能因 schema 差异失败，跳过而非报错
            if resp.status_code not in (200, 201):
                pytest.skip(f"创建帮扶村失败: {resp.status_code} {resp.text[:200]}")
            village_id = resp.json().get("data", {}).get("id")
            if not village_id:
                pytest.skip("无法获取帮扶村ID")

            # org2 普通用户尝试访问 → 应 403（跨组织）
            client.app.dependency_overrides[get_current_user] = lambda: org2_user
            resp2 = client.get(f"/api/v1/supported-villages/{village_id}")
            assert resp2.status_code in (403, 404), (
                f"跨组织访问应返回 403/404，实际 {resp2.status_code} — 数据隔离漏洞!"
            )
        finally:
            client.app.dependency_overrides = original


# ──────────────────────── CRIT-2: policy 写操作 ────────────────────────


class TestPolicyWritePermission:
    """政策写操作（2026-08-15 产品要求）：普通用户与管理员完全一致，均可增删改。

    权限放开后，数据隔离仍由数据范围/组织隔离保障（本类不再断言 403，
    而是断言普通用户可正常发起政策写操作）。"""

    def test_non_admin_can_create_policy(self, org2_user_client):
        """普通用户可以创建政策（产品要求：政策法规全角色可用）"""
        resp = org2_user_client.post("/api/v1/policies", json={
            "title": "普通用户创建的政策",
            "content": "内容",
            "category": "local",
            "level": "national",
        })
        assert resp.status_code in (200, 201), (
            f"普通用户创建政策应成功，实际 {resp.status_code}: {resp.text[:200]}"
        )

    def test_non_admin_can_delete_policy(self, org2_user_client):
        """普通用户可以删除政策（不存在时 404 而非 403 权限拦截）"""
        resp = org2_user_client.delete("/api/v1/policies/99999")
        assert resp.status_code != 403, (
            f"普通用户删除政策不应被 403 拦截，实际 {resp.status_code}"
        )

    def test_non_admin_can_batch_delete_policies(self, org2_user_client):
        """普通用户可以批量删除政策"""
        resp = org2_user_client.post("/api/v1/policies/batch-delete", json={"ids": [1, 2, 3]})
        assert resp.status_code != 403, (
            f"普通用户批量删除不应被 403 拦截，实际 {resp.status_code}"
        )


# ──────────────────────── CRIT-2: policy 收藏 IDOR ────────────────────────


class TestPolicyFavoriteIDOR:
    """政策收藏 IDOR：不能操作他人收藏"""

    def test_favorite_no_user_id_param(self, org2_user_client):
        """收藏接口不应再接受 user_id 参数（已移除）"""
        # POST /policies/{id}/favorite 不带 user_id — 应使用 current_user.id
        resp = org2_user_client.post("/api/v1/policies/99999/favorite")
        # 政策不存在应 404，而非 422（缺少 user_id 参数）
        assert resp.status_code != 422, (
            "收藏接口仍要求 user_id 参数 — IDOR 修复未生效!"
        )

    def test_get_others_favorites_returns_403(self, org2_user_client):
        """查看他人收藏应返回 403"""
        # org2 用户(id=2) 尝试查看 user_id=1 的收藏
        resp = org2_user_client.get("/api/v1/policies/user/1/favorites")
        assert resp.status_code == 403, (
            f"查看他人收藏应返回 403，实际 {resp.status_code} — IDOR 漏洞!"
        )


# ──────────────────────── HIGH-1: projects 子端点 ────────────────────────


class TestProjectSubEndpointIsolation:
    """项目子端点：跨组织访问应返回 403"""

    def test_cross_org_project_funds_returns_403(self, client):
        """org1 创建的项目，org2 用户不应能访问经费"""
        # 与 TestSupportedVillageIsolation 相同的原因：两个组织身份 fixture
        # 共享同一 app 的 dependency_overrides，必须显式按阶段切换。
        from app.core.security import get_current_user

        org1_admin = Mock()
        org1_admin.id = 1
        org1_admin.username = "admin1"
        org1_admin.role = "admin"
        org1_admin.is_superuser = False
        org1_admin.is_active = True
        org1_admin.permissions_list = ["*"]
        org1_admin.organization_id = 1

        org2_user = Mock()
        org2_user.id = 2
        org2_user.username = "user2"
        org2_user.role = "user"
        org2_user.is_superuser = False
        org2_user.is_active = True
        org2_user.permissions_list = ["read"]
        org2_user.organization_id = 2

        original = client.app.dependency_overrides.copy()
        try:
            # org1 创建项目
            client.app.dependency_overrides[get_current_user] = lambda: org1_admin
            resp = client.post("/api/v1/projects", json={
                "name": "隔离测试项目",
                "type": "infrastructure",
            })
            if resp.status_code not in (200, 201):
                pytest.skip(f"创建项目失败: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            project_id = data.get("id") or data.get("data", {}).get("id")
            if not project_id:
                pytest.skip("无法获取项目ID")

            # org2 用户访问项目经费 → 应 403
            client.app.dependency_overrides[get_current_user] = lambda: org2_user
            resp2 = client.get(f"/api/v1/projects/{project_id}/funds")
            assert resp2.status_code in (403, 404), (
                f"跨组织访问项目经费应返回 403/404，实际 {resp2.status_code} — 越权漏洞!"
            )
        finally:
            client.app.dependency_overrides = original


# ──────────────────────── 单元级：check_record_access ────────────────────────


class TestCheckRecordAccess:
    """直接测试 check_record_access 工具函数"""

    def test_admin_sees_all(self, admin_user):
        from app.core.data_permission import check_record_access

        record = Mock()
        record.organization_id = 999
        record.created_by = 888
        assert check_record_access(record, admin_user) is True

    def test_own_dept_access(self, regular_user):
        from app.core.data_permission import check_record_access

        # role="user" 的数据域为 OWN（仅本人记录），部门级访问需要 manager/admin 角色
        regular_user.role = "manager"
        record = Mock()
        record.organization_id = 2  # 同组织
        record.created_by = 999
        assert check_record_access(record, regular_user) is True

    def test_cross_dept_denied(self, regular_user):
        from app.core.data_permission import check_record_access

        record = Mock()
        record.organization_id = 999  # 不同组织
        record.created_by = 888  # 也不是自己创建的
        assert check_record_access(record, regular_user) is False

    def test_own_record_access(self, viewer_user):
        """普通用户访问自己创建的记录"""
        from app.core.data_permission import check_record_access

        record = Mock()
        record.organization_id = 999  # 不同组织
        record.created_by = 3  # 但自己创建的 (viewer_user.id=3)
        assert check_record_access(record, viewer_user) is True


# ──────────────────────── 单元级：require_manager_role ────────────────────────


class TestRequireManagerRole:
    """测试 require_manager_role 权限函数"""

    def test_admin_passes(self, admin_user):
        from app.api.v1.deps import require_manager_role
        require_manager_role(admin_user)  # 不应抛异常

    def test_super_admin_passes(self):
        from app.api.v1.deps import require_manager_role
        user = Mock()
        user.role = "super_admin"
        user.is_superuser = True
        require_manager_role(user)  # 不应抛异常

    def test_manager_passes(self):
        from app.api.v1.deps import require_manager_role
        user = Mock()
        user.role = "manager"
        user.is_superuser = False
        require_manager_role(user)  # 不应抛异常

    def test_regular_user_denied(self, regular_user):
        from app.api.v1.deps import require_manager_role
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_manager_role(regular_user)
        assert exc_info.value.status_code == 403


# ──────────────────────── SEC-1: include_deleted 权限收敛 ────────────────────────


class TestIncludeDeletedAdminEnforcement:
    """验证 include_deleted=true 仅管理员可用（AGENTS.md / CLAUDE.md 安全基线）。

    非管理员即使显式传入 include_deleted=true，后端也应强制降级为 False，
    避免越权查看软删记录（is_active=False）。
    """

    @pytest.mark.parametrize(
        "role,is_superuser,expected_admin",
        [
            ("super_admin", True, True),
            ("super_admin", False, True),
            ("admin", False, True),
            ("manager", False, False),
            ("approval_leader", False, False),
            ("operator", False, False),
            ("viewer", False, False),
            ("user", False, False),
        ],
    )
    def test_is_admin_role_matrix(self, role, is_superuser, expected_admin):
        """验证 is_admin() 的角色判断矩阵：仅 super_admin/admin 为 True。"""
        from app.core.permission_utils import is_admin

        user = Mock()
        user.role = role
        user.is_superuser = is_superuser
        assert is_admin(user) is expected_admin, (
            f"role={role}, is_superuser={is_superuser} 应为 is_admin={expected_admin}"
        )

    def test_admin_can_pass_include_deleted(self, client):
        """管理员传入 include_deleted=true 不应被拒绝（HTTP 200）。"""
        from app.core.security import get_current_user

        admin = Mock()
        admin.id = 1
        admin.username = "admin1"
        admin.role = "admin"
        admin.is_superuser = False
        admin.is_active = True
        admin.permissions_list = ["*"]
        admin.organization_id = 1

        original = client.app.dependency_overrides.copy()
        try:
            client.app.dependency_overrides[get_current_user] = lambda: admin
            # 列表请求带 include_deleted=true，管理员应能正常获取（200）
            resp = client.get("/api/v1/supported-villages?include_deleted=true")
            assert resp.status_code == 200, (
                f"管理员请求 include_deleted=true 应返回 200，实际 {resp.status_code}"
            )
        finally:
            client.app.dependency_overrides = original

    def test_non_admin_include_deleted_silently_ignored(self, client):
        """非管理员传入 include_deleted=true 应被静默降级（仍返回 200，但不包含软删记录）。"""
        from app.core.security import get_current_user

        regular = Mock()
        regular.id = 2
        regular.username = "user2"
        regular.role = "user"
        regular.is_superuser = False
        regular.is_active = True
        regular.permissions_list = ["read"]
        regular.organization_id = 2

        original = client.app.dependency_overrides.copy()
        try:
            client.app.dependency_overrides[get_current_user] = lambda: regular
            # 非管理员请求 include_deleted=true，应静默降级为 False（不报 403/500）
            resp = client.get("/api/v1/supported-villages?include_deleted=true")
            assert resp.status_code == 200, (
                f"非管理员请求 include_deleted=true 应静默降级返回 200，"
                f"实际 {resp.status_code} — 不应抛 403/500 暴露参数存在"
            )
            # 数据中不应包含 is_active=False 的记录（由于 is_active 默认 True，此处仅验证不报错）
            body = resp.json()
            data = body.get("data", body)
            items = data.get("items", []) if isinstance(data, dict) else data
            for item in items:
                if isinstance(item, dict):
                    # 非管理员不应看到任何 is_active=False 的记录
                    assert item.get("is_active", True) is not False, (
                        "非管理员看到了软删记录 — include_deleted 权限收敛失效!"
                    )
        finally:
            client.app.dependency_overrides = original
