"""业务数据体检 API（W17-008）。

GET /api/v1/system/business-health —— 仅管理员。

为什么单独成端点而不是塞进 /system/diagnostics：
- diagnostics 是基础设施/运行态排障包（版本、日志、资源），会整体外带；
- 本端点只出业务数据质量计数与前端入口，不含日志、不含 PII，供管理员日常巡检。

响应结构：{generated_at, year, stale_days, status, summary, checks[]}；
每项 check 带 count（全量计数）、entry（前端处理入口）、items（截断明细）、
items_truncated。扫描全部走 ORM（实现见 services/business_health_service.py）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.business_health_service import (
    DEFAULT_ITEM_LIMIT,
    DEFAULT_STALE_DAYS,
    MAX_ITEM_LIMIT,
    BusinessHealthService,
)

router = APIRouter(prefix="/business-health", tags=["业务数据体检"])


@router.get("", summary="业务数据体检（仅管理员）")
def business_health(
    year: Optional[int] = Query(default=None, ge=2000, le=2100, description="体检年度，默认当前年"),
    stale_days: int = Query(default=DEFAULT_STALE_DAYS, ge=1, le=3650, description="长期未动阈值（天）"),
    item_limit: int = Query(default=DEFAULT_ITEM_LIMIT, ge=1, le=MAX_ITEM_LIMIT, description="每项明细返回上限"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """业务数据体检报告：村年度缺失 / 金额矛盾 / 长期未动 / 组织归属缺失。"""
    require_admin(current_user)
    service = BusinessHealthService(
        db,
        year=year,
        stale_days=stale_days,
        item_limit=item_limit,
    )
    return success_response(data=service.collect())
