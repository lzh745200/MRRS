# security-audit: exempt data_scope — 认证/身份域（本人资料与管理员用户列表/统计），非组织数据枚举
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.data_permission import DataScope, get_data_scope
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
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, normalize_role
from app.core.transaction import safe_commit
from app.core.response import success_response
from app.utils.pagination import clamp_offset_limit, coerce_page_param
from app.utils.upload_helper import read_upload_with_limit

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

# 超级管理员账号的保护口径（W15 深审 #9~#12）：
# 系统管理员（admin）不得创建、修改、删除或重置 super_admin 账号——
# 修复前 admin 可创建 super_admin（一步提权）、可删除/重置超管密码（接管超管）。
_SUPER_ADMIN_ROLE = "super_admin"


def _is_super_admin_account(user) -> bool:
    """判断目标账号是否属于超级管理员（role 或 is_superuser 任一命中即算）"""
    if user is None:
        return False
    if is_superuser(user):
        return True
    return normalize_role(getattr(user, "role", None)) == _SUPER_ADMIN_ROLE


def _assert_can_grant_data_scope(current_user, data_scope: Optional[str]) -> None:
    """仅超级管理员可授予「全部数据」范围（``data_scope="all"``）。

    W25 漏洞收口：``apply_scope_filter``（data_permission.py:574）与
    ``get_org_scope`` 都把 ``data_scope == "all"`` 当作**全局管理员**放行，
    而原实现（create / update / update-permissions 三处）只校验取值合法性、
    不校验**授予权限** —— 部门级 admin 可把任意账号（含自己）改成 ``all``，
    一步获得全库数据可见性（资金/项目/帮扶村/一户一档全量）。
    现与 ``_assert_can_manage_super_admin`` 同口径：仅超管可授予。

    Raises:
        HTTPException(403): 非超管试图授予 ``all``。
    """
    if data_scope != "all":
        return
    if is_superuser(current_user):
        return
    if normalize_role(getattr(current_user, "role", None)) == _SUPER_ADMIN_ROLE:
        return
    raise HTTPException(
        status_code=403,
        detail="仅超级管理员可授予「全部数据」范围",
    )


def _assert_can_manage_super_admin(
    current_user,
    target=None,
    *,
    target_role: Optional[str] = None,
) -> None:
    """仅 super_admin 可管理 super_admin 账号。

    Args:
        current_user: 发起操作的用户。
        target: 被操作的用户对象（删除/重置密码/改资料时传入）。
        target_role: 目标角色（创建/改角色时传入的新角色值）。

    Raises:
        HTTPException(403): 非超管试图管理超管账号。
    """
    if is_superuser(current_user):
        return
    if target is not None and _is_super_admin_account(target):
        raise HTTPException(status_code=403, detail="仅超级管理员可管理超级管理员账号")
    if target_role is not None and normalize_role(target_role) == _SUPER_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="仅超级管理员可管理超级管理员账号")


def _apply_user_data_scope(query, current_user, db: Session):
    """用户查询的数据域过滤（user 列表 / 待审 / staff-list 共用）。

    - ALL（super_admin / is_superuser）→ 不过滤
    - OWN_DEPT（有组织的部门级管理员）→ 本组织及下级组织（parent_id 递归子树）
    - OWN（无组织归属者）→ 仅本人

    ADR-0002 fail-closed：无组织账号绝不落入"不过滤"分支。

    R28 口径（W1-#10 fail-closed）：``db`` 为**必填**参数 —— 旧实现默认
    ``db=None``，缺失时静默退化为「仅本组织」，staff-list / 待审列表两处调用方
    因此漏看下级组织成员。子树解析必须依赖真实会话；漏传在调用点直接 TypeError。
    """
    scope = get_data_scope(current_user)
    if scope == DataScope.OWN:
        return query.filter(User.id == getattr(current_user, "id", None))
    if scope == DataScope.OWN_DEPT:
        from app.core.data_permission import _get_org_subtree

        org_id = getattr(current_user, "organization_id", None) or getattr(current_user, "org_id", None)
        if org_id is None:
            return query.filter(User.id == getattr(current_user, "id", None))
        subtree, _names = _get_org_subtree(db, org_id)
        # 组织不存在（被删除/悬空 id）→ 子树为空，退化为 in_([org_id]) 只命中悬空
        # 组织自身名下的记录，仍不会放大可见范围（fail-closed）。
        return query.filter(User.organization_id.in_(subtree or [org_id]))
    return query


def _assert_user_org_reachable(db: Session, current_user, target_user, *, action: str = "管理该用户") -> None:
    """用户管理写端点的跨组织越权守卫（H4，涉军审计红线）。

    历史缺陷：这些端点只有 ``require_admin``（角色级）+ 提权收敛，
    完全没有组织可达性校验 —— role=admin、organization_id=2 的部门管理员可以
    对其它组织的用户改角色/改组织/停用/删除/重置密码/分配权限（越权管理）。

    此处与 organization.py ``_assert_org_write_scope`` / fund_budgets.py 同口径，
    统一走 core.data_permission.assert_org_reachable：超管直接放行；非超管要求
    目标用户所属组织在自身组织子树内，否则 403。

    目标用户 ``organization_id`` 为 None 时 fail-closed（ADR-0002）：无组织归属的
    账号不属于任何组织树分支，部门级管理员不得管理（仅超管可管理），否则会出现
    "无组织用户人人可管"的漏洞。
    """
    from app.core.data_permission import assert_org_reachable

    target_org_id = getattr(target_user, "organization_id", None)
    if target_org_id is None:
        if is_superuser(current_user):
            return
        raise HTTPException(
            status_code=403,
            detail="目标用户无组织归属，仅超级管理员可管理无组织用户",
        )
    assert_org_reachable(db, current_user, target_org_id, action=action)


def _require_admin_user(current_user=Depends(get_current_user)):  # noqa: B008 - FastAPI 依赖
    """路由级管理员校验依赖（供带缓存装饰器的静态选项端点使用）。

    W15 深审 #9：cache_result 装饰器在缓存命中时直接返回缓存值，
    函数体内联的 require_admin 被整体跳过（认证依赖仍会执行，但不再校验角色），
    普通用户命中缓存即可读取管理员专属选项。把校验放进路由依赖后，
    缓存命中与否都必须先过权限。
    """
    require_admin(current_user)
    return current_user


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
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    keyword: Optional[str] = None,
    username: Optional[str] = None,
    is_active: Optional[bool] = None,
    organization_id: Optional[int] = None,
    role: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户列表 - 支持按用户名、关键词、状态、组织、角色筛选

    ``username`` 与 ``keyword`` 的区别：前者只匹配账号名（前端「用户名」搜索框），
    后者模糊匹配账号名/姓名/邮箱（前端「姓名」搜索框）。
    历史缺陷：前端一直发 ``username``，而后端没有该形参，FastAPI 静默忽略未知
    query 参数 → 「用户名」搜索框完全不生效（测试只断言参数已发送，故全绿）。
    """
    require_admin(current_user)
    query = db.query(User)

    # 数据范围收口（ADR-0002 fail-closed）：唯一事实源 core.data_permission。
    # R28 统一口径：改走共享的 _apply_user_data_scope（OWN_DEPT = 本组织及子树，
    # parent_id 递归），与 /pending、/staff-list 同一实现。旧实现内联按
    # Organization.path 前缀匹配子孙组织 —— 依赖 path 已被回填，遗留库或直写
    # 组织的 path 缺失时会静默漏数据；且同文件三处各自实现，口径容易漂移。
    query = _apply_user_data_scope(query, current_user, db=db)

    if username:
        query = query.filter(User.username.contains(username))

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
    # R29 探测：本端点 page/page_size 是裸 int（无 Query(ge/le) 约束）。
    # SQLite 语义下 LIMIT -1 等于不限量，OFFSET 负数属非法偏移 —— 裸传
    # (page-1)*page_size / limit 可被 page_size=-1 或超大值一次拉全表
    # （既是 DoS 面也是信息暴露面）。与 feedback/rbac/data_sync 同口径，
    # 用仓库唯一分页钳制入口收敛，避免再各处 max(skip, 0) 各写一遍。
    page_size = coerce_page_param(page_size, DEFAULT_PAGE_SIZE)
    offset, page_size = clamp_offset_limit((page - 1) * page_size, page_size)
    users = query.options(joinedload(User.organization)).offset(offset).limit(page_size).all()

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
                "permission_pack_id": u.permission_pack_id,
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
    """获取待审核（未激活）的用户列表，供管理员审核

    H4：按调用者数据域收敛 —— 原实现列**全库**待审核用户，任意部门管理员可看到
    其它组织的待审账号（含用户名/邮箱），属跨组织信息外泄。约束与 ``list_users``
    同一口径：super_admin/is_superuser 全量、部门级管理员本组织及子树、无组织者仅本人。
    """
    require_admin(current_user)

    query = db.query(User).filter(User.is_active == False)  # noqa: E712
    # R28 口径修正：传 db 以解析组织子树。旧调用漏传 db，共享函数静默退化为
    # 「仅本组织」，与 docstring 的 «本组织及子树» 契约（及 list_users/staff-list）
    # 不一致 —— 部门级管理员会漏看下级组织的待审账号。
    query = _apply_user_data_scope(query, current_user, db=db)
    pending_users = query.all()

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
    keyword: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取活跃用户列表，供任务分配/审批转交等场景使用（任何登录用户均可访问）"""
    query = db.query(User).filter(User.is_active == True)  # noqa: E712
    # 数据范围收口（ADR-0002 fail-closed）：与 /users 列表共用 _apply_user_data_scope ——
    # OWN_DEPT 为**本组织及子树**。旧实现此处内联 `organization_id == 本组织`（不含
    # 子树），同一部门级管理员在 /users 与 /staff-list 看到的成员集合不一致
    # （R28 统一口径；无组织管理员仍由 get_data_scope 收口为 OWN，不会跳过过滤）。
    query = _apply_user_data_scope(query, current_user, db=db)

    # 关键词检索（审批转交/任务分配的远程搜索；原 /user-management 列表能力迁移至此）
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.filter(
            User.username.contains(kw) | User.full_name.contains(kw)
        )
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
    # H4 补口（跨组织越权读取）：非本人查看详情时目标用户须在自身组织子树内
    # （与 update/delete/permissions/reset-password 同口径）。原实现只查角色级
    # admin，部门级 admin 可通过遍历 id 读取他组织用户详情（手机号/邮箱/组织）。
    if user_id != current_user.id:
        _assert_user_org_reachable(db, current_user, user, action="查看该用户详情")

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

    # 邮箱归一化：空串/纯空白视同"未填写"（统一存 NULL）。
    # 历史缺陷：前端未填邮箱时提交 ""，而查重分支 `if data.email` 会短路跳过查重，
    # 但 User.email 有 UNIQUE 约束 → 第二个"未填邮箱"的用户插入即触发
    # IntegrityError（500）。归一到 None 后多行 NULL 不违反唯一约束。
    email = (data.email or "").strip() or None
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="邮箱已被使用")

    # 验证组织是否存在（如果指定了组织）
    if data.organization_id:
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == data.organization_id).first()
        if not org:
            raise HTTPException(status_code=400, detail=f"组织ID {data.organization_id} 不存在")
        # H4 补口（跨组织越权写入，2026-10-16 收尾）：与 update/delete/permissions/
        # admin-reset-password 的 _assert_user_org_reachable 同口径 —— 非超管只能把
        # 新用户创建在**自身组织子树**内，否则部门级 admin 可向任意组织投放账号
        # （含 admin 角色账号，构成对目标组织的持久渗透）。
        from app.core.data_permission import assert_org_reachable

        assert_org_reachable(db, current_user, data.organization_id, action="在该组织下创建用户")

    # 验证角色有效性（兼容历史角色值：approval_leader/manager→admin，operator→user）
    role = normalize_role(data.role)
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"无效的角色: {role}")

    # 提权收敛：仅 super_admin 可创建 super_admin 账号
    _assert_can_manage_super_admin(current_user, target_role=role)

    # 验证数据范围有效性
    data_scope = data.data_scope or "org"
    if data_scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"无效的数据范围: {data_scope}")
    # W25：授予「全部数据」仅超管可为（否则部门级 admin 可一步制造全库可见账号）
    _assert_can_grant_data_scope(current_user, data_scope)

    # 禁止创建无组织管理员（产品决策 2026-09-14）：部门级管理员的职责边界就是其组织，
    # 无组织会让数据范围失去锚点（修复前更会因过滤被跳过而越权枚举全库用户）。
    if role in ("admin", "super_admin") and not data.organization_id:
        raise HTTPException(
            status_code=400,
            detail="管理员必须指定所属组织：请在“所属组织”中选择该管理员管辖的组织",
        )

    # 密码策略校验：与 admin-reset-password / change-password 保持一致
    # （此前管理员可绕过策略设置任意弱口令，E2E 回归发现的不一致）
    from app.core.security import PasswordPolicy

    is_valid, policy_msg = PasswordPolicy.validate(data.password, username=data.username)
    if not is_valid:
        raise HTTPException(status_code=400, detail=policy_msg)

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
        email=email,
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
        # H4 补口（跨组织越权写入）：非超管只能把用户改到**自身组织子树**内的组织，
        # 否则可把账号“推入”他组织（含改组织后脱离自身管理，或向目标组织渗透）。
        from app.core.data_permission import assert_org_reachable

        assert_org_reachable(
            db, current_user, update_fields["organization_id"], action="把用户移动到该组织"
        )

    # 验证角色有效性（归一化兼容历史角色值）
    if "role" in update_fields and update_fields["role"]:
        update_fields["role"] = normalize_role(update_fields["role"])
        if update_fields["role"] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="无效的角色")

    # 提权收敛：非超管既不能改动 super_admin 账号，也不能把账号提升为 super_admin
    _assert_can_manage_super_admin(current_user, target=user)
    if "role" in update_fields:
        _assert_can_manage_super_admin(current_user, target_role=update_fields["role"])

    # H4：跨组织越权守卫（目标用户必须在自身组织子树内）
    _assert_user_org_reachable(db, current_user, user, action="修改该用户")

    # 禁止把管理员改成“无组织”（与创建同一不变式：管理员必须有组织）
    effective_role = normalize_role(update_fields.get("role") or user.role)
    effective_org = update_fields["organization_id"] if "organization_id" in update_fields else user.organization_id
    if effective_role in ("admin", "super_admin") and not effective_org:
        raise HTTPException(
            status_code=400,
            detail="管理员必须指定所属组织：不能将管理员改为无组织状态",
        )

    # 验证数据范围有效性
    if "data_scope" in update_fields and update_fields["data_scope"]:
        if update_fields["data_scope"] not in VALID_SCOPES:
            raise HTTPException(status_code=400, detail="无效的数据范围")
        # W25：授予「全部数据」仅超管可为
        _assert_can_grant_data_scope(current_user, update_fields["data_scope"])

    # 邮箱归一化 + 唯一性校验。
    # 历史缺陷：更新路径既不归一化也不查重 —— ① 提交 "" 会占住邮箱唯一键
    # （第二个空邮箱用户更新即 500）；② 改成已存在的邮箱同样撞 UNIQUE 约束 500。
    if "email" in update_fields:
        email = (update_fields["email"] or "").strip() or None
        update_fields["email"] = email
        if email and db.query(User).filter(User.email == email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="邮箱已被使用")

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

    # 提权收敛：仅 super_admin 可删除 super_admin 账号
    _assert_can_manage_super_admin(current_user, target=user)

    # H4：跨组织越权守卫（删除他组织用户属越权管理）
    _assert_user_org_reachable(db, current_user, user, action="删除该用户")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    # 级联清理后再删除：按外键的 ondelete 策略清理/置空所有引用 users.id 的表。
    # 历史缺陷：此处原为直接 `db.delete(user)` —— 而 machine_code.created_by 等
    # 外键既无 ondelete 声明又非空，删除"创建过机器码"的用户会撞外键约束，
    # safe_commit 重新抛出原始异常 → 500（且没有任何中文提示）。
    # 级联服务（含"合规留痕表只置空绝不物理删除"的保护）早已存在，只是从未接线。
    from app.services.user_cascade_delete_service import UserCascadeDeleteService

    cascade_result = UserCascadeDeleteService(db).delete_user_cascade(user_id)
    if not cascade_result.get("success"):
        raise HTTPException(status_code=400, detail=cascade_result.get("message") or "删除用户失败")

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

    # 提权收敛：非超管既不能改动 super_admin 账号，也不能把账号提升为 super_admin
    _assert_can_manage_super_admin(current_user, target=user)
    if "role" in update_fields:
        _assert_can_manage_super_admin(current_user, target_role=update_fields["role"])

    # H4：跨组织越权守卫（分配他组织用户的权限属越权管理）
    _assert_user_org_reachable(db, current_user, user, action="管理该用户权限")

    # 验证数据范围有效性
    if "data_scope" in update_fields:
        if update_fields["data_scope"] not in VALID_SCOPES:
            raise HTTPException(status_code=400, detail=f"无效的数据范围: {update_fields['data_scope']}")
        # W25：授予「全部数据」仅超管可为
        _assert_can_grant_data_scope(current_user, update_fields["data_scope"])

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


@router.get(
    "/roles/options",
    summary="获取角色选项",
    dependencies=[Depends(_require_admin_user)],
)
# R12：默认键包含 current_user 的 repr（含内存地址），每次请求键都不同 → 缓存永不
# 命中。三处 options 返回内容与调用者无关（静态数据），键固定为函数名。
@cache_result(ttl=OPTIONS_CACHE_TTL, key_builder=lambda *a, **k: "role-options")
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


@router.get(
    "/data-scopes/options",
    summary="获取数据范围选项",
    dependencies=[Depends(_require_admin_user)],
)
@cache_result(ttl=OPTIONS_CACHE_TTL, key_builder=lambda *a, **k: "data-scope-options")
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


@router.get(
    "/permissions/options",
    summary="获取权限选项",
    dependencies=[Depends(_require_admin_user)],
)
@cache_result(ttl=OPTIONS_CACHE_TTL, key_builder=lambda *a, **k: "permission-options")
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

    # 提权收敛：仅 super_admin 可重置 super_admin 账号的密码，
    # 否则部门级管理员可直接接管超级管理员账号（改密 + 吊销其全部令牌）
    _assert_can_manage_super_admin(current_user, target=user)

    # H4：跨组织越权守卫（重置他组织用户密码属越权接管）
    _assert_user_org_reachable(db, current_user, user, action="重置该用户密码")

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

    # 批次 3（危险操作强制审计）：管理员重置他人密码 = 账号接管级操作
    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action="admin_reset_password",
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", ""),
        resource_type="user",
        resource_id=user_id,
        details={"target_username": user.username, "forced_change": True},
    )

    return {"code": 200, "message": "密码重置成功"}


@router.post("/{user_id}/unlock", summary="解锁被登录失败锁定的账号")
async def unlock_user(
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员手动解锁账号（登录失败次数达阈值后的锁定）。

    锁定本身由 LockoutService 维护；这里只清除计数与锁定标记，不触碰密码与令牌。
    动作写审计（account_unlock），可追溯到操作人。
    """
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    from app.services.lockout_service import get_lockout_service
    from app.utils.audit_logger import AuditLogger

    get_lockout_service().clear(user, db)
    AuditLogger.log(
        action="account_unlock",
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", ""),
        resource_type="user",
        resource_id=user_id,
        details={"target_username": user.username},
    )
    return success_response(data={"unlocked": True}, message="账号已解锁")


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

    # 读取内容并校验大小（R2 第二层：分块读取 + 滚动计数，超限即停，
    # 不再先整包入内存再比较——2MB 上限下峰值可控）
    content = await read_upload_with_limit(
        avatar, 2 * 1024 * 1024,
        status_code=400,
        error_detail="头像文件不能超过 2MB",
    )

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
