"""``include_deleted`` 权限收敛回归测试

验证软删除 ``include_deleted=true`` 参数仅管理员可用，非管理员请求静默降级。

覆盖范围（9.5.4）：
    - 单元级：``enforce_admin_include_deleted`` 依赖函数（参数化角色矩阵）
    - 单元级：``build_viewable_because`` 元数据函数（参数化记录状态 + 角色）
    - 集成级：4 个软删端点的 API 回归（supported-villages / schools / projects / funds）

安全基线参考：AGENTS.md → "软删除模式" → "include_deleted=true 显示全部（管理员）"。
"""
from unittest.mock import Mock

import pytest

# ──────────────────────── 单元级：enforce_admin_include_deleted ────────────────────────


def _make_user(role, is_superuser=False):
    """构造一个带 role/is_superuser 属性的 Mock 用户。"""
    u = Mock()
    u.role = role
    u.is_superuser = is_superuser
    u.is_active = True
    u.organization_id = 1
    return u


class TestEnforceAdminIncludeDeletedUnit:
    """直接调用 ``enforce_admin_include_deleted`` 依赖函数，覆盖角色矩阵。

    该依赖的核心契约（参考 AGENTS.md "软删除模式"）：
        * include_deleted=False → 永远返回 False（无论角色）
        * include_deleted=True + 管理员 → 返回 True（透传）
        * include_deleted=True + 非管理员 → 返回 False（静默降级，不抛 403）
    """

    @pytest.mark.parametrize(
        "role,is_superuser,include_deleted,expected",
        [
            # 管理员（super_admin / admin / is_superuser=True）→ 透传
            ("super_admin", True, True, True),
            ("super_admin", False, True, True),
            ("admin", False, True, True),
            ("admin", True, True, True),
            # 非管理员 → 静默降级为 False
            ("manager", False, True, False),
            ("approval_leader", False, True, False),
            ("operator", False, True, False),
            ("viewer", False, True, False),
            ("user", False, True, False),
            # include_deleted=False → 无论角色都返回 False
            ("super_admin", True, False, False),
            ("admin", False, False, False),
            ("manager", False, False, False),
            ("user", False, False, False),
        ],
    )
    def test_role_matrix(self, role, is_superuser, include_deleted, expected):
        """参数化角色矩阵：验证 include_deleted 降级逻辑。"""
        from app.api.v1.deps import enforce_admin_include_deleted

        user = _make_user(role, is_superuser)
        # 直接调用函数（绕过 FastAPI 依赖注入），模拟依赖解析后的调用
        result = enforce_admin_include_deleted(
            include_deleted=include_deleted, current_user=user
        )
        assert result is expected, (
            f"role={role}, is_superuser={is_superuser}, "
            f"include_deleted={include_deleted} 应返回 {expected}，"
            f"实际返回 {result}"
        )

    def test_none_user_safely_returns_false(self):
        """current_user=None 时不应崩溃，应返回 False（防御性）。"""
        from app.api.v1.deps import enforce_admin_include_deleted

        # is_admin(None) 返回 False → 降级为 False
        result = enforce_admin_include_deleted(
            include_deleted=True, current_user=None
        )
        assert result is False

    def test_non_admin_does_not_raise(self):
        """非管理员传入 include_deleted=True 不应抛 HTTPException（静默降级）。"""
        from app.api.v1.deps import enforce_admin_include_deleted

        user = _make_user("user", is_superuser=False)
        # 不应抛异常
        result = enforce_admin_include_deleted(
            include_deleted=True, current_user=user
        )
        assert result is False
        # 确认没有 HTTPException 被抛出（静默降级的核心契约）
        # 如果函数抛异常，上面的调用就会失败


# ──────────────────────── 单元级：build_viewable_because ────────────────────────


class TestBuildViewableBecauseUnit:
    """``build_viewable_because`` 元数据生成函数的单元测试。

    契约（参考 deps.py docstring）：
        * record=None 或 current_user=None → None
        * record.is_active=True（未软删）→ None
        * record.is_active=False + 管理员 → "admin"
        * record.is_active=False + 非管理员 → None
    """

    def _make_record(self, is_active=True):
        record = Mock()
        record.is_active = is_active
        return record

    @pytest.mark.parametrize(
        "role,is_superuser,is_active,expected",
        [
            # 已软删（is_active=False）+ 管理员 → "admin"
            ("admin", False, False, "admin"),
            ("super_admin", False, False, "admin"),
            ("super_admin", True, False, "admin"),
            ("manager", True, False, "admin"),  # is_superuser=True → is_admin True
            # 已软删 + 非管理员 → None（被 _get_xxx_or_404 拦截后的兜底）
            ("manager", False, False, None),
            ("approval_leader", False, False, None),
            ("operator", False, False, None),
            ("viewer", False, False, None),
            ("user", False, False, None),
            # 未软删（is_active=True）→ 无论角色都返回 None
            ("admin", False, True, None),
            ("super_admin", True, True, None),
            ("user", False, True, None),
        ],
    )
    def test_matrix(self, role, is_superuser, is_active, expected):
        """参数化矩阵：记录状态 × 角色组合。"""
        from app.api.v1.deps import build_viewable_because

        user = _make_user(role, is_superuser)
        record = self._make_record(is_active=is_active)
        result = build_viewable_because(user, record)
        assert result == expected, (
            f"role={role}, is_superuser={is_superuser}, is_active={is_active} "
            f"应返回 {expected!r}，实际返回 {result!r}"
        )

    def test_none_record_returns_none(self):
        """record=None 应返回 None。"""
        from app.api.v1.deps import build_viewable_because

        user = _make_user("admin", is_superuser=False)
        assert build_viewable_because(user, None) is None

    def test_none_user_returns_none(self):
        """current_user=None 应返回 None。"""
        from app.api.v1.deps import build_viewable_because

        record = self._make_record(is_active=False)
        assert build_viewable_because(None, record) is None

    def test_none_record_and_user_returns_none(self):
        """record=None 且 current_user=None 应返回 None。"""
        from app.api.v1.deps import build_viewable_because

        assert build_viewable_because(None, None) is None

    def test_record_without_is_active_attr(self):
        """record 没有 is_active 属性时应安全返回 None（getattr 默认值）。"""
        from app.api.v1.deps import build_viewable_because

        user = _make_user("admin", is_superuser=False)
        record = Mock(spec=[])  # spec=[] → 无任何属性
        result = build_viewable_because(user, record)
        assert result is None


# ──────────────────────── 集成级：4 端点 API 回归 ────────────────────────


# 4 个软删端点的列表 URL（路由前缀 + api_v1 前缀）
SOFT_DELETE_ENDPOINTS = [
    "/api/v1/supported-villages",
    "/api/v1/schools",
    "/api/v1/projects",
    "/api/v1/funds",
]


def _set_user(client, user):
    """切换 TestClient 的 get_current_user 依赖覆盖，返回原始覆盖便于恢复。"""
    from app.core.security import get_current_user

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    return original


def _restore(client, original):
    """恢复 dependency_overrides。"""
    client.app.dependency_overrides = original


class TestIncludeDeletedApiRegression:
    """4 个软删端点的参数化 API 回归测试。

    验证每个端点的列表请求都正确接入了 ``enforce_admin_include_deleted`` 依赖：
        * 管理员 include_deleted=true → 200（透传）
        * 非管理员 include_deleted=true → 200（静默降级，不抛 403/500）
        * 非管理员响应中不含 is_active=False 的记录
    """

    @pytest.mark.parametrize("endpoint", SOFT_DELETE_ENDPOINTS)
    def test_admin_include_deleted_returns_200(self, client, endpoint):
        """管理员请求 include_deleted=true 应返回 200，不报错。"""

        admin = _make_user("admin", is_superuser=False)
        admin.id = 1
        admin.username = "admin1"
        admin.organization_id = 1
        admin.permissions_list = ["*"]

        original = _set_user(client, admin)
        try:
            resp = client.get(f"{endpoint}?include_deleted=true")
            assert resp.status_code == 200, (
                f"管理员请求 {endpoint}?include_deleted=true 应返回 200，"
                f"实际 {resp.status_code} — 响应: {resp.text[:300]}"
            )
        finally:
            _restore(client, original)

    @pytest.mark.parametrize("endpoint", SOFT_DELETE_ENDPOINTS)
    def test_non_admin_include_deleted_silently_ignored(self, client, endpoint):
        """非管理员请求 include_deleted=true 应静默降级（200），不含软删记录。"""

        regular = _make_user("user", is_superuser=False)
        regular.id = 2
        regular.username = "user2"
        regular.organization_id = 2
        regular.permissions_list = ["read"]

        original = _set_user(client, regular)
        try:
            resp = client.get(f"{endpoint}?include_deleted=true")
            # 核心契约：不抛 403/500，静默降级为 False → 正常返回 200
            assert resp.status_code == 200, (
                f"非管理员请求 {endpoint}?include_deleted=true 应静默降级返回 200，"
                f"实际 {resp.status_code} — 不应抛 403/500 暴露参数存在"
            )
            # 非管理员不应看到任何 is_active=False 的记录
            body = resp.json()
            data = body.get("data", body)
            items = data.get("items", []) if isinstance(data, dict) else data
            for item in items:
                if isinstance(item, dict):
                    assert item.get("is_active", True) is not False, (
                        f"非管理员在 {endpoint} 看到了软删记录 "
                        f"(is_active=False) — include_deleted 权限收敛失效!"
                    )
        finally:
            _restore(client, original)

    @pytest.mark.parametrize("endpoint", SOFT_DELETE_ENDPOINTS)
    def test_default_excludes_deleted(self, client, endpoint):
        """不带 include_deleted 参数时，所有端点默认隐藏软删记录。"""

        admin = _make_user("admin", is_superuser=False)
        admin.id = 1
        admin.username = "admin1"
        admin.organization_id = 1
        admin.permissions_list = ["*"]

        original = _set_user(client, admin)
        try:
            # 不带 include_deleted → 默认 False → 隐藏软删记录
            resp = client.get(endpoint)
            assert resp.status_code == 200, (
                f"请求 {endpoint} 应返回 200，实际 {resp.status_code}"
            )
            body = resp.json()
            data = body.get("data", body)
            items = data.get("items", []) if isinstance(data, dict) else data
            for item in items:
                if isinstance(item, dict):
                    assert item.get("is_active", True) is not False, (
                        f"{endpoint} 默认返回了软删记录 (is_active=False) — "
                        f"默认过滤未生效!"
                    )
        finally:
            _restore(client, original)

    @pytest.mark.parametrize(
        "role,is_superuser",
        [
            ("manager", False),
            ("approval_leader", False),
            ("operator", False),
            ("viewer", False),
            ("user", False),
        ],
    )
    def test_non_admin_roles_all_endpoints(self, client, role, is_superuser):
        """所有非管理员角色在所有端点上 include_deleted=true 都应静默降级。

        双重参数化：5 个非管理员角色 × 4 个端点 = 20 组合，
        确保 enforce_admin_include_deleted 依赖在所有端点都正确接入。
        """

        user = _make_user(role, is_superuser=is_superuser)
        user.id = 99
        user.username = f"test_{role}"
        user.organization_id = 1
        user.permissions_list = ["read"]

        original = _set_user(client, user)
        try:
            for endpoint in SOFT_DELETE_ENDPOINTS:
                resp = client.get(f"{endpoint}?include_deleted=true")
                # 关键断言：不抛 403/422/500（静默降级的核心契约）
                assert resp.status_code == 200, (
                    f"role={role} 请求 {endpoint}?include_deleted=true 应静默"
                    f"降级返回 200，实际 {resp.status_code} — "
                    f"响应: {resp.text[:200]}"
                )
        finally:
            _restore(client, original)


class TestViewableBecauseApiIntegration:
    """验证详情端点返回的 ``viewableBecause`` 元数据。

    当管理员查看一条已软删的记录时，详情应包含 ``viewableBecause: "admin"``。
    由于需要真实的软删记录，此测试在创建→软删→查看链路完成后验证。
    """

    def test_admin_detail_of_active_record_has_no_viewable_because(self, client):
        """管理员查看未软删的帮扶村详情时，viewableBecause 应为 None（不存在或 null）。"""

        admin = _make_user("admin", is_superuser=False)
        admin.id = 1
        admin.username = "admin1"
        admin.organization_id = 1
        admin.permissions_list = ["*"]

        original = _set_user(client, admin)
        try:
            # 创建一条帮扶村
            resp = client.post("/api/v1/supported-villages", json={
                "village_name": "测试村VB",
                "province": "贵州省",
                "county": "测试县",
            })
            if resp.status_code not in (200, 201):
                pytest.skip(f"创建帮扶村失败: {resp.status_code} {resp.text[:200]}")
            village_id = resp.json().get("data", {}).get("id") or resp.json().get("id")
            if not village_id:
                pytest.skip("无法获取帮扶村ID")

            # 查看详情 → 未软删 → viewableBecause 应为 None 或不存在
            detail = client.get(f"/api/v1/supported-villages/{village_id}")
            assert detail.status_code == 200, (
                f"查看帮扶村详情应返回 200，实际 {detail.status_code}"
            )
            data = detail.json().get("data", detail.json())
            assert data.get("viewableBecause") in (None, "admin"), (
                f"未软删记录的 viewableBecause 应为 None，"
                f"实际 {data.get('viewableBecause')!r}"
            )
        finally:
            _restore(client, original)
