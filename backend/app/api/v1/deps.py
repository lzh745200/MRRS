"""API dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from app.core.database import get_db  # noqa: F401 — 统一从 database.py re-export
from app.core.security import get_current_user  # noqa: F401 — 真实 JWT 认证实现
from app.core.permission_utils import is_admin, is_superuser  # noqa: F401 — re-export
from app.core.constants import ADMIN_ROLES  # noqa: F401 — 单一来源：app.core.constants

# 别名,兼容新代码
get_current_active_user = get_current_user

# 管理角色列表（可执行创建/编辑/删除操作）—— 单一来源 app.core.constants.ADMIN_ROLES
# 注意：manager/approval_leader 是"管理级业务角色"，仅在 require_manager_role 等业务
# 入口经 normalize_role() 归一化后放行管理操作；is_admin()（系统管理层）不含它们。


def require_manager_role(current_user) -> None:
    """要求管理角色，否则返回 403。在 funds / fund_lifecycle 等模块共用。"""
    from app.core.constants import normalize_role

    # 归一化角色：历史角色值（manager/approval_leader）映射为 admin，
    # 保证存量用户的管理权限不因角色精简而降级
    role = normalize_role(getattr(current_user, "role", ""))
    if role not in ADMIN_ROLES and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="权限不足，仅管理员或管理角色可执行此操作")


def require_policy_operator_role(current_user) -> None:
    """政策法规模块操作权限：放行全部已认证角色（admin/user/viewer 均可）。

    产品要求（2026-08-15）：普通用户的政策法规功能与管理员完全一致，
    增删改查全部可用；数据隔离由 filter_by_data_scope 保障。
    """
    # 已通过 get_current_user 认证即放行；显式保留函数便于未来收紧策略
    return None


# 经费管理可操作角色白名单（allowlist）：
# super_admin / admin / user 可完整操作经费流程；viewer 只读；其余角色一律拒绝。
_FUNDS_OPERATOR_ROLES = frozenset({"super_admin", "admin", "user"})


def require_funds_operator_role(current_user) -> None:
    """经费管理操作权限：放行 user 及以上角色（viewer 保持只读）。

    产品要求普通用户（user）可完整操作经费管理（申请/审批/拨付/结算全流程），
    viewer 仍为只读角色；数据隔离由 filter_by_data_scope / check_record_access 保障。

    安全约定（W15 深审 #36）：本函数原为 **denylist**（只拒绝 viewer），而
    normalize_role 对未知角色原样返回、对空值兜底为 user，于是拼写错误、
    脏数据、无角色账号全部被放行 → 等价于给任意非法角色发放经费全流程写权限。
    现改为 **allowlist**（fail-closed）：归一化后不在白名单内一律 403。
    """
    from app.core.constants import normalize_role

    # 显式 is_superuser 标记（历史账号 role 可能不是 super_admin）仍需放行
    if is_superuser(current_user):
        return None

    raw_role = getattr(current_user, "role", None)
    # 空角色没有任何授权基础：normalize_role 会把空值兜底成 user，
    # 沿用该兜底等于让"未分配角色"的账号获得写权限 → 这里直接 fail-closed。
    if not isinstance(raw_role, str) or not raw_role.strip():
        raise HTTPException(status_code=403, detail="权限不足：账号未分配有效角色")

    role = normalize_role(raw_role)
    if role == "viewer":
        raise HTTPException(status_code=403, detail="权限不足，viewer 角色仅可查看经费数据")
    if role not in _FUNDS_OPERATOR_ROLES:
        raise HTTPException(status_code=403, detail="权限不足：当前角色无权操作经费数据")
    return None


def enforce_admin_include_deleted(
    include_deleted: bool = Query(False, description="是否包含已软删的记录（仅管理员可用）"),
    current_user=Depends(get_current_user),
) -> bool:
    """依赖项：非管理员传入 include_deleted=true 时降级为 False，管理员正常透传。

    本依赖统一收敛 4 个软删端点（supported-villages / schools / projects / funds）
    的 `include_deleted` 权限，避免每个端点重复编写 3 行内联判断，同时保证
    非管理员即使显式传入 `include_deleted=true` 也无法越权查看软删记录。

    参考：AGENTS.md → "软删除模式" 章节 → "include_deleted=true 显示全部（管理员）"。

    Returns:
        实际生效的 include_deleted 值（True=显示软删记录，False=隐藏）。
    """
    if include_deleted and not is_admin(current_user):
        # 静默降级：不抛 403 以免暴露参数存在，而是返回 False 让查询走默认过滤
        return False
    return include_deleted


def build_viewable_because(current_user, record) -> str | None:
    """生成软删记录可见性元数据。

    当管理员查看一条已软删的记录时，返回 "admin" 字符串，便于前端审计展示。
    其他情况（记录未删除、非管理员、无权限）返回 None。

    用法（详情端点）::

        data = record.to_dict()
        data["viewableBecause"] = build_viewable_because(current_user, record)
        return success_response(data=data)

    Args:
        current_user: 当前登录用户（FastAPI 依赖注入）。
        record: ORM 模型实例，需具有 ``is_active`` 属性。

    Returns:
        "admin" 或 None。
    """
    if record is None or current_user is None:
        return None
    is_deleted = not bool(getattr(record, "is_active", True))
    if not is_deleted:
        return None
    # 已软删记录：只有管理员才能看到详情（非管理员会被 _get_xxx_or_404 拦截）
    if is_admin(current_user):
        return "admin"
    return None
