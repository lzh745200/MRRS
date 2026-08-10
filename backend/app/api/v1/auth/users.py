import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.exceptions import AuthenticationException, NotFoundException
from app.core.permission_utils import is_superuser, require_admin
from app.core.response import ok_list
from app.core.security import get_current_user, get_password_hash
from app.core.cache import cache_result
from app.core.config import settings
from app.models.machine_code import MachineCode
from app.models.user import User
from app.services.user_service import VALID_ROLES
from app.core.constants import normalize_role
from app.core.transaction import safe_commit
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["用户管理"])


# ==================== Schemas ====================


class ProfileUpdate(BaseModel):
    """个人资料更新"""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[str] = None
    address: Optional[str] = None
    remark: Optional[str] = None


class UserCreateBody(BaseModel):
    """创建用户请求体"""

    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = "user"
    organization_id: Optional[int] = None
    data_scope: Optional[str] = "org"
    permissions: Optional[str] = ""  # 兼容旧格式，逗号分隔
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = True
    allowed_permissions: Optional[str] = None  # 新格式，JSON数组字符串


class UserPermissionsUpdate(BaseModel):
    """用户权限分配请求体"""

    role: Optional[str] = None
    organization_id: Optional[int] = None
    data_scope: Optional[str] = None
    permissions: Optional[str] = None
    is_active: Optional[bool] = None
    department: Optional[str] = None
    position: Optional[str] = None
    machine_binding_required: Optional[bool] = None
    allowed_permissions: Optional[str] = None


class UserUpdateBody(BaseModel):
    """更新用户基本信息请求体（不包含权限分配）"""

    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[str] = None
    address: Optional[str] = None
    remark: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[int] = None
    data_scope: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordBody(BaseModel):
    """修改密码请求体"""

    old_password: str
    new_password: str


class AdminResetPasswordBody(BaseModel):
    """管理员重置密码请求体"""

    new_password: str


VALID_SCOPES = {"all", "org", "org_children", "self"}

# 静态选项数据缓存 TTL (1小时)
OPTIONS_CACHE_TTL = 3600


# ==================== 个人中心 ====================


# 角色中文名称映射
_ROLE_DISPLAY_MAP = {
    "super_admin": "超级管理员",
    "admin": "系统管理员",
    "user": "普通用户",
    "viewer": "访客",
}


def _get_role_display(user) -> str:
    """根据用户角色返回中文名称"""
    if is_superuser(user):
        return "超级管理员"
    return _ROLE_DISPLAY_MAP.get(user.role or "", "普通用户")


@router.get("/me", summary="获取当前用户信息")
async def get_current_user_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户的完整信息"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise NotFoundException("用户不存在")
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": user.id,
            "username": user.username,
            "name": user.full_name or user.username,
            "email": user.email,
            "phone": user.phone,
            "department": user.department or "",
            "position": user.position or "",
            "avatar": user.avatar or "",
            "gender": getattr(user, "gender", "") or "",
            "birthday": getattr(user, "birthday", "") or "",
            "address": getattr(user, "address", "") or "",
            "remark": getattr(user, "remark", "") or "",
            "role": user.role or "user",
            "roleName": _get_role_display(user),
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "status": "active" if user.is_active else "inactive",
            "lastLoginTime": (user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else ""),
            "lastLoginIp": "",
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "allowed_menus": user.allowed_menus_list,
        },
    }


@router.put("/me/profile", summary="更新当前用户资料")
async def update_current_user_profile(
    data: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前登录用户的个人资料"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise NotFoundException("用户不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    safe_commit(db)
    db.refresh(user)
    return {
        "code": 200, "success": True, "message": "资料更新成功",
        "data": {
            "id": user.id, "username": user.username,
            "name": user.full_name or user.username,
            "email": user.email, "phone": user.phone,
            "department": user.department or "",
            "position": user.position or "",
            "avatar": user.avatar or "",
            "gender": getattr(user, "gender", "") or "",
            "birthday": getattr(user, "birthday", "") or "",
            "address": getattr(user, "address", "") or "",
            "remark": getattr(user, "remark", "") or "",
            "role": user.role or "user",
            "roleName": _get_role_display(user),
            "is_active": user.is_active,
            "status": "active" if user.is_active else "inactive",
        },
    }


# ==================== 用户列表 ====================


@router.get("")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    organization_id: Optional[int] = None,
    role: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户列表 - 支持按状态、组织、角色筛选"""
    require_admin(current_user)
    query = db.query(User)

    # 非 super_admin 只能查看本组织及下级组织的用户
    is_super = getattr(current_user, "is_superuser", False) or current_user.role == "super_admin"
    if not is_super and current_user.organization_id:
        from app.models.organization import Organization
        child_org_ids = [
            row[0] for row in db.query(Organization.id).filter(
                Organization.path.contains(f"/{current_user.organization_id}/")
            ).all()
        ]
        allowed_org_ids = [current_user.organization_id] + child_org_ids
        query = query.filter(User.organization_id.in_(allowed_org_ids))

    if keyword:
        query = query.filter(
            User.username.contains(keyword) | User.full_name.contains(keyword) | User.email.contains(keyword)
        )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if organization_id is not None:
        query = query.filter(User.organization_id == organization_id)

    if role:
        query = query.filter(User.role == role)

    total = query.count()
    users = query.options(joinedload(User.organization)).offset((page - 1) * page_size).limit(page_size).all()

    # 批量查询机器码绑定信息
    user_ids = [u.id for u in users]
    machine_codes = {}
    if user_ids:
        mc_records = (
            db.query(MachineCode).filter(MachineCode.user_id.in_(user_ids), MachineCode.status == "active").all()
        )
        for mc in mc_records:
            machine_codes[mc.user_id] = mc.machine_code

    return ok_list(
        items=[
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "phone": u.phone,
                "department": u.department,
                "position": u.position,
                "is_active": u.is_active,
                "is_superuser": is_superuser(u),
                "role": u.role or None,
                "organization_id": u.organization_id,
                "organization_name": u.organization.name if u.organization else None,
                "data_scope": u.data_scope,
                "permissions": u.permissions_list if hasattr(u, "permissions_list") else [],
                "machine_binding_required": u.machine_binding_required,
                "allowed_permissions": u.allowed_permissions or "",
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "machine_code": machine_codes.get(u.id),
            }
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/pending/list", summary="获取待审核用户列表")
async def get_pending_users(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取待审核（未激活）的用户列表，供管理员审核"""
    require_admin(current_user)

    pending_users = db.query(User).filter(User.is_active == False).all()  # noqa: E712

    return ok_list(
        items=[
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "role": u.role,
            }
            for u in pending_users
        ],
        total=len(pending_users),
    )


class StaffItem(BaseModel):
    """人员列表项"""

    id: int
    username: str
    name: str
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    avatar: Optional[str] = None


@router.get("/staff-list", summary="获取人员列表（公开）")
async def get_staff_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取活跃用户列表，供任务分配等场景使用（任何登录用户均可访问）"""
    from app.core.data_permission import get_data_scope, DataScope

    query = db.query(User).filter(User.is_active == True)  # noqa: E712
    # User 模型无 created_by/department_id 列，仅按组织过滤
    scope = get_data_scope(current_user)
    if scope == DataScope.OWN:
        query = query.filter(User.id == current_user.id)
    elif scope == DataScope.OWN_DEPT and getattr(current_user, "organization_id", None):
        query = query.filter(User.organization_id == current_user.organization_id)
    # DataScope.ALL — 无过滤
    total = query.count()

    users = (
        query.order_by(User.username)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ok_list(
        items=[
            StaffItem(
                id=u.id,
                username=u.username,
                name=u.full_name or u.username,
                full_name=u.full_name,
                role=u.role,
                department=u.department,
                position=u.position,
                avatar=u.avatar or "",
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== 用户详情（动态路径必须在静态路径之后） ====================


@router.get("/{user_id}")
async def get_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户详情 - 包含完整的权限和组织信息"""
    # 允许用户查看自己的信息，查看其他用户需管理员权限
    if user_id != current_user.id:
        require_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    org = user.organization
    org_info = {"id": org.id, "name": org.name, "code": org.code} if org else None

    return success_response(data={
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "department": user.department,
        "position": user.position,
        "avatar": user.avatar,
        "gender": user.gender,
        "address": user.address,
        "remark": user.remark,
        "is_active": user.is_active,
        "is_superuser": is_superuser(user),
        "role": user.role,
        "organization_id": user.organization_id,
        "organization": org_info,
        "data_scope": user.data_scope,
        "permissions": user.permissions_list if hasattr(user, "permissions_list") else [],
        "machine_binding_required": user.machine_binding_required,
        "allowed_permissions": user.allowed_permissions or "",
        "must_change_password": user.must_change_password,
        "failed_login_count": user.failed_login_count,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    })


@router.post("")
async def create_user(
    data: UserCreateBody,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建用户（支持完整的权限和组织分配）

    管理员可以：
    1. 指定用户的角色（role）
    2. 分配所属组织（organization_id）
    3. 设置数据范围（data_scope）
    4. 分配权限列表（permissions）
    5. 设置初始状态（is_active，可用于审核流程）
    """
    require_admin(current_user)

    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    if data.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 验证组织是否存在（如果指定了组织）
    if data.organization_id:
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == data.organization_id).first()
        if not org:
            raise HTTPException(status_code=400, detail=f"组织ID {data.organization_id} 不存在")

    # 验证角色有效性（兼容历史角色值：approval_leader/manager→admin，operator→user）
    role = normalize_role(data.role)
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的角色: {role}")

    # 验证数据范围有效性
    data_scope = data.data_scope or "org"
    if data_scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"无效的数据范围: {data_scope}")

    # 处理权限：将逗号分隔的权限转换为JSON数组保存到allowed_permissions
    allowed_perms = data.allowed_permissions
    if not allowed_perms and data.permissions:
        # 将旧格式逗号分隔的权限转换为JSON数组
        import json

        perms_list = [p.strip() for p in data.permissions.split(",") if p.strip()]
        allowed_perms = json.dumps(perms_list) if perms_list else None

    # 创建用户，包含所有权限和组织信息
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=role,
        organization_id=data.organization_id,
        data_scope=data_scope,
        permissions=data.permissions or "",  # 保留旧字段以兼容
        allowed_permissions=allowed_perms,  # RBAC服务使用此字段
        department=data.department,
        position=data.position,
        phone=data.phone,
        is_active=data.is_active if data.is_active is not None else True,
    )

    db.add(user)
    safe_commit(db)
    db.refresh(user)

    return success_response(data={
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
        "data_scope": user.data_scope,
        "is_active": user.is_active,
        "message": "用户创建成功"
        + ("，请通知用户登录" if user.is_active else "，用户当前处于待审核状态，需激活后才能登录"),
    }, message="用户创建成功"
        + ("，请通知用户登录" if user.is_active else "，用户当前处于待审核状态，需激活后才能登录"))


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdateBody,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户基本信息（包含权限分配）"""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    update_fields = data.model_dump(exclude_unset=True)

    # 受保护的字段不允许通过此接口修改
    PROTECTED_FIELDS = {"is_superuser"}
    update_fields = {k: v for k, v in update_fields.items() if k not in PROTECTED_FIELDS}

    # 不能修改自己的权限（避免误操作导致失去管理权限）
    if user.id == current_user.id and "role" in update_fields:
        if update_fields["role"] not in ["admin", "super_admin"]:
            raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    # 验证组织是否存在（如果指定了组织）
    if "organization_id" in update_fields and update_fields["organization_id"]:
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == update_fields["organization_id"]).first()
        if not org:
            raise HTTPException(status_code=400, detail="组织不存在")

    # 验证角色有效性（归一化兼容历史角色值）
    if "role" in update_fields and update_fields["role"]:
        update_fields["role"] = normalize_role(update_fields["role"])
        if update_fields["role"] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="无效的角色")

    # 验证数据范围有效性
    if "data_scope" in update_fields and update_fields["data_scope"]:
        if update_fields["data_scope"] not in VALID_SCOPES:
            raise HTTPException(status_code=400, detail="无效的数据范围")

    for field, value in update_fields.items():
        setattr(user, field, value)

    safe_commit(db)

    return {"code": 200, "message": "更新成功", "updated_fields": list(update_fields.keys())}


@router.delete("/{user_id}")
async def delete_user(user_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    db.delete(user)
    safe_commit(db)

    return {"code": 200, "message": "删除成功"}


@router.put("/{user_id}/permissions", summary="分配/修改用户权限")
async def update_user_permissions(
    user_id: int,
    data: UserPermissionsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员分配或修改用户权限

    可用于：
    1. 审核新用户（设置 is_active=True 并分配角色）
    2. 调整用户角色
    3. 分配所属组织
    4. 设置数据范围
    5. 分配具体权限
    """
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    # 不能修改自己的权限（避免误操作导致失去管理权限）
    if user.id == current_user.id and data.role and data.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    update_fields = data.model_dump(exclude_unset=True)

    # 验证组织是否存在（如果指定了组织）
    if "organization_id" in update_fields and update_fields["organization_id"]:
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == update_fields["organization_id"]).first()
        if not org:
            raise HTTPException(status_code=400, detail=f"组织ID {update_fields['organization_id']} 不存在")

    # 验证角色有效性（归一化兼容历史角色值）
    if "role" in update_fields:
        if update_fields["role"]:
            update_fields["role"] = normalize_role(update_fields["role"])
        if update_fields["role"] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"无效的角色: {update_fields['role']}")

    # 验证数据范围有效性
    if "data_scope" in update_fields:
        if update_fields["data_scope"] not in VALID_SCOPES:
            raise HTTPException(status_code=400, detail=f"无效的数据范围: {update_fields['data_scope']}")

    # 应用更新
    for field, value in update_fields.items():
        setattr(user, field, value)

    safe_commit(db)
    db.refresh(user)

    return success_response(data={
        "message": "用户权限更新成功",
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
        "data_scope": user.data_scope,
        "is_active": user.is_active,
    }, message="用户权限更新成功")


@router.get("/roles/options", summary="获取角色选项")
@cache_result(ttl=OPTIONS_CACHE_TTL)
async def get_role_options(
    current_user=Depends(get_current_user),
):
    """获取可用的角色列表，用于创建/编辑用户时选择角色"""
    require_admin(current_user)

    return success_response(data={
        "roles": [
            {"value": "super_admin", "label": "超级管理员", "description": "系统最高权限，可管理所有功能"},
            {"value": "admin", "label": "系统管理员", "description": "可管理用户、组织、系统配置"},
            {"value": "user", "label": "普通用户", "description": "日常数据录入和操作"},
            {"value": "viewer", "label": "访客", "description": "只能查看数据，无法修改"},
        ]
    })


@router.get("/data-scopes/options", summary="获取数据范围选项")
@cache_result(ttl=OPTIONS_CACHE_TTL)
async def get_data_scope_options(
    current_user=Depends(get_current_user),
):
    """获取可用的数据范围选项"""
    require_admin(current_user)

    return success_response(data={
        "data_scopes": [
            {"value": "all", "label": "全部数据", "description": "可访问系统内所有数据"},
            {"value": "org_children", "label": "本组织及下级", "description": "可访问本组织及其下级组织的所有数据"},
            {"value": "org", "label": "仅本组织", "description": "仅能访问本组织的数据"},
            {"value": "self", "label": "仅自己", "description": "仅能访问自己创建的数据"},
        ]
    })


@router.get("/permissions/options", summary="获取权限选项")
@cache_result(ttl=OPTIONS_CACHE_TTL)
async def get_permission_options(
    current_user=Depends(get_current_user),
):
    """获取可用的权限列表，用于给用户分配具体权限"""
    require_admin(current_user)

    return success_response(data={
        "permissions": [
            # 系统管理权限
            {"code": "system:manage", "name": "系统管理", "category": "系统"},
            {"code": "user:manage", "name": "用户管理", "category": "系统"},
            {"code": "org:manage", "name": "组织管理", "category": "系统"},
            {"code": "role:manage", "name": "角色管理", "category": "系统"},
            # 数据管理权限
            {"code": "village:manage", "name": "村庄管理", "category": "数据"},
            {"code": "project:manage", "name": "项目管理", "category": "数据"},
            {"code": "fund:manage", "name": "资金管理", "category": "数据"},
            {"code": "report:manage", "name": "报表管理", "category": "数据"},
            # 操作权限
            {"code": "data:view", "name": "数据查看", "category": "操作"},
            {"code": "data:create", "name": "数据创建", "category": "操作"},
            {"code": "data:edit", "name": "数据编辑", "category": "操作"},
            {"code": "data:delete", "name": "数据删除", "category": "操作"},
            {"code": "data:export", "name": "数据导出", "category": "操作"},
            {"code": "data:import", "name": "数据导入", "category": "操作"},
            # 审批权限
            {"code": "approve:view", "name": "查看审批", "category": "审批"},
            {"code": "approve:submit", "name": "提交审批", "category": "审批"},
            {"code": "approve:process", "name": "处理审批", "category": "审批"},
        ]
    })


@router.post("/{user_id}/admin-reset-password", summary="管理员重置用户密码")
async def admin_reset_password(
    user_id: int,
    data: AdminResetPasswordBody,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员直接重置用户密码（无需旧密码）"""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    from app.core.security import PasswordPolicy

    is_valid, msg = PasswordPolicy.validate(data.new_password, username=user.username)
    if not is_valid:
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": msg, "field": "new_password"},
        )

    user.hashed_password = get_password_hash(data.new_password)
    user.revoke_all_tokens()
    user.must_change_password = True
    safe_commit(db)

    return {"code": 200, "message": "密码重置成功"}


@router.put("/{user_id}/password")
async def change_password(
    user_id: int,
    data: ChangePasswordBody,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    if not current_user.is_superuser and user_id != current_user.id:
        raise AuthenticationException("无权修改其他用户密码")

    from app.core.security import PasswordPolicy, verify_password

    # 校验旧密码
    if not verify_password(data.old_password, user.hashed_password):
        # 返回 envelope 带 field 字段，前端据此高亮 oldPassword 输入框
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": "当前密码错误", "field": "old_password"},
        )

    # 密码策略校验（传入用户名做弱密码检查）
    is_valid, msg = PasswordPolicy.validate(data.new_password, username=user.username)
    if not is_valid:
        # 返回 envelope 带 field 字段，前端据此高亮 newPassword 输入框
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": msg, "field": "new_password"},
        )

    user.hashed_password = get_password_hash(data.new_password)
    user.revoke_all_tokens()
    user.must_change_password = False
    safe_commit(db)

    # 清理自动生成的管理员密码临时文件（admin_pwd_*.txt）
    if user.username == "admin":
        try:
            import glob as _glob
            import tempfile as _tf
            for _f in _glob.glob(os.path.join(_tf.gettempdir(), "admin_pwd_*.txt")):
                os.remove(_f)
                logger.info("已清理管理员密码临时文件: %s", _f)
        except Exception as _cleanup_err:
            logger.warning("清理密码临时文件失败: %s", _cleanup_err)

    # 审计日志（密码修改已提交，审计失败不影响主流程）
    try:
        from app.services.work_log_service import write_work_log

        write_work_log(
            db=db,
            log_type="user",
            action="change_password",
            entity_id=user.id,
            entity_name=user.username,
            user_id=current_user.id,
            username=current_user.username,
        )
    except Exception as audit_err:
        # 审计日志写入失败不应阻断密码修改主流程，但必须记录日志便于排查
        logger.warning("密码修改审计日志写入失败: %s", audit_err, exc_info=True)

    return {"code": 200, "message": "密码修改成功"}


# ==================== 头像上传 ====================


@router.post("/{user_id}/avatar", summary="上传用户头像")
async def upload_avatar(
    user_id: int,
    avatar: "UploadFile",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传用户头像（仅本人或管理员）"""
    import os as _os
    import uuid as _uuid
    from pathlib import Path as _Path

    # 权限检查：仅本人或管理员可上传
    if current_user.id != user_id and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="无权修改他人头像")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    # 校验文件类型 — 必须有 Content-Type 且为允许的图片格式
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if not avatar.content_type or avatar.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WebP 格式")

    # 读取内容并校验大小（最大 2MB）
    content = await avatar.read()
    max_size = 2 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="头像文件不能超过 2MB")

    # 保存文件到 uploads/avatars/（使用 settings.UPLOAD_DIR，兼容打包模式）
    upload_dir = _Path(settings.UPLOAD_DIR) / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = (_os.path.splitext(avatar.filename or "avatar.png")[1] or ".png").lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        ext = ".png"
    filename = f"{_uuid.uuid4().hex}{ext}"
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    # 更新用户头像 URL
    avatar_url = f"/uploads/avatars/{filename}"
    user.avatar = avatar_url
    safe_commit(db)

    return {
        "code": 200,
        "message": "头像上传成功",
        "avatar_url": avatar_url,
    }
