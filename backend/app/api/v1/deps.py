"""API dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from app.core.database import get_db  # noqa: F401 — 统一从 database.py re-export
from app.core.security import get_current_user  # noqa: F401 — 真实 JWT 认证实现
from app.core.permission_utils import is_admin, is_superuser  # noqa: F401 — re-export

# 别名,兼容新代码
get_current_active_user = get_current_user

# 管理角色列表（可执行创建/编辑/删除操作）
# 历史角色 manager/approval_leader 已由 constants.normalize_role() 归一化为 admin
ADMIN_ROLES = ("admin", "super_admin")


def require_manager_role(current_user) -> None:
    """要求管理角色，否则返回 403。在 funds / fund_lifecycle 等模块共用。"""
    from app.core.constants import normalize_role

    # 归一化角色：历史角色值（manager/approval_leader）映射为 admin，
    # 保证存量用户的管理权限不因角色精简而降级
    role = normalize_role(getattr(current_user, "role", ""))
    if role not in ADMIN_ROLES and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="权限不足，仅管理员或管理角色可执行此操作")


def require_funds_operator_role(current_user) -> None:
    """经费管理操作权限：放行 user 及以上角色（viewer 保持只读）。

    产品要求普通用户（user）可完整操作经费管理（申请/审批/拨付/结算全流程），
    viewer 仍为只读角色；数据隔离由 filter_by_data_scope / check_record_access 保障。
    """
    from app.core.constants import normalize_role

    role = normalize_role(getattr(current_user, "role", ""))
    if role == "viewer" and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="权限不足，viewer 角色仅可查看经费数据")
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
