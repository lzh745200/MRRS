"""
菜单权限管理 API

提供菜单权限的查询和配置功能：
- 获取当前用户可见菜单
- 获取所有菜单定义（管理员）
- 获取/设置用户菜单权限配置

菜单定义采用前后端同步模式：
- 后端定义用于 API 返回和权限校验
- 前端定义用于本地降级和菜单渲染
- 两者必须同步修改
"""

import json
import logging
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import normalize_role
from app.core.database import get_db
from app.core.security import (
    get_current_user,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
)
from app.models.user import User
from app.models.permission_pack import PermissionPack
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log


def _is_admin(user) -> bool:
    """检查用户是否为管理员"""
    return user.role in (ROLE_ADMIN, ROLE_SUPER_ADMIN) or user.is_superuser


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/menus", tags=["菜单权限管理"])


# ==================== 菜单定义 ====================
# 前后端必须同步修改！

MENU_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "dashboard",
        "label": "工作台",
        "path": "/dashboard",
        "icon": "HomeFilled",
        "order": 1,
        "roles": None,  # 所有角色可见
    },
    {
        "key": "villages",
        "label": "帮扶村管理",
        "path": "/villages",
        "icon": "Location",
        "order": 2,
        "roles": None,
    },
    {
        "key": "schools",
        "label": "帮扶学校管理",
        "path": "/schools",
        "icon": "School",
        "order": 3,
        "roles": None,
    },
    {
        "key": "projects",
        "label": "帮扶项目管理",
        "path": "/projects",
        "icon": "Folder",
        "order": 4,
        "roles": None,
    },
    {
        "key": "funds-admin",
        "label": "经费管理",
        "path": "/funds",
        "icon": "Money",
        "order": 5,
        # 普通用户可完整操作经费管理（申请/审批/拨付/结算全流程）
        "roles": ["admin", "super_admin", "user", "viewer"],
    },
    {
        "key": "funds-user",
        "label": "经费申请",
        "path": "/funds/user",
        "icon": "Money",
        "order": 6,
        "roles": ["user", "viewer"],
    },
    {
        "key": "funds-lifecycle",
        "label": "资金周期",
        "path": "/funds/lifecycle",
        "icon": "Money",
        "order": 6,
        "roles": ["admin", "super_admin", "user", "viewer"],
    },
    {
        "key": "funds-settlement",
        "label": "决算结算",
        "path": "/funds/settlement",
        "icon": "Money",
        "order": 7,
        "roles": ["admin", "super_admin", "user", "viewer"],
    },
    {
        "key": "policies",
        "label": "政策法规",
        "path": "/policies",
        "icon": "Document",
        "order": 7,
        "roles": None,
    },
    {
        "key": "rural-works",
        "label": "乡村工作",
        "path": "/rural-works",
        "icon": "Sunny",
        "order": 8,
        "roles": None,
    },
    {
        "key": "approval",
        "label": "审批管理",
        "path": "/approval/pending",
        "icon": "Stamp",
        "order": 9,
        "roles": ["admin", "super_admin"],
    },
    {
        "key": "helpData",
        "label": "帮扶数据管理",
        "icon": "TrendCharts",
        "order": 10,
        "roles": ["admin", "super_admin", "user"],
        "children": [
            {
                "key": "comprehensive-entry",
                "label": "综合数据录入",
                "path": "/data-entry/comprehensive",
                "roles": None,
            },
            {
                "key": "batch-import",
                "label": "数据批量导入",
                "path": "/data-package",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-verify",
                "label": "数据校验审核",
                "path": "/data-verify",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "validation-rules",
                "label": "校验规则管理",
                "path": "/data-verify/rules",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-analysis",
                "label": "数据统计分析",
                "path": "/data-analysis",
                "roles": None,
            },
            {
                "key": "report-templates",
                "label": "报表模板管理",
                "path": "/report-templates",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "report-export",
                "label": "报表导出",
                "path": "/report-export",
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "analytics",
        "label": "数据分析",
        "icon": "DataAnalysis",
        "order": 11,
        "roles": None,
        "children": [
            {
                "key": "analytics-dashboard",
                "label": "分析仪表盘",
                "path": "/analytics/dashboard",
                "roles": None,
            },
            {
                "key": "analytics-map",
                "label": "地图可视化",
                "path": "/analytics/map",
                "roles": None,
            },
            {
                "key": "work-analysis",
                "label": "工作分析",
                "path": "/analytics/work-analysis",
                "roles": None,
            },
        ],
    },
    {
        "key": "data-upload",
        "label": "数据上报",
        "icon": "Upload",
        "order": 12,
        "roles": None,
        "children": [
            {
                "key": "data-package-report",
                "label": "数据上报",
                "path": "/data-package/report",
                "roles": None,
            },
            {
                "key": "data-package-receive",
                "label": "接收数据包",
                "path": "/data-package/receive",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-package-list",
                "label": "数据包列表",
                "path": "/data-package/list",
                "roles": None,
            },
            {
                "key": "data-package-version",
                "label": "版本管理",
                "path": "/data-package/version",
                "roles": None,
            },
            {
                "key": "task-package-admin",
                "label": "任务数据包管理",
                "path": "/data-package/admin",
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "data",
        "label": "数据管理",
        "icon": "FolderOpened",
        "order": 13,
        "roles": ["admin", "super_admin"],
        "children": [
            {
                "key": "data-overview",
                "label": "数据总览",
                "path": "/data-management/overview",
                "roles": None,
            },
            {
                "key": "user-backup",
                "label": "用户数据备份",
                "path": "/data-management/backup",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-quality",
                "label": "数据质量监控",
                "path": "/data-management/quality",
                "roles": None,
            },
            {
                "key": "data-logs",
                "label": "操作日志",
                "path": "/data-management/logs",
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "batch-operations",
        "label": "批量操作",
        "icon": "Operation",
        "path": "/batch",
        "order": 14,
        "roles": None,
    },
    {
        "key": "system",
        "label": "系统管理",
        "icon": "Setting",
        "order": 99,
        "roles": ["admin", "super_admin"],
        "children": [
            {
                "key": "machine-code",
                "label": "机器码管理",
                "path": "/admin/machine-code",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "pass-code",
                "label": "通行码管理",
                "path": "/organizations/pass-code",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "users-orgs",
                "label": "用户与组织管理",
                "path": "/system/users-orgs",
                "roles": ["admin", "super_admin"],
            },
            # 角色权限管理和菜单权限管理已合并到用户管理页面中的"角色/权限"子模块
            # /system/roles → redirect /system/users
            # /system/menu-permissions → redirect /system/users
            {
                "key": "system-config",
                "label": "系统配置",
                "path": "/system/config",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "audit",
                "label": "安全审计",
                "path": "/system/audit",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "health",
                "label": "系统健壮性",
                "path": "/system/health",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "feedback",
                "label": "反馈管理",
                "path": "/system/feedback",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "backup",
                "label": "备份管理",
                "path": "/system/backup",
                # 普通用户只读可见（2026-08 产品要求）；写操作仍由后端 require_admin 把关
                "roles": ["admin", "super_admin", "user"],
            },
            {
                "key": "cache",
                "label": "缓存管理",
                "path": "/system/cache",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "monitor",
                "label": "系统监控",
                "path": "/system/monitor",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "help",
                "label": "帮助文档",
                "path": "/system/help",
                "roles": None,
            },
            {
                "key": "health-check",
                "label": "健康检查",
                "path": "/system/health-check",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "about",
                "label": "关于系统",
                "path": "/system/about",
                "roles": None,
            },
            {
                "key": "update-logs",
                "label": "更新日志",
                "path": "/system/update-logs",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "user-permissions",
                "label": "用户权限",
                "path": "/system/user-permissions",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "system-permission-packs",
                "label": "权限包管理",
                "path": "/system/permission-packs",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "tasks",
                "label": "后台任务",
                "path": "/system/tasks",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "secrets",
                "label": "密钥管理",
                "path": "/system/secrets",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "i18n",
                "label": "多语言",
                "path": "/system/i18n",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-tier",
                "label": "数据分级",
                "path": "/system/data-tier",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "map-tiles",
                "label": "地图瓦片",
                "path": "/system/map-tiles",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "environment",
                "label": "运行环境",
                "path": "/system/environment",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "zero-trust",
                "label": "零信任",
                "path": "/system/zero-trust",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "error-reports",
                "label": "错误上报",
                "path": "/system/error-reports",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "system-overview",
                "label": "系统总览",
                "path": "/system/overview",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "admin-dashboard",
                "label": "管理面板",
                "path": "/admin/dashboard",
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "messages",
        "label": "消息中心",
        "icon": "Message",
        "path": "/message",
        "order": 110,
        "roles": None,
    },
    {
        "key": "effectiveness",
        "label": "帮扶成效",
        "icon": "TrendCharts",
        "order": 111,
        "roles": None,
        "children": [
            {
                "key": "effectiveness-rankings",
                "label": "成效排名",
                "path": "/effectiveness/rankings",
                "roles": None,
            },
            {
                "key": "effectiveness-evaluate",
                "label": "成效评估",
                "path": "/effectiveness/evaluate",
                "roles": None,
            },
        ],
    },
    {
        "key": "todos",
        "label": "待办事项",
        "icon": "Select",
        "path": "/todos",
        "order": 112,
        "roles": None,
    },
    {
        "key": "sentiment",
        "label": "情感分析",
        "icon": "ChatDotRound",
        "path": "/sentiment",
        "order": 113,
        "roles": None,
    },
    {
        "key": "reminder",
        "label": "提醒中心",
        "icon": "Bell",
        "path": "/reminder",
        "order": 114,
        "roles": None,
    },
    {
        "key": "checkin",
        "label": "驻村工作台",
        "icon": "Location",
        "path": "/rural-works/checkin",
        "order": 115,
        "roles": None,
    },
]


@lru_cache(maxsize=8)
def _get_role_default_menu_keys(role: str) -> frozenset[str]:
    """根据角色返回默认可见的菜单key集合"""
    role = normalize_role(role)  # 兼容旧角色值（manager/approval_leader→admin, operator→user）
    role_menu_keys: set[str] = set()

    def traverse(menus: list[dict[str, Any]]) -> None:
        for m in menus:
            allowed_roles = m.get("roles")
            if allowed_roles is None or role in allowed_roles:
                role_menu_keys.add(m["key"])
            children = m.get("children")
            if children:
                traverse(children)

    traverse(MENU_DEFINITIONS)
    return frozenset(role_menu_keys)


def _get_user_bound_pack(user: User, db: Session) -> PermissionPack | None:
    """获取用户绑定的启用中权限包（未绑定/已停用/包不存在时返回 None）"""
    pack_id = getattr(user, "permission_pack_id", None)
    # 防御：仅接受真实 int（Mock 用户/脏数据直接跳过，回落角色默认）
    if not isinstance(pack_id, int) or isinstance(pack_id, bool) or pack_id <= 0:
        return None
    return (
        db.query(PermissionPack)
        .filter(PermissionPack.id == pack_id, PermissionPack.is_active.is_(True))
        .first()
    )


# 全角色公开模块（2026-08-15 产品要求）：
# 政策法规与数据分析对普通用户（user/viewer）与管理员完全一致，
# 不受用户级 allowed_menus / 权限包 / 角色默认配置的裁剪。
_PUBLIC_ACCESS_KEYS: frozenset[str] = frozenset({
    "policies",                    # 政策法规
    "helpData",                    # 数据分析的父级（帮扶数据管理）
    "data-analysis",               # 数据统计分析
    "analytics",                   # 数据分析
    "analytics-dashboard",         # 分析仪表盘
    "analytics-map",               # 地图可视化
    "work-analysis",               # 工作分析
})


def _get_user_accessible_menu_keys(user: User, db: Session) -> set[str]:
    """获取用户实际可见的菜单key集合

    优先级：用户级 allowed_menus 配置 > 绑定的启用中权限包 > 角色默认。
    之后无条件并入 _PUBLIC_ACCESS_KEYS（政策法规/数据分析全角色公开）。
    """
    allowed = user.allowed_menus_list
    if allowed is not None:
        # 用户级别配置优先
        keys = set(allowed)
    else:
        # 其次：绑定的启用中权限包（菜单套餐）
        pack = _get_user_bound_pack(user, db)
        if pack is not None:
            keys = set(pack.menu_keys_list)
        else:
            # 否则继承角色默认
            keys = set(_get_role_default_menu_keys(user.role))
    # 公开模块强制并入，保证普通用户政策法规/数据分析与管理员一致
    keys |= _PUBLIC_ACCESS_KEYS
    return keys


def _filter_menu_tree(menus: list[dict[str, Any]], allowed_keys: set[str]) -> list[dict[str, Any]]:
    """根据允许的菜单key集合过滤菜单树"""
    result: list[dict[str, Any]] = []
    for m in menus:
        if m["key"] in allowed_keys:
            filtered: dict[str, Any] = {k: v for k, v in m.items() if k != "children"}
            children = m.get("children")
            if children:
                filtered_children = _filter_menu_tree(children, allowed_keys)
                if filtered_children:
                    filtered["children"] = filtered_children
            result.append(filtered)
    return result


def _flatten_menu_keys(menus: list[dict[str, Any]]) -> set[str]:
    """扁平化所有菜单key"""
    keys: set[str] = set()

    def traverse(items: list[dict[str, Any]]) -> None:
        for item in items:
            keys.add(item["key"])
            if item.get("children"):
                traverse(item["children"])

    traverse(menus)
    return keys


# ==================== 请求/响应模型 ====================


class UserMenuUpdate(BaseModel):
    """设置用户菜单权限"""
    menu_keys: Optional[list[str]] = None  # None = 恢复角色默认菜单


class MenuItemResponse(BaseModel):
    """菜单项响应"""
    key: str
    label: str
    path: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    roles: Optional[list[str]] = None
    children: Optional[list["MenuItemResponse"]] = None


# ==================== API 接口 ====================


@router.get(
    "/accessible",
    summary="获取当前用户可见菜单",
    response_model=dict,
)
async def get_accessible_menus(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    返回当前登录用户可访问的完整菜单树。

    过滤逻辑：
    1. 用户设置了 allowed_menus -> 使用用户配置（source="user"）
    2. 用户绑定了启用中的权限包 -> 使用权限包菜单（source="pack"）
    3. 用户未设置 -> 使用角色默认菜单（source="role"）
    4. 子菜单同时受 roles 字段约束
    """
    allowed_keys = _get_user_accessible_menu_keys(current_user, db)
    accessible_menus = _filter_menu_tree(MENU_DEFINITIONS, allowed_keys)
    if current_user.allowed_menus_list is not None:
        source = "user"
    elif _get_user_bound_pack(current_user, db) is not None:
        source = "pack"
    else:
        source = "role"
    logger.debug(
        "菜单查询: user=%s role=%s source=%s keys=%s",
        current_user.username, current_user.role, source, sorted(allowed_keys),
    )
    return {
        "success": True,
        "data": accessible_menus,
        "source": source,
    }


@router.get(
    "/all",
    summary="获取所有菜单定义（管理员）",
    response_model=dict,
)
async def get_all_menus(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    返回所有菜单项的完整定义，包含 roles 信息，供管理员配置使用
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    # 返回完整定义（包含 roles），供前端 el-tree 使用
    return {
        "success": True,
        "data": MENU_DEFINITIONS,
    }


@router.get(
    "/user-menus/{user_id}",
    summary="获取指定用户的菜单权限配置",
    response_model=dict,
)
async def get_user_menu_config(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取用户的菜单权限配置详情"""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 用户当前配置
    user_menu_keys = user.allowed_menus_list  # None = 使用角色默认
    role_default_keys = _get_role_default_menu_keys(user.role)
    all_valid_keys = _flatten_menu_keys(MENU_DEFINITIONS)

    return {
        "success": True,
        "data": {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "mode": "custom" if user_menu_keys is not None else "role_default",
            "menu_keys": user_menu_keys if user_menu_keys is not None else list(role_default_keys),
            "is_customized": user_menu_keys is not None,
            "role_default_keys": list(role_default_keys),
            "all_valid_keys": list(all_valid_keys),
        },
    }


@router.put(
    "/user-menus/{user_id}",
    summary="设置用户的菜单权限",
    response_model=dict,
)
async def set_user_menu_config(
    user_id: int,
    data: UserMenuUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    设置用户的菜单权限。

    - menu_keys = None: 恢复角色默认菜单（即删除用户级配置）
    - menu_keys = []: 清空用户所有菜单
    - menu_keys = ["key1", "key2"]: 自定义菜单配置
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不能修改自己的菜单配置（防止管理员锁死自己）
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的菜单权限")

    # 获取所有有效的菜单 key
    all_valid_keys = _flatten_menu_keys(MENU_DEFINITIONS)

    if data.menu_keys is None:
        # 恢复角色默认 -> 清除 allowed_menus 字段
        user.allowed_menus = None
        mode = "role_default"
        message = "已恢复角色默认菜单"
    elif len(data.menu_keys) == 0:
        # 清空 -> 无菜单
        user.allowed_menus = json.dumps([])
        mode = "custom"
        message = "已清空用户菜单权限（用户将无法访问任何菜单）"
    else:
        # 验证所有 key 是否有效
        invalid_keys = [k for k in data.menu_keys if k not in all_valid_keys]
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"存在无效的菜单key: {', '.join(invalid_keys)}",
            )
        user.allowed_menus = json.dumps(data.menu_keys)
        mode = "custom"
        message = f"已设置用户菜单权限（共 {len(data.menu_keys)} 个菜单）"

    safe_commit(db)
    try:
        write_work_log(db, "menu", "update_menus", user.id, f"设置用户菜单权限: {user.username}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败")
    logger.info(f"管理员 {current_user.username} 设置用户 {user.username} 菜单权限: {mode}")

    return {
        "success": True,
        "message": message,
        "mode": mode,
    }


@router.get(
    "/role-defaults",
    summary="获取所有角色的默认菜单配置",
    response_model=dict,
)
async def get_role_default_menus(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    返回所有角色的默认菜单配置，用于管理员参考
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    all_roles = [
        "super_admin", "admin", "user", "viewer",
    ]
    role_menus: dict[str, list[str]] = {}
    for role in all_roles:
        keys = list(_get_role_default_menu_keys(role))
        role_menus[role] = keys

    return {
        "success": True,
        "data": role_menus,
    }
