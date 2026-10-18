"""消费帮扶台账 API（W22 v1.14.0，替换原舆情监测模块）。

契约（`.scratch/w22-feature-batch/000-contract.md` §2）：
- ``GET /consumption`` 列表（ok_list，含 village_name）；
- ``GET /consumption/statistics`` 年度/品类/村统计；
- ``POST/PUT/DELETE /consumption`` 台账 CRUD（软删 is_active=false）；
- ``GET /consumption/export?format=xlsx|csv`` 台账导出（StreamingResponse）。

数据域统一 ``get_org_scope`` / ``filter_by_org_ids``；写操作走 ``safe_commit``，
审计留痕复用 ``write_work_log``。凭证文件由通用 ``/files/upload`` 落盘后回填
``voucher_url``，本模块不重复实现上传。
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import enforce_admin_include_deleted
from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.models.consumption import ConsumptionRecord
from app.schemas.consumption import (
    ConsumptionRecordCreate,
    ConsumptionRecordUpdate,
)
from app.services.consumption_service import (
    apply_consumption_filters,
    attach_village_names,
    build_export_table,
    consumption_base_query,
    consumption_statistics,
    ensure_village_accessible,
    get_consumption_or_404,
)
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consumption", tags=["消费帮扶台账"])


def _write_log(
    db: Session, action: str, entity_id: int, title: str, current_user, detail: str = ""
) -> None:
    write_work_log(
        db,
        "consumption",
        action,
        entity_id,
        title,
        user_id=current_user.id,
        username=getattr(current_user, "username", "系统"),
        detail=detail,
    )


# ==================== 查询 ====================


@router.get("")
async def list_consumption(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    year: Optional[int] = Query(None, description="年度筛选"),
    category: Optional[str] = Query(None, description="品类筛选"),
    village_id: Optional[int] = Query(None, description="帮扶村ID筛选"),
    keyword: Optional[str] = Query(None, description="产品/采购方/供货方关键字"),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """消费帮扶台账列表（envelope；非管理员 include_deleted 静默降级）。"""
    query = apply_consumption_filters(
        consumption_base_query(db, data_scope, include_deleted=include_deleted),
        year=year,
        category=category,
        village_id=village_id,
        keyword=keyword,
    )
    total = query.count()
    records = (
        query.order_by(ConsumptionRecord.created_at.desc(), ConsumptionRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    rows = attach_village_names(db, [record.to_dict() for record in records])
    return ok_list(items=rows, total=total, page=page, page_size=page_size)


@router.get("/statistics")
async def get_consumption_statistics(
    year: Optional[int] = Query(None, description="年度筛选（空=全部年度）"),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """消费帮扶统计（总额/笔数/品类分布/村分布，口径跟随数据域）。"""
    return success_response(
        data=consumption_statistics(
            db, data_scope, year=year, include_deleted=include_deleted
        ),
        message="成功",
    )


@router.get("/export")
async def export_consumption(
    format: str = Query("xlsx", description="导出格式: xlsx 或 csv"),
    year: Optional[int] = Query(None, description="年度筛选"),
    category: Optional[str] = Query(None, description="品类筛选"),
    village_id: Optional[int] = Query(None, description="帮扶村ID筛选"),
    keyword: Optional[str] = Query(None, description="关键字筛选"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """导出消费帮扶台账（当前筛选集，xlsx / csv）。"""
    if format not in ("xlsx", "csv"):
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")

    query = apply_consumption_filters(
        consumption_base_query(db, data_scope, include_deleted=False),
        year=year,
        category=category,
        village_id=village_id,
        keyword=keyword,
    )
    records = query.order_by(
        ConsumptionRecord.year.desc(), ConsumptionRecord.id.desc()
    ).all()
    rows = attach_village_names(db, [record.to_dict() for record in records])
    headers, data_rows = build_export_table(rows)

    suffix = str(year) if year else "all"
    filename = f"消费帮扶台账_{suffix}.{format}"
    content = _build_export_bytes(format, headers, data_rows)
    media_type = (
        "text/csv; charset=utf-8"
        if format == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _build_export_bytes(
    export_format: str, headers: list, data_rows: list
) -> bytes:
    """生成导出文件字节（xlsx 用 openpyxl / csv 用标准库，csv 带 BOM 兼容 Excel）。"""
    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(data_rows)
        return ("\ufeff" + buffer.getvalue()).encode("utf-8")

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "消费帮扶台账"
    sheet.append(headers)
    for row in data_rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


# ==================== 写操作 ====================


@router.post("")
async def create_consumption(
    data: ConsumptionRecordCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建消费帮扶台账记录。"""
    ensure_village_accessible(db, data.supported_village_id, current_user)

    payload = data.model_dump()
    payload["organization_id"] = getattr(current_user, "organization_id", None)
    payload["created_by"] = current_user.id
    record = ConsumptionRecord(**payload)
    db.add(record)
    safe_commit(db)
    db.refresh(record)

    _write_log(
        db, "create", record.id, record.item_name, current_user,
        detail=f"金额={record.amount} 年度={record.year}",
    )
    row = attach_village_names(db, [record.to_dict()])[0]
    return success_response(data=row, message="创建成功")


@router.put("/{record_id}")
async def update_consumption(
    record_id: int,
    data: ConsumptionRecordUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新消费帮扶台账记录（部分更新）。"""
    record = get_consumption_or_404(
        db, record_id, current_user, "无权编辑该消费帮扶记录"
    )
    update_data = data.model_dump(exclude_unset=True)
    if "supported_village_id" in update_data:
        ensure_village_accessible(db, update_data["supported_village_id"], current_user)

    for key, value in update_data.items():
        setattr(record, key, value)
    safe_commit(db)
    db.refresh(record)

    _write_log(db, "update", record.id, record.item_name, current_user)
    row = attach_village_names(db, [record.to_dict()])[0]
    return success_response(data=row, message="更新成功")


@router.delete("/{record_id}")
async def delete_consumption(
    record_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除消费帮扶台账记录（软删除 is_active=false）。"""
    record = get_consumption_or_404(
        db, record_id, current_user, "无权删除该消费帮扶记录"
    )
    record.is_active = False
    record.deleted_at = datetime.now(timezone.utc)
    safe_commit(db)

    _write_log(db, "delete", record.id, record.item_name, current_user)
    return success_response(data={"id": record.id}, message="删除成功")
