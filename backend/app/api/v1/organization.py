"""
组织管理API
支持部门单位和帮扶单位的层级管理
与权限管理集成：组织创建、修改需要管理员权限
"""

import io
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.cache import cache_manager
from ...core.database import get_db
from ...core.logging import logger
from ...core.permission_utils import is_superuser
from ...core.response import ok_list
from ...core.security import get_current_user
from ...models.organization import Organization, OrganizationLevel, OrganizationType
from ...models.user import User
from ...services.organization_service import OrganizationService
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log
from app.core.response import success_response

router = APIRouter(prefix="/organizations", tags=["组织管理"])


def _invalidate_dashboard_cache_safe() -> None:
    """组织写操作后失效工作台统计缓存，保证删除/新增/停用后总数立即更新。"""
    try:
        from app.api.v1.data.data.dashboard import invalidate_dashboard_cache
        invalidate_dashboard_cache()
    except Exception:  # pragma: no cover
        logger.debug("仪表盘缓存失效失败")


# ==================== Pydantic模型 ====================


class OrganizationBase(BaseModel):
    name: str
    code: Optional[str] = None
    org_type: Optional[str] = None  # department 或 support_unit
    level: Optional[str] = None
    parent_id: Optional[int] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True
    description: Optional[str] = None
    sort_order: int = 0


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    org_type: Optional[str] = None
    level: Optional[str] = None
    parent_id: Optional[int] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class OrganizationSortItem(BaseModel):
    """组织排序项"""

    id: int
    sort_order: int


class BatchUpdateSortRequest(BaseModel):
    """批量更新排序请求"""

    items: List[OrganizationSortItem]


class OrganizationResponse(OrganizationBase):
    id: int
    level: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationTreeNode(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    org_type: Optional[str] = None
    level: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: bool
    children: List["OrganizationTreeNode"] = []

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    """分页响应"""

    items: List[OrganizationResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


# ==================== API端点 ====================


@router.get("")
async def get_organizations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    org_type: Optional[str] = None,
    parent_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    search: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """获取组织列表（分页）"""
    # 无过滤条件的默认列表请求使用缓存（5分钟）
    _cache_key = "orgs:list"
    if not any([org_type, parent_id, is_active, keyword, search]) and page == 1 and page_size == 20:
        cached = await cache_manager.get(_cache_key)
        if cached is not None:
            return cached
    try:
        query = db.query(Organization)

        if org_type:
            query = query.filter(Organization.org_type == org_type)
        if parent_id is not None:
            query = query.filter(Organization.parent_id == parent_id)
        # is_active 参数说明：
        # - 不传递或传递 null：返回所有组织（包括已停用的）
        # - 传递 true：只返回活跃组织
        # - 传递 false：只返回已停用的组织
        if is_active is not None:
            query = query.filter(Organization.is_active == is_active)
        # 兼容前端参数名: keyword 或 search
        search_term = keyword or search
        if search_term:
            # 转义 SQL LIKE 通配符以防止注入
            escaped_term = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            # 使用 like() 方法配合 escape 参数
            query = query.filter(
                (Organization.name.like(f"%{escaped_term}%", escape="\\"))
                | (Organization.code.like(f"%{escaped_term}%", escape="\\"))
            )

        total = query.count()
        items = (
            query.order_by(Organization.sort_order, Organization.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items_list = [OrganizationResponse.model_validate(item).model_dump(mode="json") for item in items]
        result = ok_list(items=items_list, total=total, page=page, page_size=page_size)
        # 仅对默认无过滤请求写缓存
        if not any([org_type, parent_id, is_active, keyword, search]) and page == 1 and page_size == 20:
            await cache_manager.set(_cache_key, result, ttl=300)
        return result
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取组织列表失败，请稍后重试或联系管理员")


def _set_no_cache_headers(response: Response):
    """设置无缓存响应头"""
    if response:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"


def _org_level_to_number(org: Organization) -> int:
    """将组织 level 枚举值转为数字"""
    if not org.level:
        return 0
    level_str = str(org.level)
    if not level_str.startswith("level_"):
        return 0
    try:
        return int(level_str.split("_")[1])
    except (ValueError, IndexError):
        return 0


def _org_to_tree_node(org: Organization, org_dict: dict) -> dict:
    """将组织对象转为树节点字典"""
    path = _build_org_path(org.id, org_dict)
    return {
        "id": str(org.id),
        "name": org.name,
        "code": org.code or "",
        "org_type": str(org.org_type) if org.org_type else None,
        "level": _org_level_to_number(org),
        "parent_id": str(org.parent_id) if org.parent_id is not None else None,
        "is_active": org.is_active,
        "path": path,
        "description": org.description or "",
        "contact_person": org.contact_person or "",
        "contact_phone": org.contact_phone or "",
        "address": org.address or "",
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
        "children": [],
    }


def _build_org_path(org_id: int, org_dict: dict, visited: set = None) -> str:
    """构建组织路径（避免循环）"""
    if visited is None:
        visited = set()
    if org_id in visited:
        return ""
    visited.add(org_id)
    org = org_dict.get(org_id)
    if not org:
        return ""
    if not org.parent_id or org.parent_id not in org_dict:
        return f"/{org.name}"
    parent_path = _build_org_path(org.parent_id, org_dict, visited)
    return f"{parent_path}/{org.name}" if parent_path else f"/{org.name}"


def _build_org_tree(organizations: list, org_map: dict) -> list:
    """将扁平的节点字典构建为树形结构"""
    tree = []
    for org in organizations:
        node = org_map[org.id]
        if org.parent_id and org.parent_id in org_map:
            org_map[org.parent_id]["children"].append(node)
        else:
            tree.append(node)
    return tree


@router.get("/tree")
async def get_organization_tree(
    org_type: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """获取组织树形结构"""
    _set_no_cache_headers(response)
    try:
        query = db.query(Organization).filter(Organization.is_active == True)  # noqa: E712

        if org_type:
            query = query.filter(Organization.org_type == org_type)

        organizations = query.order_by(Organization.sort_order, Organization.id).all()
        org_dict = {org.id: org for org in organizations}

        org_map = {}
        for org in organizations:
            org_map[org.id] = _org_to_tree_node(org, org_dict)

        tree = _build_org_tree(organizations, org_map)
        return success_response(data=tree)
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织树失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取组织树失败，请稍后重试或联系管理员")


@router.get("/statistics/summary", summary="获取组织统计信息")
async def get_organization_statistics(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取组织机构统计数据

    返回：总数量、活跃/停用数、按类型分布、按层级分布、成员总数等
    """
    try:
        total = db.query(func.count(Organization.id)).scalar() or 0
        active = db.query(func.count(Organization.id)).filter(
            Organization.is_active == True  # noqa: E712
        ).scalar() or 0
        inactive = total - active

        # 按类型统计
        type_rows = (
            db.query(Organization.org_type, func.count(Organization.id))
            .filter(Organization.is_active == True)  # noqa: E712
            .group_by(Organization.org_type)
            .all()
        )
        type_dist = {str(t or "unknown"): c for t, c in type_rows}

        # 按层级统计
        level_rows = (
            db.query(Organization.level, func.count(Organization.id))
            .filter(Organization.is_active == True)  # noqa: E712
            .group_by(Organization.level)
            .all()
        )
        level_dist = {str(lv or "unknown"): c for lv, c in level_rows}

        # 绑定了用户的组织数
        orgs_with_members = (
            db.query(func.count(func.distinct(User.organization_id)))
            .filter(User.organization_id.isnot(None), User.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        # 总用户数
        total_members = (
            db.query(func.count(User.id))
            .filter(User.is_active == True, User.organization_id.isnot(None))  # noqa: E712
            .scalar()
            or 0
        )

        return {
            "code": 200,
            "data": {
                "total": total,
                "active": active,
                "inactive": inactive,
                "type_distribution": type_dist,
                "level_distribution": level_dist,
                "orgs_with_members": orgs_with_members,
                "total_members": total_members,
            },
            "message": "获取统计信息成功",
        }
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织统计信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.get("/export/list", summary="导出组织列表Excel")
async def export_organizations(
    org_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出组织列表为 Excel 文件"""
    # 权限检查
    if getattr(current_user, "role", None) not in ("admin", "super_admin") and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可导出组织列表")

    try:
        from app.services.export_service import ExcelExportService

        query = db.query(Organization)
        if org_type:
            query = query.filter(Organization.org_type == org_type)
        if is_active is not None:
            query = query.filter(Organization.is_active == is_active)

        orgs = query.order_by(Organization.sort_order, Organization.id).all()

        # 构建导出数据
        export_data = []
        for org in orgs:
            # 查询成员数
            member_count = (
                db.query(func.count(User.id))
                .filter(User.organization_id == org.id, User.is_active == True)  # noqa: E712
                .scalar()
                or 0
            )
            type_label = {"department": "部门单位", "support_unit": "帮扶单位", "other": "其他"}.get(
                str(org.org_type) if org.org_type else "", str(org.org_type or "")
            )
            export_data.append(
                {
                    "name": org.name,
                    "code": org.code or "",
                    "type": type_label,
                    "level": str(org.level or ""),
                    "contact_person": org.contact_person or "",
                    "contact_phone": org.contact_phone or "",
                    "address": org.address or "",
                    "description": org.description or "",
                    "member_count": member_count,
                    "status": "正常" if org.is_active else "停用",
                    "created_at": org.created_at.strftime("%Y-%m-%d") if org.created_at else "",
                }
            )

        export_service = ExcelExportService()
        excel_bytes = export_service.export_organizations(
            organizations=export_data,
            filename="组织机构列表",
        )

        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=organizations.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"导出组织列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="导出失败")


@router.get("/my-organization", response_model=OrganizationResponse)
async def get_my_organization(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户所属组织"""
    try:
        # 优先返回用户关联的组织
        if hasattr(current_user, "organization_id") and current_user.organization_id:
            org = (
                db.query(Organization)
                .filter(
                    Organization.id == current_user.organization_id,
                    Organization.is_active == True,  # noqa: E712
                )
                .first()
            )
            if org:
                return org

        # 如果用户没有关联组织,返回第一个激活的组织
        org = (
            db.query(Organization)
            .filter(Organization.is_active == True)  # noqa: E712
            .order_by(Organization.id)
            .first()
        )

        if not org:
            raise HTTPException(status_code=404, detail="未找到组织信息")

        return org
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"获取当前用户组织失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取当前用户组织失败，请稍后重试或联系管理员")


@router.get("/my", response_model=OrganizationResponse)
async def get_my_organization_alias(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户所属组织（/my 别名，兼容前端调用）"""
    return await get_my_organization(current_user, db)


@router.get("/subordinates", response_model=List[OrganizationResponse])
async def get_subordinates(
    include_self: bool = Query(False, description="是否包含自身"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取下级组织列表"""
    try:
        query = db.query(Organization).filter(Organization.is_active == True)  # noqa: E712
        if not include_self:
            query = query.filter(Organization.parent_id.isnot(None))
        return query.order_by(Organization.sort_order, Organization.id).all()
    except Exception as e:  # pragma: no cover
        logger.error(f"获取下级组织失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取下级组织失败，请稍后重试或联系管理员")


@router.get("/types/options")
async def get_type_options():
    """获取组织类型选项"""
    return success_response(data={
        "types": [
            {"value": "department", "label": "部门单位"},
            {"value": "support_unit", "label": "帮扶单位"},
        ],
        "levels": [
            {"value": "level_1", "label": "一级单位"},
            {"value": "level_2", "label": "二级单位"},
            {"value": "level_3", "label": "三级单位"},
            {"value": "level_4", "label": "四级单位"},
        ],
    })


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取组织详情"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    return org


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    data: OrganizationCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建组织"""
    # 权限检查：仅管理员可创建组织
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    # 检查编码是否重复
    if data.code:
        existing = db.query(Organization).filter(Organization.code == data.code).first()
        if existing:
            raise HTTPException(status_code=400, detail="组织编码已存在")

    # 转换枚举类型
    org_data = data.model_dump(exclude_defaults=False)
    if org_data.get("org_type"):
        org_data["org_type"] = OrganizationType(org_data["org_type"])
    if org_data.get("level"):
        org_data["level"] = OrganizationLevel(org_data["level"])

    # 确保 is_active 有值
    if "is_active" not in org_data:
        org_data["is_active"] = True

    # 排序值自动递增：新增组织默认排到同级末尾
    # （sort_order 未显式指定或为 0 时，取当前最大值 +1）
    if not org_data.get("sort_order"):
        max_order = (
            db.query(func.max(Organization.sort_order))
            .filter(
                Organization.parent_id == org_data.get("parent_id")
                if org_data.get("parent_id")
                else Organization.parent_id.is_(None)
            )
            .scalar()
        )
        org_data["sort_order"] = (max_order or 0) + 1

    org = Organization(**org_data)
    db.add(org)
    db.flush()  # 先获取自增 id，供自动生成编码使用
    if not org.code:
        # 前端表单提示"留空自动生成"：按自增 id 生成唯一编码（id 唯一故编码唯一）
        if org.id is not None:
            org.code = f"ORG{org.id:06d}"
        else:
            # db.flush 未回填自增 id 的兜底（测试替身等场景）：随机后缀保证编码非空唯一
            import secrets

            org.code = f"ORG{secrets.token_hex(3).upper()}"
    safe_commit(db)
    db.refresh(org)
    try:
        write_work_log(db, "organization", "create", org.id, f"创建组织: {org.name}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新组织"""
    # 权限检查：仅管理员可更新组织
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    # 检查编码是否重复
    if data.code:
        existing = db.query(Organization).filter(Organization.code == data.code, Organization.id != org_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="组织编码已存在")

    update_data = data.model_dump(exclude_unset=True)

    # 安全检查：禁止将 parent_id 设为自身（防止循环引用）
    if "parent_id" in update_data and update_data["parent_id"] == org_id:
        raise HTTPException(status_code=400, detail="不能将组织自身设为上级组织")

    # 转换枚举类型
    if "org_type" in update_data and update_data["org_type"]:
        update_data["org_type"] = OrganizationType(update_data["org_type"])
    if "level" in update_data and update_data["level"]:
        update_data["level"] = OrganizationLevel(update_data["level"])

    for key, value in update_data.items():
        setattr(org, key, value)

    safe_commit(db)
    db.refresh(org)
    try:
        write_work_log(db, "organization", "update", org.id, f"更新组织: {org.name}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    return org


@router.delete("/{org_id}")
async def delete_organization(
    org_id: int,
    force: bool = Query(False, description="保留参数，暂未使用"),
    confirm_password: str = Query("", description="二次确认：输入当前用户密码"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除组织（逻辑删除：将 is_active 设为 False）

    Args:
        org_id: 组织ID
        force: 保留参数，暂未使用
        confirm_password: 二次确认密码（单机共用电脑防误删）

    Returns:
        删除结果
    """

    # 权限检查：仅管理员可删除组织
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    # 二次确认：校验当前用户密码（防共用电脑误操作）
    from app.core.security import verify_password

    user_row = db.query(User).filter(User.id == current_user.id).first()
    if not user_row or not verify_password(confirm_password, user_row.hashed_password or ""):
        raise HTTPException(status_code=400, detail="二次确认失败：密码不正确")

    logger.info(f"=== 开始删除组织 === org_id={org_id}, user={current_user.id}")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        logger.error(f"组织不存在: org_id={org_id}")
        raise HTTPException(status_code=404, detail="组织不存在")

    logger.info(f"找到组织: id={org.id}, name={org.name}")

    # 检查是否有激活的子组织（软删除的子组织不阻止父级删除）
    children = db.query(Organization).filter(
        Organization.parent_id == org_id,
        Organization.is_active == True  # noqa: E712 -- SQLAlchemy boolean filter
    ).count()
    if children > 0:
        logger.warning(f"组织有子组织: org_id={org_id}, children_count={children}")
        raise HTTPException(status_code=400, detail="该组织下有子组织，请先删除子组织")

    # 逻辑删除：将 is_active 设置为 False
    logger.info(f"执行逻辑删除: org_id={org_id}")
    org.is_active = False
    safe_commit(db)
    try:
        write_work_log(db, "organization", "delete", org_id, f"删除组织: {org.name}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover
        logger.debug("记录工作日志失败", exc_info=True)
    logger.info(f"删除成功: org_id={org_id}")
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()

    return success_response(data={
        "message": "组织已删除",
        "type": "soft_delete",
    }, message="组织已删除")


@router.get("/{org_id}/children", response_model=List[OrganizationResponse])
async def get_children(org_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取子组织"""
    return (
        db.query(Organization)
        .filter(Organization.parent_id == org_id)
        .order_by(Organization.sort_order, Organization.id)
        .all()
    )


@router.get("/{org_id}/ancestors", response_model=List[OrganizationResponse])
async def get_ancestors(org_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取祖先组织（沿父链逐级查询，避免全表加载）"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    # 沿父链逐级向上查询（组织层级通常≤5层，最多5次高效索引查询）
    ancestors = []
    visited: set = set()
    current_id = org.parent_id
    while current_id and current_id not in visited:
        visited.add(current_id)
        parent = db.query(Organization).filter(Organization.id == current_id).first()
        if not parent:
            break
        ancestors.append(parent)
        current_id = parent.parent_id

    return ancestors


class MoveOrganizationRequest(BaseModel):
    """移动组织请求体"""

    new_parent_id: Optional[int] = None


@router.post("/{org_id}/move")
async def move_organization(
    org_id: int,
    body: MoveOrganizationRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移动组织到新的父级"""
    # 权限检查：仅管理员可移动组织
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    new_parent_id = body.new_parent_id

    # 检查新父级是否存在
    if new_parent_id:
        new_parent = db.query(Organization).filter(Organization.id == new_parent_id).first()
        if not new_parent:
            raise HTTPException(status_code=404, detail="目标父组织不存在")

        # 检查是否会形成循环（沿父链逐级查询，避免全表加载）
        visited: set = set()
        check_id: Optional[int] = new_parent_id
        while check_id and check_id not in visited:
            if check_id == org_id:
                raise HTTPException(status_code=400, detail="不能将组织移动到其子组织下")
            visited.add(check_id)
            check_node = db.query(Organization).filter(Organization.id == check_id).first()
            check_id = check_node.parent_id if check_node else None

    org.parent_id = new_parent_id
    safe_commit(db)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    return success_response(data={"message": "移动成功"}, message="移动成功")


@router.post("/batch-update-sort")
async def batch_update_sort_orders(
    request: BatchUpdateSortRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量更新组织排序

    管理员接口，用于拖拽排序后批量更新排序号。

    Args:
        request: 批量更新请求，包含组织ID和排序号列表
    """
    # 权限检查：仅管理员可更新排序
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    try:
        service = OrganizationService(db)

        # 转换为字典列表
        sort_list = [{"id": item.id, "sort_order": item.sort_order} for item in request.items]

        # 批量更新
        success, updated_count = service.batch_update_sort_orders(sort_list)

        if not success:
            raise HTTPException(status_code=500, detail="批量更新排序失败")

        await cache_manager.delete("orgs:list")
        _invalidate_dashboard_cache_safe()
        return {
            "code": 200,
            "data": {"updated_count": updated_count},
            "message": f"成功更新 {updated_count} 个组织的排序",
        }
    except HTTPException:
        raise
    except Exception:  # pragma: no cover
        db.rollback()
        raise HTTPException(status_code=500, detail="批量更新排序失败，请稍后重试或联系管理员")


@router.get("/{org_id}/members", summary="获取组织成员列表")
async def get_organization_members(
    org_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定组织的成员列表"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    try:
        query = db.query(User).filter(User.organization_id == org_id, User.is_active == True)  # noqa: E712
        total = query.count()
        users = (
            query.order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name or "",
                "email": u.email or "",
                "role": u.role or "user",
                "is_active": u.is_active,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]
        return ok_list(items=items, total=total, page=page, page_size=page_size)
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织成员列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取成员列表失败")


@router.post("/{org_id}/members", summary="添加组织成员（将用户划入组织）")
async def add_organization_members(
    org_id: int,
    data: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将指定的用户划入该组织（设置 organization_id）"""
    from app.api.v1.deps import require_manager_role

    require_manager_role(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    user_ids = data.get("user_ids") or []
    if not user_ids:
        raise HTTPException(status_code=400, detail="请选择要添加的成员")

    added = 0
    for uid in user_ids:
        try:
            uid_int = int(uid)
        except (ValueError, TypeError):
            continue  # 非数字 ID 跳过，不导致整接口 500
        user = db.query(User).filter(User.id == uid_int).first()
        if user and user.is_active:
            user.organization_id = org_id
            added += 1
    safe_commit(db)
    return {"code": 200, "success": True, "message": f"已添加 {added} 名成员", "data": {"added": added}}


@router.delete("/{org_id}/members/{user_id}", summary="移除组织成员")
async def remove_organization_member(
    org_id: int,
    user_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将成员移出组织（清空 organization_id）"""
    from app.api.v1.deps import require_manager_role

    require_manager_role(current_user)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.organization_id = None
    safe_commit(db)
    return {"code": 200, "success": True, "message": "已移除成员", "data": {"removed": user_id}}


@router.get("/{org_id}/detail", summary="获取组织详情（含子组织和成员数）")
async def get_organization_detail(
    org_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取组织详情，包含子组织数量、成员数量、上级组织路径等扩展信息"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    try:
        # 子组织数量
        children_count = (
            db.query(func.count(Organization.id))
            .filter(Organization.parent_id == org_id, Organization.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        # 成员数量
        member_count = (
            db.query(func.count(User.id))
            .filter(User.organization_id == org_id, User.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        # 直接子组织列表
        children = (
            db.query(Organization)
            .filter(Organization.parent_id == org_id, Organization.is_active == True)  # noqa: E712
            .order_by(Organization.sort_order, Organization.id)
            .all()
        )
        children_list = [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code or "",
                "org_type": str(c.org_type) if c.org_type else None,
                "level": str(c.level) if c.level else None,
                "sort_order": c.sort_order,
                "is_active": c.is_active,
            }
            for c in children
        ]

        # 上级组织路径
        ancestors = []
        current_id = org.parent_id
        visited: set = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            parent = db.query(Organization).filter(Organization.id == current_id).first()
            if not parent:
                break
            ancestors.insert(0, {"id": parent.id, "name": parent.name})
            current_id = parent.parent_id

        return {
            "code": 200,
            "data": {
                "id": org.id,
                "name": org.name,
                "code": org.code or "",
                "org_type": str(org.org_type) if org.org_type else None,
                "level": str(org.level) if org.level else None,
                "parent_id": org.parent_id,
                "parent_name": ancestors[-1]["name"] if ancestors else None,
                "is_active": org.is_active,
                "sort_order": org.sort_order,
                "description": org.description or "",
                "contact_person": org.contact_person or "",
                "contact_phone": org.contact_phone or "",
                "contact_email": org.contact_email or "",
                "address": org.address or "",
                "created_at": org.created_at.isoformat() if org.created_at else None,
                "updated_at": org.updated_at.isoformat() if org.updated_at else None,
                "children_count": children_count,
                "member_count": member_count,
                "children": children_list,
                "ancestors": ancestors,
            },
            "message": "获取详情成功",
        }
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取详情失败")


@router.post("/{org_id}/activate", summary="激活组织")
async def activate_organization(
    org_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """激活指定组织（将 is_active 设为 True）"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    org.is_active = True
    safe_commit(db)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    return success_response(data={"message": "组织已激活", "id": org_id, "is_active": True}, message="组织已激活")


@router.post("/{org_id}/deactivate", summary="停用组织")
async def deactivate_organization(
    org_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """停用指定组织（将 is_active 设为 False）"""
    if getattr(current_user, "role", None) not in (
        "admin",
        "super_admin",
    ) and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    org.is_active = False
    safe_commit(db)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    return success_response(data={"message": "组织已停用", "id": org_id, "is_active": False}, message="组织已停用")
