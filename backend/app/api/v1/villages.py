"""
村庄 API 路由

提供自然村的 CRUD 操作。
已优化 N+1 查询：使用 selectinload 分离查询加载关联数据（避免多 joinedload 笛卡尔积）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import get_current_user

router = APIRouter(prefix="/villages", tags=["村庄管理"])


@router.get("")
async def list_villages(
    skip: int = 0,
    limit: int = 50,
    keyword: str = QueryParam(None, description="搜索关键词"),
    ethnic_group: str = QueryParam(None, description="民族属性筛选"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取村庄列表（已优化 N+1 查询）"""
    from app.models.village import Village

    query = db.query(Village).options(
        selectinload(Village.villagers),
        selectinload(Village.industries),
        selectinload(Village.tea_plantations),
        selectinload(Village.cactus_fruit_plots),
    )

    # 关键词搜索
    if keyword:
        query = query.filter(
            Village.name.ilike(f"%{keyword}%")
            | Village.code.ilike(f"%{keyword}%")
            | Village.county.ilike(f"%{keyword}%")
        )

    # 民族属性筛选
    if ethnic_group:
        query = query.filter(Village.ethnic_group == ethnic_group)

    # 数据权限过滤
    from app.services.data_scope_query import scoped_filter  # B1 下沉：服务层统一入口
    query = scoped_filter(query, Village, current_user, )

    # 先取 total 再分页（避免分页后 total 不准）
    total = query.count()
    villages = query.offset(skip).limit(limit).all()

    items = [
        {
            "id": v.id,
            "name": v.name,
            "code": v.code,
            "province": v.province,
            "city": v.city,
            "county": v.county,
            "township": v.township,
            "ethnic_group": getattr(v, "ethnic_group", ""),
            "is_ethnic_village": getattr(v, "is_ethnic_village", False),
            "karst_ratio": getattr(v, "karst_ratio", 0.0),
            "terrain_type": v.terrain_type or "",
            "region_code": v.region_code or "",
            "latitude": v.latitude,
            "longitude": v.longitude,
            "villager_count": len(v.villagers) if v.villagers else 0,
            "industry_count": len(v.industries) if v.industries else 0,
            "tea_plantation_count": len(v.tea_plantations)
            if v.tea_plantations
            else 0,
            "cactus_fruit_count": len(v.cactus_fruit_plots)
            if v.cactus_fruit_plots
            else 0,
        }
        for v in villages
    ]

    # envelope 格式：{code:200, data:{items,total,...}, message:"成功"}
    page = (skip // limit) + 1 if limit > 0 else 1
    return ok_list(items, total, page=page, page_size=limit)


@router.get("/{village_id}")
async def get_village(
    village_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取单个村庄详情（已优化 N+1 查询）"""
    from app.models.village import Village

    village = (
        db.query(Village)
        .options(
            selectinload(Village.villagers),
            selectinload(Village.industries),
            selectinload(Village.tea_plantations),
            selectinload(Village.cactus_fruit_plots),
        )
        .filter(Village.id == village_id)
        .first()
    )
    if not village:
        raise HTTPException(status_code=404, detail="村庄不存在")

    # 数据权限校验：非本组织/非本人创建且非管理员 → 403（区分"不存在"与"越权"）
    from app.core.data_permission import check_record_access
    if current_user is not None and not check_record_access(
        village, current_user, owner_field="created_by", dept_field="organization_id"
    ):
        raise HTTPException(status_code=403, detail="无权访问该村庄")

    from app.utils.common import StringHelper
    return {
        "id": village.id,
        "name": village.name,
        "code": village.code,
        "province": village.province,
        "city": village.city,
        "county": village.county,
        "township": village.township,
        "description": village.description,
        "ethnic_group": getattr(village, "ethnic_group", ""),
        "is_ethnic_village": getattr(village, "is_ethnic_village", False),
        "karst_ratio": getattr(village, "karst_ratio", 0.0),
        "terrain_type": village.terrain_type or "",
        "region_code": village.region_code or "",
        "latitude": village.latitude,
        "longitude": village.longitude,
        "villagers": [
            {
                "id": vl.id,
                "name": vl.name,
                "phone": StringHelper.mask_sensitive(vl.phone),
                "is_poverty": vl.is_poverty,
            }
            for vl in (village.villagers or [])
        ],
        "industries": [
            {"id": ind.id, "name": ind.name, "industry_type": ind.industry_type}
            for ind in (village.industries or [])
        ],
    }
