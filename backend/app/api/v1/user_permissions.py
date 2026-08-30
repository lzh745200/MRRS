# -*- coding: utf-8 -*-
"""
用户权限管理 API（旧版 — 计划废弃）

⚠️ 本模块的端点计划在 v1.6.0 合并到 /api/v1/permissions/*
   新功能请使用 /rbac/* 端点。
   旧端点兼容保留至 2027-01-01，届时删除。
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.response import success_response
from app.core.security import get_current_user
from app.models.user import User
from app.core.permission_utils import is_superuser
from app.services.user_permission_service import UserPermissionService
from app.core.error_handler import BusinessLogicError
from app.core.cache import cache_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-permissions", tags=["用户权限管理（旧版，v1.6.0后合并至/rbac）"])


# ==================== Pydantic 模型 ====================


class AssignUserToOrgRequest(BaseModel):
    """分配用户到组织请求"""

    user_id: int
    organization_id: int
    role: str = "member"  # admin, member, viewer
    is_primary: bool = False


class AssignRoleRequest(BaseModel):
    """分配角色请求"""

    user_id: int
    role_id: str
    expires_at: Optional[str] = None


class GrantPermissionRequest(BaseModel):
    """授予权限请求"""

    user_id: int
    permission: str
    expires_at: Optional[str] = None


class CheckPermissionRequest(BaseModel):
    """检查权限请求"""

    user_id: int
    permission: str


# ==================== 用户-组织管理 ====================


@router.post("/assign-organization")
async def assign_user_to_organization(
    request: AssignUserToOrgRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    将用户分配到组织

    需要权限: user:assign_org
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "user:assign_org"):
        if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
            raise HTTPException(status_code=403, detail="没有权限分配用户到组织")

    try:
        user_org = service.assign_user_to_organization(
            user_id=request.user_id,
            organization_id=request.organization_id,
            role=request.role,
            is_primary=request.is_primary,
        )

        return success_response(
            data={
                "user_id": user_org.user_id,
                "organization_id": user_org.organization_id,
                "role": user_org.role,
            },
            message="用户已分配到组织",
        )
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/remove-organization")
async def remove_user_from_organization(
    user_id: int = Query(...),
    organization_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    将用户从组织中移除

    需要权限: user:remove_org
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "user:remove_org"):
        if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
            raise HTTPException(status_code=403, detail="没有权限移除用户组织")

    success = service.remove_user_from_organization(user_id, organization_id)

    if not success:
        raise HTTPException(status_code=404, detail="用户组织关联不存在")

    return success_response(message="用户已从组织中移除")


@router.get("/user-organizations/{user_id}")
async def get_user_organizations(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户所属的所有组织

    需要权限: user:view 或查看自己的信息
    """
    service = UserPermissionService(db)

    # 权限检查：可以查看自己的信息或有权限查看其他用户
    if user_id != current_user.id:
        if not service.check_user_permission(current_user.id, "user:view"):
            if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
                raise HTTPException(status_code=403, detail="没有权限查看用户组织")

    organizations = service.get_user_organizations(user_id)

    return success_response(data=organizations, count=len(organizations))


@router.get("/organization-users/{organization_id}")
async def get_organization_users(
    organization_id: int,
    include_children: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取组织下的所有用户

    需要权限: org:view_users
    """
    service = UserPermissionService(db)

    # 权限检查：需要有权限查看组织用户
    if not service.check_user_permission(current_user.id, "org:view_users"):
        # 或者是该组织的管理员
        if not service.check_user_data_scope(current_user.id, organization_id):
            raise HTTPException(status_code=403, detail="没有权限查看组织用户")

    users = service.get_organization_users(organization_id, include_children)

    return success_response(data=users, count=len(users))


# ==================== 角色管理 ====================


@router.post("/assign-role")
async def assign_role_to_user(
    request: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为用户分配角色

    需要权限: role:assign
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "role:assign"):
        if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
            raise HTTPException(status_code=403, detail="没有权限分配角色")

    try:
        from datetime import datetime

        expires_at = None
        if request.expires_at:
            expires_at = datetime.fromisoformat(request.expires_at)

        user_role = service.assign_role_to_user(
            user_id=request.user_id,
            role_id=request.role_id,
            granted_by=current_user.id,
            expires_at=expires_at,
        )

        return success_response(
            data={"user_id": user_role.user_id, "role_id": user_role.role_id},
            message="角色已分配",
        )
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/remove-role")
async def remove_role_from_user(
    user_id: int = Query(...),
    role_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    移除用户的角色

    需要权限: role:remove
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "role:remove"):
        if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
            raise HTTPException(status_code=403, detail="没有权限移除角色")

    success = service.remove_role_from_user(user_id, role_id)

    if not success:
        raise HTTPException(status_code=404, detail="用户角色关联不存在")

    return success_response(message="角色已移除")


@router.get("/user-roles/{user_id}")
async def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户的所有角色

    需要权限: user:view 或查看自己的信息
    """
    service = UserPermissionService(db)

    # 权限检查
    if user_id != current_user.id:
        if not service.check_user_permission(current_user.id, "user:view"):
            if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
                raise HTTPException(status_code=403, detail="没有权限查看用户角色")

    roles = service.get_user_roles(user_id)

    return success_response(data=roles, count=len(roles))


# ==================== 权限管理 ====================


@router.post("/grant-permission")
async def grant_permission_to_user(
    request: GrantPermissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    直接授予用户权限

    需要权限: permission:grant
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "permission:grant"):
        if not (current_user.is_superuser or is_superuser(current_user)):
            raise HTTPException(status_code=403, detail="没有权限授予权限")

    try:
        from datetime import datetime

        expires_at = None
        if request.expires_at:
            expires_at = datetime.fromisoformat(request.expires_at)

        user_perm = service.grant_permission_to_user(
            user_id=request.user_id,
            permission=request.permission,
            granted_by=current_user.id,
            expires_at=expires_at,
        )

        return success_response(
            data={"user_id": user_perm.user_id, "permission": user_perm.permission},
            message="权限已授予",
        )
    except BusinessLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/revoke-permission")
async def revoke_permission_from_user(
    user_id: int = Query(...),
    permission: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    撤销用户的权限

    需要权限: permission:revoke
    """
    service = UserPermissionService(db)

    # 权限检查
    if not service.check_user_permission(current_user.id, "permission:revoke"):
        if not (current_user.is_superuser or is_superuser(current_user)):
            raise HTTPException(status_code=403, detail="没有权限撤销权限")

    success = service.revoke_permission_from_user(user_id, permission)

    if not success:
        raise HTTPException(status_code=404, detail="用户权限不存在")

    return success_response(message="权限已撤销")


@router.get("/user-permissions/{user_id}")
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户的所有权限

    需要权限: user:view 或查看自己的信息
    """
    service = UserPermissionService(db)

    # 权限检查
    if user_id != current_user.id:
        if not service.check_user_permission(current_user.id, "user:view"):
            if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
                raise HTTPException(status_code=403, detail="没有权限查看用户权限")

    permissions = service.get_user_permissions(user_id)

    return success_response(data=permissions, count=len(permissions))


@router.post("/check-permission")
async def check_user_permission(
    request: CheckPermissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    检查用户是否拥有指定权限

    任何用户都可以检查自己的权限
    """
    service = UserPermissionService(db)

    # 只能检查自己的权限，除非是管理员
    if request.user_id != current_user.id:
        if not (current_user.is_superuser or current_user.role in ["super_admin", "admin"]):
            raise HTTPException(status_code=403, detail="只能检查自己的权限")

    has_permission = service.check_user_permission(request.user_id, request.permission)

    return success_response(has_permission=has_permission)


# ==================== 组织树管理 ====================


@router.get("/organization-tree")
@cache_result(ttl=3600)
async def get_organization_tree(
    parent_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取组织树

    根据用户的数据范围权限过滤
    """
    service = UserPermissionService(db)

    tree = service.get_organization_tree(parent_id, current_user.id)

    return success_response(data=tree)


@router.get("/accessible-organizations")
async def get_accessible_organizations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    获取当前用户可访问的所有组织ID列表
    """
    service = UserPermissionService(db)

    org_ids = service.get_user_accessible_organizations(current_user.id)

    return success_response(data=org_ids, count=len(org_ids))


@router.get("")
async def get_user_permissions_root(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前用户权限信息（根路径）
    """
    service = UserPermissionService(db)

    # 获取用户可访问的组织
    org_ids = service.get_user_accessible_organizations(current_user.id)

    return success_response(
        data={
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "accessible_organization_ids": org_ids,
            "organization_id": current_user.organization_id,
        },
    )
