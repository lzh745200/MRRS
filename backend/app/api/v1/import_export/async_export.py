"""
异步导出API端点

Task 3.3: 实现导出状态查询和下载API
- GET /api / v1 / async - export / status/{task_id} - 查询导出状态
- GET /api / v1 / async - export / download/{task_id} - 下载导出文件
- POST /api / v1 / async - export / villages - 导出帮扶村数据

Requirements: 2.1, 2.2, 2.3
"""

from datetime import datetime
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import is_superuser
from app.core.security import get_current_user
from app.models.export_task import ExportStatus
from app.models.user import User
from app.services.async_export_service import AsyncExportService

router = APIRouter(prefix="/async-export", tags=["异步导出"])


# ==================== Response Schemas ====================


class ExportTaskResponse(BaseModel):
    """导出任务响应"""

    id: int
    task_id: str
    export_type: str
    status: str
    record_count: int = 0
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_downloadable: bool = False

    model_config = ConfigDict(from_attributes=True)


class ExportTaskListResponse(BaseModel):
    """导出任务列表响应"""

    items: List[ExportTaskResponse]
    total: int
    page: int
    page_size: int


class ExportRequestResponse(BaseModel):
    """导出请求响应"""

    mode: str = Field(..., description="导出模式: sync / async")
    task_id: Optional[str] = Field(None, description="异步任务ID")
    file_name: Optional[str] = Field(None, description="同步导出文件名")
    record_count: int = Field(0, description="记录数量")
    message: str = Field(..., description="提示信息")


class ExportFilterParams(BaseModel):
    """导出筛选参数"""

    department: Optional[str] = Field(None, description="部门筛选")
    support_unit: Optional[str] = Field(None, description="帮扶单位筛选")
    village_name: Optional[str] = Field(None, description="村庄名称筛选")
    region_scope: Optional[str] = Field(None, description="地区范围筛选")
    is_three_regions: Optional[bool] = Field(None, description="是否三区三州")
    is_border_area: Optional[bool] = Field(None, description="是否边疆地区")
    is_revitalization_tier: Optional[bool] = Field(None, description="是否振兴梯队")


class ReportExportRequest(BaseModel):
    """报表导出请求"""

    report_type: str = Field(..., description="报表类型")
    format: str = Field("xlsx", description="导出格式")
    scope: str = Field("sel", description="数据范围")
    include_charts: bool = Field(False, description="是否包含图表")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    options: Optional[dict] = Field(None, description="额外选项")


# ==================== API Endpoints ====================


@router.post("/reports")
async def export_reports(
    params: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出报表数据

    根据 report_type 生成相应的报表导出任务。
    """
    import logging

    logger = logging.getLogger(__name__)

    service = AsyncExportService(db)

    try:
        # 构造查询参数
        query_params = {
            "report_type": params.report_type,
            "format": params.format,
            "scope": params.scope,
        }
        if params.start_date:
            query_params["start_date"] = params.start_date
        if params.end_date:
            query_params["end_date"] = params.end_date
        if params.options:
            query_params["options"] = params.options

        # 使用 export_report_sync 按 report_type 分发导出（真实查库）
        content, filename, count = service.export_report_sync(
            report_type=params.report_type,
            query_params=query_params,
            db=db,
            user=current_user,
        )
        # URL 编码文件名,避免 latin-1 编码错误
        encoded_filename = quote(filename)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )
    except Exception as e:
        logger.error(f"报表导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"报表导出失败: {str(e)}")


@router.post("/villages")
async def export_villages(
    filters: Optional[ExportFilterParams] = None,
    force_async: bool = Query(False, description="强制使用异步导出"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出帮扶村数据

    Requirements: 2.1, 2.3, 2.4

    - 数据量 <= 5000: 同步导出，直接返回文件
    - 数据量 > 5000: 异步导出，返回任务ID
    - force_async=true: 强制使用异步导出
    """
    service = AsyncExportService(db)

    # 转换筛选参数
    query_params = filters.dict(exclude_none=True) if filters else {}

    # 判断是否使用异步导出
    should_async = force_async or service.should_use_async("supported_village", query_params)

    if should_async:  # 异步导出
        task = await service.export_supported_villages_async(
            user_id=current_user.id, query_params=query_params
        )

        return ExportRequestResponse(
            mode="async",
            task_id=task.task_id,
            record_count=service.estimate_record_count("supported_village", query_params),
            message="导出任务已创建，请稍后查询导出状态",
        )
    else:
        # 同步导出（真实查库）
        content, filename, count = service.export_supported_villages_sync(
            db, current_user, query_params
        )

        # URL 编码文件名,避免 latin-1 编码错误
        encoded_filename = quote(filename)
        # 直接返回文件
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
        )


@router.get("/status/{task_id}", response_model=ExportTaskResponse)
async def get_export_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    查询导出任务状态

    Requirements: 2.2, 2.3

    - 返回任务的当前状态、进度和文件信息
    """
    service = AsyncExportService(db)
    task = service.get_export_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="导出任务不存在")

    # 验证权限
    if task.user_id != current_user.id and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="无权查看此任务")

    return ExportTaskResponse(
        id=task.id,
        task_id=task.task_id,
        export_type=task.export_type,
        status=task.status,
        record_count=task.record_count or 0,
        file_name=task.file_name,
        file_size=task.file_size,
        error_message=task.error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        expires_at=task.expires_at,
        is_downloadable=task.is_downloadable,
    )


@router.get("/download/{task_id}")
async def download_export_file(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    下载导出文件

    Requirements: 2.2, 2.3

    - 只能下载已完成且未过期的导出文件
    """
    service = AsyncExportService(db)
    task = service.get_export_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="导出任务不存在")

    # 验证权限
    if task.user_id != current_user.id and not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="无权下载此文件")

    # 检查是否可下载
    if not task.is_downloadable:
        if task.status == ExportStatus.PROCESSING.value:
            raise HTTPException(status_code=400, detail="导出任务正在处理中，请稍后再试")
        elif task.status == ExportStatus.FAILED.value:
            raise HTTPException(status_code=400, detail=f"导出任务失败: {task.error_message}")
        elif task.status == ExportStatus.EXPIRED.value:
            raise HTTPException(status_code=400, detail="导出文件已过期")
        else:
            raise HTTPException(status_code=400, detail="导出文件不可下载")

    # 获取文件
    result = service.get_export_file(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="导出文件不存在")

    content, filename = result

    # URL 编码文件名,避免 latin-1 编码错误
    encoded_filename = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.get("/tasks", response_model=ExportTaskListResponse)
async def get_export_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取导出任务列表

    Requirements: 2.3

    - 返回当前用户的导出任务列表
    - 支持分页和状态筛选
    """
    service = AsyncExportService(db)
    tasks, total = service.get_user_export_tasks(user_id=current_user.id, page=page, page_size=page_size, status=status)

    return ExportTaskListResponse(
        items=[
            ExportTaskResponse(
                id=t.id,
                task_id=t.task_id,
                export_type=t.export_type,
                status=t.status,
                record_count=t.record_count or 0,
                file_name=t.file_name,
                file_size=t.file_size,
                error_message=t.error_message,
                created_at=t.created_at,
                started_at=t.started_at,
                completed_at=t.completed_at,
                expires_at=t.expires_at,
                is_downloadable=t.is_downloadable,
            )
            for t in tasks
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
