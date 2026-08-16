"""
用户管理API - 完整CRUD操作
支持用户创建、密码生成、权限分配等功能
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import generate_password, get_current_user, get_password_hash
from app.core.constants import UserRole, normalize_role
from app.core.permission_utils import is_superuser
from app.models.user import User
from app.core.transaction import safe_commit

router = APIRouter(prefix="/user-management", tags=["用户管理"])


# Pydantic 模型
class UserCreate(BaseModel):
    """创建用户请求"""

    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = None  # 如果不提供则自动生成
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = "user"
    is_active: bool = True
    organization_id: Optional[int] = None  # 所属组织ID


class UserUpdate(BaseModel):
    """更新用户请求"""

    full_name: Optional[str] = None
    name: Optional[str] = None  # 前端可能传 name
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None  # 前端可能传 status
    organization_id: Optional[int] = None  # 所属组织ID


class UserResponse(BaseModel):
    """用户响应"""

    id: int
    username: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime]
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    """重置密码请求"""

    new_password: Optional[str] = None  # 如果不提供则自动生成


# ==================== 静态路由（必须在动态路由 /{user_id} 之前） ====================


@router.get("/generate-password")
async def get_generated_password(length: int = Query(12, ge=8, le=32), current_user=Depends(get_current_user)):
    """生成随机密码"""
    return {"success": True, "data": {"password": generate_password(length)}}


@router.get("/roles")
async def list_roles(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """获取角色列表"""
    role_counts = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())

    items = [
        {
            "id": "1",
            "name": "超级管理员",
            "code": "super_admin",
            "description": "系统配置、备份恢复等最高权限",
            "is_system": True,
            "user_count": role_counts.get(UserRole.SUPER_ADMIN, 0),
        },
        {
            "id": "2",
            "name": "系统管理员",
            "code": "admin",
            "description": "日常业务管理权限",
            "is_system": True,
            "user_count": role_counts.get(UserRole.ADMIN, 0),
        },
        {
            "id": "3",
            "name": "普通用户",
            "code": "user",
            "description": "日常数据录入和操作权限",
            "is_system": True,
            "user_count": role_counts.get(UserRole.USER, 0),
        },
        {
            "id": "4",
            "name": "访客",
            "code": "viewer",
            "description": "只读查看权限",
            "is_system": True,
            "user_count": role_counts.get(UserRole.VIEWER, 0),
        },
    ]

    return ok_list(items=items, total=len(items))


# ==================== CRUD路由 ====================


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    name: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取用户列表"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    query = db.query(User)

    # 搜索条件
    if username:
        query = query.filter(User.username.ilike(f"%{username}%"))
    if name:
        query = query.filter(User.full_name.ilike(f"%{name}%"))
    if status:
        if status == "active":
            query = query.filter(User.is_active == True)  # noqa: E712
        elif status == "inactive":
            query = query.filter(User.is_active == False)  # noqa: E712

    # 总数
    total = query.count()

    # 分页
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    # 构建响应数据
    items = []
    for user in users:
        items.append(
            {
                "id": str(user.id),
                "username": user.username,
                "name": user.full_name or user.username,
                "role": (user.role if user.role else ("admin" if user.is_superuser else "user")),
                "department": user.department or "",
                "phone": user.phone or "",
                "email": user.email or "",
                "status": "active" if user.is_active else "inactive",
                "lastLogin": (user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else "-"),
                "organization_id": user.organization_id,
                "organization_name": (user.organization_name if hasattr(user, "organization_name") else ""),
            }
        )

    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post("")
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建用户"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 生成或使用提供的密码
    password = user_data.password or generate_password()

    # 创建用户（角色归一化：兼容历史角色值）
    from app.core.constants import normalize_role

    user = User(
        username=user_data.username,
        full_name=user_data.full_name or user_data.username,
        hashed_password=get_password_hash(password),
        email=user_data.email,
        phone=user_data.phone,
        department=user_data.department,
        role=normalize_role(user_data.role),
        is_active=user_data.is_active,
        is_superuser=(is_superuser(user_data) or user_data.role == UserRole.ADMIN),
        organization_id=user_data.organization_id,
    )

    db.add(user)
    safe_commit(db)
    db.refresh(user)

    return {
        "success": True,
        "message": "用户创建成功",
        "data": {
            "id": str(user.id),
            "username": user.username,
            "password": password,
        },  # 返回生成的密码（仅在创建时）
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新用户信息"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新字段
    # 兼容前端传 name 或 full_name
    _name = user_data.full_name or user_data.name
    if _name is not None:
        user.full_name = _name
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.phone is not None:
        user.phone = user_data.phone
    if user_data.department is not None:
        user.department = user_data.department
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.status is not None:
        user.is_active = user_data.status == "active"
    if user_data.role is not None:
        user.role = normalize_role(user_data.role)
        user.is_superuser = is_superuser(user_data) or user_data.role == UserRole.ADMIN
    if user_data.organization_id is not None:
        user.organization_id = user_data.organization_id

    user.updated_at = datetime.now()
    safe_commit(db)

    return {"success": True, "message": "用户更新成功"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除用户(级联删除所有相关数据)"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不允许删除超级管理员
    if user.is_superuser and user.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除系统管理员账户")

    # 不允许删除自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    # 使用级联删除服务
    from app.services.user_cascade_delete_service import UserCascadeDeleteService

    try:
        cascade_service = UserCascadeDeleteService(db)
        result = cascade_service.delete_user_cascade(user_id)

        if result["success"]:
            return {
                "success": True,
                "message": "用户删除成功",
                "deleted_records": result["deleted_records"],
                "set_null_records": result.get("set_null_records", 0),
            }
        else:
            raise HTTPException(status_code=404, detail=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"删除用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除用户失败: {str(e)}")


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    reset_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """重置用户密码"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 生成或使用提供的密码
    new_password = reset_data.new_password or generate_password()

    # 仅当调用方显式提供密码时才校验强度；自动生成的密码已符合策略
    if reset_data.new_password:
        from app.core.security import PasswordPolicy

        is_valid, msg = PasswordPolicy.validate(new_password, username=user.username)
        if not is_valid:
            raise HTTPException(status_code=400, detail=msg)

    user.hashed_password = get_password_hash(new_password)
    user.updated_at = datetime.now()
    safe_commit(db)

    return {
        "success": True,
        "message": "密码重置成功",
        "data": {"username": user.username, "new_password": new_password},
    }


@router.post("/{user_id}/assign-role")
async def assign_role(
    user_id: int,
    role_code: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """为用户分配角色"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新角色字段和权限
    user.role = role_code
    user.is_superuser = role_code in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    user.updated_at = datetime.now()
    safe_commit(db)

    return {"success": True, "message": "角色分配成功"}
