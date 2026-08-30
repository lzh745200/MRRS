"""
权限管理 API 路由
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success_response
from app.core.security import get_current_user, require_admin
from app.models.rbac import RbacRole, RolePermission, UserRole
from app.models.user import User
from app.core.transaction import TransactionManager
from app.services.rbac_service import Permission, rbac_service

router = APIRouter(prefix="/rbac", tags=["权限管理"])


# ==================== 数据模型 ====================


class RoleCreate(BaseModel):
    name: str
    description: str
    permissions: List[str]
    is_system: bool = False


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    is_system: bool
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime


class PermissionGrant(BaseModel):
    user_id: int
    permissions: List[str]
    expires_at: Optional[datetime] = None


class RoleRevoke(BaseModel):
    user_id: int
    role_id: str


class RoleAssign(BaseModel):
    user_id: int
    role_id: str
    expires_at: Optional[datetime] = None


class PermissionCheckRequest(BaseModel):
    permission: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class UserPermissionsResponse(BaseModel):
    user_id: str
    permissions: List[str]
    roles: List[dict]


# ==================== 权限检查 API ====================


@router.post("/check")
async def check_permission(
    request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """检查用户权限"""
    current_user_id = str(current_user.id)
    has_permission = await rbac_service.check_permission(
        user_id=current_user_id,
        permission=request.permission,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        db=db,
    )

    return success_response(
        has_permission=has_permission,
        permission=request.permission,
        user_id=current_user_id,
    )


@router.get("/user/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取用户所有权限（普通用户仅可查看自己的权限，管理员可查看任意用户）"""
    current_user_id = str(current_user.id)
    current_role = getattr(current_user, "role", "")
    if current_user_id != user_id and current_role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权查看其他用户的权限")

    permissions = await rbac_service.get_user_permissions(user_id, db)
    roles = await rbac_service.get_user_roles(user_id, db)
    return UserPermissionsResponse(user_id=user_id, permissions=list(permissions), roles=roles)


@router.get("/user/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取用户角色（普通用户仅可查看自己的角色，管理员可查看任意用户）"""
    current_user_id = str(current_user.id)
    current_role = getattr(current_user, "role", "")
    if current_user_id != user_id and current_role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权查看其他用户的角色")

    roles = await rbac_service.get_user_roles(user_id, db)
    return success_response(data=roles, count=len(roles))


# ==================== 角色管理 API ====================


@router.post("/roles")
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """创建角色（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        role_id = await rbac_service.create_role(
            name=role_data.name,
            description=role_data.description,
            permissions=role_data.permissions,
            is_system=role_data.is_system,
            db=sess,
        )
    return success_response(
        role_id=role_id,
        message=f"角色 '{role_data.name}' 创建成功",
    )


@router.get("/roles")
async def list_roles(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取角色列表（分页）"""
    # 先查询总数
    total = db.query(sa_func.count(RbacRole.id)).scalar() or 0

    # 再查询分页数据
    roles = (
        db.query(RbacRole).order_by(RbacRole.priority.asc(), RbacRole.created_at.desc()).offset(skip).limit(limit).all()
    )

    # 注意：此处不用 ok_list() —— 前端 Role.vue / PermissionAssignmentDrawer.vue
    # 以 res.data 直接读取角色数组，包成 {items,...} 会破坏数组语义。
    return success_response(data=[r.to_dict() for r in roles], total=total)


@router.get("/roles/{role_id}")
async def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取角色详情"""
    role = db.query(RbacRole).filter(RbacRole.id == role_id).first()
    if not role:
        return JSONResponse(status_code=404, content={"error": "角色不存在"})

    perms = db.query(RolePermission.permission).filter(RolePermission.role_id == role_id).all()

    data = role.to_dict()
    data["permissions"] = [p[0] for p in perms]
    return success_response(data=data)


@router.put("/roles/{role_id}")
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """更新角色（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        role = sess.query(RbacRole).filter(RbacRole.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 更新基本字段
        if role_data.name is not None:
            role.name = role_data.name
        if role_data.description is not None:
            role.description = role_data.description
        if role_data.is_active is not None:
            role.is_active = role_data.is_active

        # 更新权限列表（先删后增）
        if role_data.permissions is not None:
            sess.query(RolePermission).filter(RolePermission.role_id == role_id).delete(
                synchronize_session=False,
            )
            for perm in role_data.permissions:
                sess.add(RolePermission(role_id=role_id, permission=perm))

        sess.flush()
        sess.refresh(role)

    return success_response(message=f"角色 '{role.name}' 更新成功")


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """删除角色（具有事务原子性，系统角色不可删除）"""
    with TransactionManager.transaction(db) as sess:
        role = sess.query(RbacRole).filter(RbacRole.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")
        if role.is_system:
            raise HTTPException(status_code=400, detail="系统内置角色不可删除")

        sess.delete(role)  # cascade 会自动删除关联的 UserRole 和 RolePermission

    return success_response(message=f"角色 '{role.name}' 已删除")


@router.get("/roles/{role_id}/users")
async def get_role_users(
    role_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """获取角色关联的用户列表"""
    rows = (
        db.query(User.id, User.username, User.full_name, User.role, User.is_active)
        .join(UserRole, User.id == UserRole.user_id)
        .filter(UserRole.role_id == role_id)
        .all()
    )

    users = [
        {
            "id": r.id,
            "username": r.username,
            "full_name": r.full_name,
            "role": r.role,
            "is_active": r.is_active,
        }
        for r in rows
    ]
    return success_response(data=users, total=len(users))


# ==================== 权限分配 API ====================


@router.post("/assign/role")
async def assign_role(
    assignment: RoleAssign,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """分配角色给用户（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        result = await rbac_service.assign_role(
            user_id=str(assignment.user_id),
            role_id=assignment.role_id,
            granted_by=str(current_user.id),
            expires_at=assignment.expires_at.isoformat() if assignment.expires_at else None,
            db=sess,
        )

    if result["success"]:
        status = "已完成分配" if result["newly_granted"] else "角色已存在（无需操作）"
        return success_response(
            newly_granted=result["newly_granted"],
            message=f"角色分配成功: 用户 {assignment.user_id} -> 角色 {assignment.role_id} — {status}",
        )
    raise HTTPException(status_code=400, detail="角色分配失败")


@router.delete("/revoke/role")
async def revoke_role(
    revoke: RoleRevoke,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """撤销用户角色（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        success = await rbac_service.revoke_role(
            user_id=str(revoke.user_id), role_id=revoke.role_id, db=sess,
        )

    if success:
        return success_response(
            message=f"角色撤销成功: 用户 {revoke.user_id} -> 角色 {revoke.role_id}",
        )
    raise HTTPException(status_code=400, detail="角色撤销失败")


@router.post("/grant/permission")
async def grant_permission(
    grant: PermissionGrant,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """直接授予用户权限（支持批量，具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        result = await rbac_service.grant_permissions_batch(
            user_id=str(grant.user_id),
            permissions=grant.permissions,
            granted_by=str(current_user.id),
            expires_at=grant.expires_at.isoformat() if grant.expires_at else None,
            db=sess,
        )

    return success_response(
        granted=result["granted"],
        skipped=result["skipped"],
        failed=result["failed"],
        message=(
            f"权限授予完成: 新增 {len(result['granted'])}"
            + (f", 跳过(已存在) {len(result['skipped'])}" if result["skipped"] else "")
        ),
    )


@router.post("/revoke/permission")
async def revoke_permission(
    revoke: PermissionGrant,  # 复用 PermissionGrant 模型（user_id + permissions: List[str]）
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """批量撤销用户权限（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        revoked, failed = await rbac_service.revoke_permissions_batch(
            user_id=str(revoke.user_id),
            permissions=revoke.permissions,
            db=sess,
        )

    return success_response(
        success=len(failed) == 0,
        revoked=revoked,
        failed=failed,
        message=f"权限撤销完成: 成功 {len(revoked)}, 失败 {len(failed)}",
    )


@router.post("/save-permissions")
async def save_permissions(
    grant: PermissionGrant,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin()),
):
    """原子性保存用户权限——在单个事务内完成撤销 + 授予（具有事务原子性）"""
    with TransactionManager.transaction(db) as sess:
        result = await rbac_service.save_permissions(
            user_id=str(grant.user_id),
            permissions=grant.permissions,
            granted_by=str(current_user.id),
            expires_at=grant.expires_at.isoformat() if grant.expires_at else None,
            db=sess,
        )

    return success_response(
        success=True,
        **result,
        message=(
            f"权限保存完成: 授予 {len(result['granted'])}"
            + (f", 撤销 {len(result['revoked'])}" if result["revoked"] else "")
            + (f", 跳过(已存在) {len(result['skipped'])}" if result["skipped"] else "")
        ),
    )


# ==================== 权限列表 API ====================


@router.get("/permissions")
async def list_permissions(current_user=Depends(get_current_user)):
    """获取所有可用权限列表"""
    permissions = [
        {
            "code": perm.value,
            "name": perm.name,
            "category": perm.value.split(":")[0] if ":" in perm.value else "other",
            "description": perm.value.replace("_", " ").replace(":", " - "),
        }
        for perm in Permission
    ]

    # 按类别分组
    categories: dict = {}
    for perm in permissions:
        category = perm["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(perm)

    return success_response(
        data=permissions,
        categories=categories,
        total=len(permissions),
    )


# ==================== 前端组件需要的 API ====================


@router.get("/frontend/current-user-permissions")
async def get_current_user_permissions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取当前用户权限（前端组件专用）"""
    current_user_id = str(current_user.id)
    permissions = await rbac_service.get_user_permissions(current_user_id, db)
    roles = await rbac_service.get_user_roles(current_user_id, db)

    # 格式化前端需要的权限数据
    frontend_permissions = {
        "user": {
            "read": Permission.USER_READ.value in permissions,
            "write": Permission.USER_WRITE.value in permissions,
            "delete": Permission.USER_DELETE.value in permissions,
            "manageRoles": Permission.USER_MANAGE_ROLES.value in permissions,
        },
        "village": {
            "read": Permission.VILLAGE_READ.value in permissions,
            "write": Permission.VILLAGE_WRITE.value in permissions,
            "delete": Permission.VILLAGE_DELETE.value in permissions,
            "export": Permission.VILLAGE_EXPORT.value in permissions,
        },
        "policy": {
            "read": Permission.POLICY_READ.value in permissions,
            "write": Permission.POLICY_WRITE.value in permissions,
            "delete": Permission.POLICY_DELETE.value in permissions,
            "publish": Permission.POLICY_PUBLISH.value in permissions,
        },
        "backup": {
            "create": Permission.BACKUP_CREATE.value in permissions,
            "restore": Permission.BACKUP_RESTORE.value in permissions,
            "delete": Permission.BACKUP_DELETE.value in permissions,
            "download": Permission.BACKUP_DOWNLOAD.value in permissions,
        },
        "system": {
            "config": Permission.SYSTEM_CONFIG.value in permissions,
            "monitor": Permission.SYSTEM_MONITOR.value in permissions,
            "logs": Permission.SYSTEM_LOGS.value in permissions,
        },
        "analytics": {
            "read": Permission.ANALYTICS_READ.value in permissions,
            "export": Permission.ANALYTICS_EXPORT.value in permissions,
        },
        "admin": Permission.ADMIN_ALL.value in permissions,
    }

    return success_response(
        data={
            "permissions": frontend_permissions,
            "roles": roles,
            "role_names": [role.get("name") for role in roles],
            "is_admin": Permission.ADMIN_ALL.value in permissions,
        },
    )


@router.get("/frontend/route-permissions")
async def get_route_permissions(current_user=Depends(get_current_user)):
    """获取路由权限配置（前端路由守卫专用）"""
    route_permissions = {
        "/dashboard": ["user:read"],
        "/villages": ["village:read"],
        "/villages/create": ["village:write"],
        "/villages/edit/:id": ["village:write"],
        "/villages/delete/:id": ["village:delete"],
        "/policies": ["policy:read"],
        "/policies/create": ["policy:write"],
        "/policies/edit/:id": ["policy:write"],
        "/policies/publish/:id": ["policy:publish"],
        "/users": ["user:read"],
        "/users/create": ["user:write"],
        "/users/edit/:id": ["user:write"],
        "/users/delete/:id": ["user:delete"],
        "/backup": ["backup:create"],
        "/backup/restore": ["backup:restore"],
        "/system": ["system:monitor"],
        "/analytics": ["analytics:read"],
    }

    return success_response(data=route_permissions)
