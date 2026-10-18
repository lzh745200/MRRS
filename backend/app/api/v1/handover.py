"""工作移交 API（w17-004：人员轮换时把「我负责/我发起」的工作一键交给接任人）。

端点：

- ``GET  /handover/inventory``  —— 预览可移交清单（空清单返回 200 空分组）；
- ``GET  /handover/candidates`` —— 可选接任人（同组织启用用户；超管全量）；
- ``POST /handover/execute``    —— 执行移交（单事务；跨组织 fail-closed 403；
  双方站内消息；写 write_work_log 审计）；
- ``GET  /handover/history``    —— 我的移交历史（由 WorkLog 审计行承载）。

业务规则全部收敛在 :mod:`app.services.handover_service`，本模块只做协议转换。
"""

from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.services.handover_service import (
    build_inventory,
    execute_handover,
    list_candidates,
    query_history,
)

router = APIRouter(prefix="/handover", tags=["工作移交"])


class HandoverExecuteRequest(BaseModel):
    """执行移交请求。

    - ``scope``：勾选的资产类型（village/project/todo/approval）；缺省=全部类型；
    - ``item_ids``：逐项勾选，``{类型: [ID...]}``；某类型未出现=整类移交，
      出现且为空数组=该类型不移交；
    - ``note``：移交备注（写入审计与交接单）。
    """

    to_user_id: int = Field(..., ge=1, description="接任人用户ID")
    scope: Optional[List[str]] = Field(
        default=None, description="移交资产类型；缺省=全部（village/project/todo/approval）"
    )
    item_ids: Optional[Dict[str, List[int]]] = Field(
        default=None, description="逐项勾选：{资产类型: [ID...]}"
    )
    note: Optional[str] = Field(default=None, max_length=500, description="移交备注")


@router.get("/inventory")
async def get_handover_inventory(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """可移交资产清单预览（我负责/我发起；按数据域过滤）。"""
    return success_response(data=build_inventory(db, current_user), message="成功")


@router.get("/candidates")
async def get_handover_candidates(
    keyword: Optional[str] = Query(None, description="用户名/姓名模糊搜索"),
    limit: int = Query(200, ge=1, le=500, description="最多返回条数"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """可选接任人列表（同组织启用用户；超管可选全部组织）。"""
    candidates = list_candidates(db, current_user, keyword=keyword, limit=limit)
    return ok_list(
        items=candidates,
        total=len(candidates),
        page=1,
        page_size=max(1, len(candidates)),
    )


@router.post("/execute")
async def execute_handover_endpoint(
    payload: HandoverExecuteRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行工作移交。

    - 单事务：任一环节失败 → 全量回滚（归属/消息/审计均不落库）；
    - 跨组织接任人 → 403（数据域 fail-closed，超管豁免）；
    - 成功 → 双方站内消息 + ``work_logs`` 审计留痕（category=handover）。
    """
    result = execute_handover(
        db,
        current_user,
        to_user_id=payload.to_user_id,
        scope=payload.scope,
        item_ids=payload.item_ids,
        note=payload.note,
    )
    return success_response(data=result, message="工作移交完成")


@router.get("/history")
async def get_handover_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: Optional[date] = Query(None, description="移交日期起（含）"),
    date_to: Optional[date] = Query(None, description="移交日期止（含）"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的移交历史（WorkLog 审计行，按时间倒序）。"""
    items, total = query_history(
        db,
        current_user,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
    )
    return ok_list(items=items, total=total, page=page, page_size=page_size)
