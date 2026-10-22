"""
组织管理API
支持部门单位和帮扶单位的层级管理
与权限管理集成：组织创建、修改需要管理员权限
"""

# security-audit: exempt data_scope — 组织域自身成员管理（按 organization_id 列成员），加数据权限会破坏组织成员维护

import io
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
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
from ...services.organization_code_service import (
    ADMIN_AREA_CODE_SUFFIX_HINTS,
    LEVEL_LABELS,
    OrganizationCodeService,
)
from ...services.organization_service import OrganizationService
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log
from app.core.response import success_response

router = APIRouter(prefix="/organizations", tags=["组织管理"])


def _coerce_org_enums(org_data: dict) -> None:
    """把 org_type / level 从字符串转成枚举，非法值返回 422 而不是 500。

    R24：`OrganizationLevel("1")` 这类非法值此前会抛 ValueError 冒泡成
    「服务器内部错误」（安装包验收实测 POST /organizations + level="1" → 500）。
    前端下拉只会给合法值，但接口是公开契约，非法输入属用户可纠正的错误。
    """
    if org_data.get("org_type"):
        try:
            org_data["org_type"] = OrganizationType(org_data["org_type"])
        except ValueError:
            allowed = ", ".join(t.value for t in OrganizationType)
            raise HTTPException(
                status_code=422, detail=f"无效的组织类型: {org_data['org_type']}（允许值：{allowed}）"
            ) from None
    if org_data.get("level"):
        try:
            org_data["level"] = OrganizationLevel(org_data["level"])
        except ValueError:
            allowed = ", ".join(level.value for level in OrganizationLevel)
            raise HTTPException(
                status_code=422, detail=f"无效的组织层级: {org_data['level']}（允许值：{allowed}）"
            ) from None


def _assert_org_write_scope(
    db: Session,
    current_user,
    org_ids: List[int],
    *,
    action: str,
) -> None:
    """R27（2026-10-14）：组织写端点跨组织越权守卫。

    写端点此前只有内联角色判定（admin/super_admin），不校验目标组织是否在
    调用者组织子树内 —— 部门级管理员（role=admin, organization_id=2）可以对
    其它分支的组织改名/软删/移动/排序。这里统一接入
    core.data_permission.assert_org_reachable（与 org_module_policy /
    control_package 写端点同口径）：超管直接放行；非超管要求目标组织在自身
    组织子树内，否则 403（"无权对该组织{action}"）。

    独立成函数：本模块多个端点的 C901 复杂度已贴近上限（16），新判定不得
    内联进现有大函数。
    """
    from app.core.data_permission import assert_org_reachable

    for org_id in org_ids:
        assert_org_reachable(db, current_user, org_id, action=action)


def _invalidate_dashboard_cache_safe() -> None:
    """组织写操作后失效工作台统计缓存，保证删除/新增/停用后总数立即更新。"""
    try:
        from app.api.v1.data.data.dashboard import invalidate_dashboard_cache
        invalidate_dashboard_cache()
    except Exception:  # pragma: no cover - 纯加速层：缓存读写失败不影响业务正确性
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


class OrganizationEnvelopeResponse(BaseModel):
    """单对象端点的标准信封响应（R7-F1，真实 HTTP 探测 2026-09-13）。

    create/update/get/my-organization 此前以裸 OrganizationResponse 返回，前端
    store 的 `res.code === 200 && res.data` 断言永不命中（org 业务编号 code 字段
    恰好占用顶层）：新建/更新组织后本地列表不插入、缓存树不失效；fetchOrganization
    / fetchMyOrganization 的 current.value 永不赋值。对齐 auth.LoginResponse 的
    信封模式；axios 拦截器会把 data.data 展开到顶层，Edit.vue 的顶层字段读取不受影响。
    """

    code: int = 200
    data: Optional[OrganizationResponse] = None
    message: str = ""


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
    # 无过滤条件的默认列表请求使用缓存（5分钟）。
    # 2026-10-14 数据范围收敛后，缓存只对"可见全量"的管理员启用 ——
    # 否则普通用户的受限结果会被写入全局缓存，造成跨用户数据泄漏。
    from app.core.data_permission import apply_scope_filter
    from app.core.permission_utils import is_superuser

    # R27-H8 收口后：部门级 admin 的列表结果已被数据域收敛为「本组织及子树」，
    # 若仍写入全局键 "orgs:list"，组织 A 的管理员会把受限结果喂给组织 B 的管理员
    # （跨组织泄漏）。因此缓存只对**真正全局**的用户启用（超管 / is_superuser）。
    _global_view = is_superuser(current_user) or getattr(current_user, "data_scope", None) == "all"
    _cache_key = "orgs:list"
    if (
        _global_view
        and not any([org_type, parent_id, is_active, keyword, search])
        and page == 1
        and page_size == 20
    ):
        cached = await cache_manager.get(_cache_key)
        if cached is not None:
            return cached
    try:
        query = apply_scope_filter(
            db.query(Organization), current_user, Organization, org_id_field="id", db=db
        )

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
        # 仅对「可见全量」的管理员的默认无过滤请求写缓存。
        # R29 探测实测：读已按 _global_view 门禁，写却漏了同一门禁 —— 普通用户
        # 默认请求会把其受限结果（OWN 范围=空列表）写进全局键 "orgs:list"，
        # 随后超管 5 分钟内的组织列表被污染成空/子集（跨用户缓存污染）。
        if (
            _global_view
            and not any([org_type, parent_id, is_active, keyword, search])
            and page == 1
            and page_size == 20
        ):
            await cache_manager.set(_cache_key, result, ttl=300)
        return result
    except Exception as e:  # pragma: no cover - 纯加速层：缓存读写失败不影响业务正确性
        logger.error(f"获取组织列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取组织列表失败，请稍后重试或联系管理员")


def _set_no_cache_headers(response: Response):
    """设置无缓存响应头"""
    if response:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"


def _org_level_to_number(org: Organization) -> int:
    """将组织 level 转为数字（兼容两种历史形态）。

    `level` 列历史上被两处写入不同口径：① 建组织时写**深度数字**（`1`/`2`…）；
    ② 早期允许显式传枚举 `level_N`。此前这里只认 `level_N`，于是第 ① 类组织
    一律被换算成 0（界面显示"未设置"）。现两种形态都正确解析；无法识别才回 0。
    """
    if not org.level:
        return 0
    level_str = str(org.level).strip()
    if level_str.isdigit():
        return int(level_str)
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
        # 2026-10-14 数据范围收敛：普通用户只见本组织及子树；管理员/超管全量。
        # （/organizations/tree 被用户管理、通行码等页面复用为组织下拉。）
        from app.core.data_permission import apply_scope_filter

        query = apply_scope_filter(query, current_user, Organization, org_id_field="id", db=db)

        if org_type:
            query = query.filter(Organization.org_type == org_type)

        organizations = query.order_by(Organization.sort_order, Organization.id).all()
        org_dict = {org.id: org for org in organizations}

        org_map = {}
        for org in organizations:
            org_map[org.id] = _org_to_tree_node(org, org_dict)

        tree = _build_org_tree(organizations, org_map)
        return success_response(data=tree)
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
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
        # 2026-10-14 数据范围收敛：统计口径跟随当前用户可见的组织集合
        # （此前任何登录用户都能看到全库组织统计）。管理员=全量；普通用户=本组织及子树。
        from app.core.data_permission import apply_scope_filter

        scoped_org_ids = [
            row if isinstance(row, int) else row[0]
            for row in apply_scope_filter(
                db.query(Organization.id), current_user, Organization, org_id_field="id", db=db
            ).all()
        ]
        org_scope = Organization.id.in_(scoped_org_ids)
        user_scope = User.organization_id.in_(scoped_org_ids)

        total = db.query(func.count(Organization.id)).filter(org_scope).scalar() or 0
        active = db.query(func.count(Organization.id)).filter(
            org_scope, Organization.is_active == True  # noqa: E712
        ).scalar() or 0
        inactive = total - active

        # 按类型统计
        type_rows = (
            db.query(Organization.org_type, func.count(Organization.id))
            .filter(org_scope, Organization.is_active == True)  # noqa: E712
            .group_by(Organization.org_type)
            .all()
        )
        type_dist = {str(t or "unknown"): c for t, c in type_rows}

        # 按层级统计
        level_rows = (
            db.query(Organization.level, func.count(Organization.id))
            .filter(org_scope, Organization.is_active == True)  # noqa: E712
            .group_by(Organization.level)
            .all()
        )
        level_dist = {str(lv or "unknown"): c for lv, c in level_rows}

        # 绑定了用户的组织数
        orgs_with_members = (
            db.query(func.count(func.distinct(User.organization_id)))
            .filter(user_scope, User.organization_id.isnot(None), User.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        # 总用户数
        total_members = (
            db.query(func.count(User.id))
            .filter(user_scope, User.is_active == True, User.organization_id.isnot(None))  # noqa: E712
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
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
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
        from app.core.data_permission import apply_scope_filter
        from app.services.export_service import ExcelExportService

        # 2026-10-14 数据范围收敛（军审红线 S2）：部门级 admin 只能导出本组织及子树，
        # super_admin/超管全量 —— 与列表/树/统计口径一致。
        query = apply_scope_filter(
            db.query(Organization), current_user, Organization, org_id_field="id", db=db
        )
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
        _wm = (
            f"导出人：{getattr(current_user, 'full_name', None) or getattr(current_user, 'username', '')}"
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        excel_bytes = export_service.export_organizations(
            organizations=export_data,
            filename="组织机构列表",
            watermark=_wm,
        )

        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=organizations.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
        logger.error(f"导出组织列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="导出失败")


@router.get("/my-organization", response_model=OrganizationEnvelopeResponse)
async def get_my_organization(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户所属组织。

    无组织归属（或所属组织已停用 / 不存在）时返回 404 —— **不回退到其它组织**。
    历史实现会返回“第一个活跃组织”，在多组织部署下等于把他人组织当作本人的，
    既误导用户，又会让后续接口以错误归属提交数据；2026-09-14 修正为
    与数据范围 fail-closed 一致的口径（无组织即无组织上下文）。
    """
    try:
        org_id = getattr(current_user, "organization_id", None)
        if not org_id:
            raise HTTPException(status_code=404, detail="当前用户未关联任何组织")

        org = (
            db.query(Organization)
            .filter(
                Organization.id == org_id,
                Organization.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not org:
            raise HTTPException(status_code=404, detail="当前用户所属组织不存在或已停用")

        return success_response(data=org, message="success")
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
        logger.error(f"获取当前用户组织失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取当前用户组织失败，请稍后重试或联系管理员")


@router.get("/my", response_model=OrganizationEnvelopeResponse)
async def get_my_organization_alias(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户所属组织（/my 别名，兼容前端调用）"""
    return await get_my_organization(current_user, db)


@router.get("/subordinates", response_model=List[OrganizationResponse])
async def get_subordinates(
    include_self: bool = Query(False, description="是否包含自身"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取下级组织列表（限调用者可及的组织子树）"""
    try:
        from app.core.data_permission import _get_org_subtree
        from app.core.permission_utils import is_superuser

        query = db.query(Organization).filter(Organization.is_active == True)  # noqa: E712
        # 数据范围收敛：历史实现对所有登录用户返回整张组织表（跨单位组织架构外泄）
        if not is_superuser(current_user):
            org_id = getattr(current_user, "organization_id", None)
            if not org_id:
                raise HTTPException(status_code=403, detail="账号未归属组织，无法查看下级组织")
            allowed_ids, _names = _get_org_subtree(db, org_id)
            query = query.filter(Organization.id.in_(allowed_ids or [org_id]))
        if not include_self:
            query = query.filter(Organization.parent_id.isnot(None))
        return query.order_by(Organization.sort_order, Organization.id).all()
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
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
        # 只有省 / 市州 / 县市三级；code_suffix 用于前端提示 6 位编码的末位规律
        "levels": [
            {"value": level, "label": LEVEL_LABELS[level],
             "code_suffix": ADMIN_AREA_CODE_SUFFIX_HINTS[level]}
            for level in ("level_1", "level_2", "level_3")
        ],
    })


@router.get("/{org_id}", response_model=OrganizationEnvelopeResponse)
async def get_organization(org_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取组织详情"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    # 2026-10-14 数据范围收敛：越权访问返回 403（区别于 404"不存在"，
    # 与本仓库跨组织访问的既有语义一致）。
    from app.core.data_permission import apply_scope_filter

    visible = (
        apply_scope_filter(
            db.query(Organization.id), current_user, Organization, org_id_field="id", db=db
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if visible is None:
        raise HTTPException(status_code=403, detail="无权查看该组织")
    return success_response(data=org, message="success")


@router.post("", response_model=OrganizationEnvelopeResponse)
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

    # 编码即行政区划代码（省 2 位 / 市州 4 位 / 县市 6 位），是跨机匹配的唯一依据，必填
    try:
        org_code = OrganizationCodeService.normalize_admin_code(data.code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    existing = db.query(Organization).filter(Organization.code == org_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="组织编码已存在")

    # 转换枚举类型
    org_data = data.model_dump(exclude_defaults=False)
    _coerce_org_enums(org_data)

    # 确保 is_active 有值
    if "is_active" not in org_data:
        org_data["is_active"] = True

    # 组织树元数据（R14 真实 HTTP 探测 2026-09-13 修复）：此前直接
    # Organization(**org_data) 落库，path/level 均为 NULL —— 而组织级数据权限
    # （OrganizationPermissionService.can_access_organization → get_subordinate_ids
    # → path LIKE 前缀匹配）**完全依赖 path**：新建组织的成员因此恒被判为
    # "无组织权限"，数据包导出等组织门禁端点一律 403（安装包首启即复现）。
    parent = None
    if org_data.get("parent_id"):
        parent = db.query(Organization).filter(Organization.id == org_data["parent_id"]).first()
        if not parent:
            raise HTTPException(status_code=400, detail="上级组织不存在")
        # R27（2026-10-14）：跨组织越权守卫 —— 部门级管理员只能在自身组织
        # 子树内创建组织（OrganizationCreate 无 organization_id 字段，树归属
        # 完全由 parent_id 决定，校验父级即可）。
        _assert_org_write_scope(db, current_user, [org_data["parent_id"]], action="创建组织")

    # 层级由行政区划代码长度推导（省=2 位 / 市州=4 位 / 县市=6 位），不允许与编码矛盾
    inferred_level = OrganizationCodeService.infer_level(org_code)
    declared_level = org_data.get("level")
    if declared_level and OrganizationCodeService.level_order(declared_level) != (
        OrganizationCodeService.level_order(inferred_level)
    ):
        raise HTTPException(
            status_code=422,
            detail="组织层级与行政区划代码不一致：省级 XX0000 / 市州级 XXYY00 / 县市级 XXYYZZ",
        )
    org_data["level"] = inferred_level
    # 跨级校验：子级必须恰为父级 +1（根组织只能建省级）
    child_order = OrganizationCodeService.level_order(inferred_level) or 0
    parent_order = (
        OrganizationCodeService.level_order(parent.level) if parent is not None else 0
    )
    if child_order != parent_order + 1:
        raise HTTPException(
            status_code=422,
            detail="层级必须逐级挂接：省级 → 市州级 → 县市级（当前上级层级不匹配）",
        )

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

    org_data["code"] = org_code
    org = Organization(**org_data)
    db.add(org)
    db.flush()  # 先获取自增 id，供自动生成编码使用
    # path 与 OrganizationService.create_organization 同口径：
    # 根组织 /{id}/，子组织 {父 path}{id}/（前缀匹配是组织树查询的唯一依据）。
    # 2026-10-14：父级 path 为空（历史数据）时**不能**让子级退化成根路径 ——
    # 那会让父子在权限视图里彻底割裂（子级被当成根，子树成员权限判错）。
    # 此处用父级 id 兜底拼出父前缀，父级自身的回填仍由启动自检统一收敛。
    if parent is not None:
        parent_prefix = parent.path or f"/{parent.id}/"
        org.path = f"{parent_prefix}{org.id}/"
    else:
        org.path = f"/{org.id}/"

    safe_commit(db)
    db.refresh(org)
    try:
        write_work_log(db, "organization", "create", org.id, f"创建组织: {org.name}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover - 纯防御兜底：工作日志写入失败按约定不阻断主流程
        logger.debug("记录工作日志失败", exc_info=True)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    # R7-F1：改用信封返回——此前裸形态使前端 store 的
    # `res.code === 200 && res.data` 断言永不命中，新建组织后本地列表不插入、
    # 缓存树不失效（用户看不到新组织）。response_model 已同步切换为
    # OrganizationEnvelopeResponse（对齐 auth.LoginResponse 模式）。
    return success_response(data=org, message="创建成功")


@router.put("/{org_id}", response_model=OrganizationEnvelopeResponse)
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

    # R27（2026-10-14）：跨组织越权守卫 —— 目标组织必须在调用者子树内
    _assert_org_write_scope(db, current_user, [org_id], action="修改组织")

    # 编码锁定：行政区划代码是跨机匹配的唯一依据，创建后不允许修改（需变更请停用后新建）
    if data.code is not None and data.code != org.code:
        raise HTTPException(
            status_code=422,
            detail="组织编码已锁定，不允许修改；如需变更请停用该组织后新建",
        )

    update_data = data.model_dump(exclude_unset=True)

    # 安全检查：禁止将 parent_id 设为自身或其子孙（防止循环引用）。
    # 走 OrganizationService.would_create_cycle —— 它沿父链逐级上溯判定，
    # 不依赖 path（组织被移动后 path 可能尚未刷新，用 path 判定不可靠）。
    if "parent_id" in update_data:
        new_parent_id = update_data["parent_id"]
        if new_parent_id is not None and OrganizationService(db).would_create_cycle(
            org_id, new_parent_id
        ):
            raise HTTPException(status_code=400, detail="不能将组织设为自身或其子孙的上级组织")

    # 转换枚举类型
    _coerce_org_enums(update_data)

    for key, value in update_data.items():
        setattr(org, key, value)

    # 改父级后必须级联重算自身与全部子孙的 path/level：
    # 组织级数据权限依赖 path 前缀匹配，不刷新会让「树视图」与「权限视图」背离。
    if "parent_id" in update_data:
        OrganizationService(db).recompute_subtree_paths(org)

    safe_commit(db)
    db.refresh(org)
    try:
        write_work_log(db, "organization", "update", org.id, f"更新组织: {org.name}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:  # pragma: no cover - 纯防御兜底：工作日志写入失败按约定不阻断主流程
        logger.debug("记录工作日志失败", exc_info=True)
    await cache_manager.delete("orgs:list")
    _invalidate_dashboard_cache_safe()
    # R7-F1：信封返回（同 create_organization），使 store 的更新断言生效
    return success_response(data=org, message="更新成功")


@router.delete("/{org_id}")
async def delete_organization(
    org_id: int,
    force: bool = Query(False, description="保留参数，暂未使用"),
    confirm_password: str = Header(
        "",
        alias="X-Confirm-Password",
        description="二次确认：输入当前用户密码（请求头传递，避免落入 access log）",
    ),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除组织（逻辑删除：将 is_active 设为 False）

    Args:
        org_id: 组织ID
        force: 保留参数，暂未使用
        confirm_password: 二次确认密码（**请求头** `X-Confirm-Password`）。
            2026-10-14 由 URL 查询串改为请求头：查询串会原样进 uvicorn access log，
            明文密码随之落盘；请求头不参与访问日志的请求行。

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

    # R27（2026-10-14）：跨组织越权守卫 —— 目标组织必须在调用者子树内，
    # 部门级管理员不得软删其它分支的组织节点
    _assert_org_write_scope(db, current_user, [org_id], action="删除组织")

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
    except Exception:  # pragma: no cover - 纯防御兜底：工作日志写入失败按约定不阻断主流程
        logger.debug("记录工作日志失败", exc_info=True)
    logger.info(f"删除成功: org_id={org_id}")
    # 批次 3（危险操作强制审计）：删除组织属高影响操作，必须留审计痕迹
    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action="organization_delete",
        user_id=current_user.id,
        username=getattr(current_user, "username", ""),
        resource_type="organization",
        resource_id=org_id,
        details={"name": org.name, "type": "soft_delete"},
    )
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

    # R27（2026-10-14）：跨组织越权守卫 —— 被移动的组织必须在调用者子树内
    _assert_org_write_scope(db, current_user, [org_id], action="移动组织")

    new_parent_id = body.new_parent_id

    # 检查新父级是否存在
    if new_parent_id:
        new_parent = db.query(Organization).filter(Organization.id == new_parent_id).first()
        if not new_parent:
            raise HTTPException(status_code=404, detail="目标父组织不存在")

        # R27：新父级也必须在调用者子树内（把子组织挂到别的分支下同样越权）
        _assert_org_write_scope(db, current_user, [new_parent_id], action="移动组织")

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
    # 移动后必须级联重算自身与全部子孙的 path/level（同 PUT 改父级），
    # 否则组织级数据权限按旧 path 前缀匹配 → 子树成员被误判无权限/看错数据。
    OrganizationService(db).recompute_subtree_paths(org)
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

    # R27（2026-10-14）：跨组织越权守卫 —— 所有目标组织都必须在调用者子树内，
    # 且在任何变更发生前统一校验（不落部分更新）
    _assert_org_write_scope(
        db, current_user, [item.id for item in request.items], action="排序组织"
    )

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
    except Exception:  # pragma: no cover - 防御性回滚：仅在未预期 DB 异常路径触发，正常路径不可达
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
    # 2026-10-14 数据范围收敛：成员名单属于组织敏感数据，越权 403（同详情端点语义）
    from app.core.data_permission import apply_scope_filter

    visible = (
        apply_scope_filter(
            db.query(Organization.id), current_user, Organization, org_id_field="id", db=db
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if visible is None:
        raise HTTPException(status_code=403, detail="无权查看该组织的成员")

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
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
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
    except Exception as e:  # pragma: no cover - 未知异常兜底：仅记录日志、不改变响应语义，正常路径不可达
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
