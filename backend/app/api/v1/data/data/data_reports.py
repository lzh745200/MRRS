"""
Data Report API
数据上报管理接口
"""
import io
import json
import os as _os
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessError, NotFoundException
from app.core.permission_utils import get_user_org_id
from app.core.response import success_response
from app.core.security import get_current_user
from app.models.data_report import ReportStatus
from app.schemas.data_report import (DataReportCreate, DataReportListResponse,
                                     DataReportResponse, DataReportReview,
                                     DataReportStatistics,
                                     SubordinateReportDashboard)
from app.services.data_report_service import (DataReportService,
                                              ReportNotFoundError,
                                              ReportStatusError)
from app.core.transaction import safe_commit
from app.services.organization_permission_service import \
    OrganizationPermissionService

router = APIRouter(prefix="/data-reports", tags=["数据上报"])


def get_report_service(db: Session = Depends(get_db)) -> DataReportService:
    return DataReportService(db)


def get_permission_service(db: Session = Depends(get_db)) -> OrganizationPermissionService:
    return OrganizationPermissionService(db)


@router.get("", response_model=DataReportListResponse)
async def list_data_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    direction: str = Query("received", pattern="^(received|submitted)$"),
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """
    获取数据上报列表

    - direction=received: 获取收到的上报（作为上级）
    - direction=submitted: 获取提交的上报（作为下级）
    """
    if not hasattr(current_user, "org_id") or not current_user.org_id:
        return DataReportListResponse(total=0, page=page, page_size=page_size, items=[])

    org_id = current_user.org_id

    if direction == "received":
        reports = service.get_subordinate_reports(org_id, status=status, skip=(page - 1) * page_size, limit=page_size)
    else:
        reports = service.get_submitted_reports(org_id, status=status, skip=(page - 1) * page_size, limit=page_size)

    return DataReportListResponse(
        total=len(reports),
        page=page,
        page_size=page_size,
        items=[DataReportResponse.model_validate(r) for r in reports],
    )


@router.get("/statistics", response_model=DataReportStatistics)
async def get_report_statistics(
    current_user=Depends(get_current_user), service: DataReportService = Depends(get_report_service)
):
    """获取上报统计"""
    if not hasattr(current_user, "org_id") or not current_user.org_id:
        return DataReportStatistics(total=0, submitted=0, approved=0, rejected=0, pending=0)

    return service.get_report_statistics(current_user.org_id)


@router.get("/dashboard", response_model=SubordinateReportDashboard)
async def get_subordinate_dashboard(
    current_user=Depends(get_current_user), service: DataReportService = Depends(get_report_service)
):
    """获取下级单位上报仪表板"""
    if not hasattr(current_user, "org_id") or not current_user.org_id:
        return SubordinateReportDashboard(
            total_subordinates=0, reported_count=0, unreported_count=0, statistics=None, subordinates=[]
        )

    return service.get_subordinate_dashboard(current_user.org_id)


@router.get("/pending")
async def get_pending_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """获取待审批的上报"""
    if not hasattr(current_user, "org_id") or not current_user.org_id:
        from app.core.response import ok_list
        return ok_list(items=[], total=0)

    reports = service.get_subordinate_reports(
        current_user.org_id, status=ReportStatus.SUBMITTED.value, skip=(page - 1) * page_size, limit=page_size
    )

    from app.core.response import ok_list

    return ok_list(
        items=[DataReportResponse.model_validate(r) for r in reports],
        total=len(reports),
        page=page,
        page_size=page_size,
        message="成功获取待审批上报列表"
    )


@router.get("/received")
async def list_received_reports(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """
    获取接收的数据上报列表

    返回下级单位上报给当前用户所在组织的数据
    """
    from app.models.data_report import DataReport

    org_id = get_user_org_id(current_user)
    if not org_id:
        from app.core.response import ok_list
        return ok_list(items=[], total=0)

    query = service.db.query(DataReport).filter(DataReport.target_org_id == org_id)

    if status:
        query = query.filter(DataReport.status == status)

    total = query.count()
    reports = query.order_by(DataReport.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    from app.core.response import ok_list

    return ok_list(
        items=[DataReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        message="成功获取待审批上报列表"
    )


@router.get("/{report_id}", response_model=DataReportResponse)
async def get_data_report(
    report_id: int,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取上报详情"""
    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限：来源组织或目标组织的用户可以查看
    user_org_id = getattr(current_user, "org_id", None)
    if user_org_id not in [report.source_org_id, report.target_org_id]:
        # 检查是否是上级组织
        if not permission_service.can_access_organization(current_user.id, report.source_org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该上报")

    return DataReportResponse.model_validate(report)


@router.post("", response_model=DataReportResponse, status_code=status.HTTP_201_CREATED)
async def create_data_report(
    data: DataReportCreate,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """创建上报"""
    if not hasattr(current_user, "org_id") or not current_user.org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户未关联组织")

    try:
        report = await service.create_report(data=data, source_org_id=current_user.org_id, created_by=current_user.id)

        return DataReportResponse.model_validate(report)

    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{report_id}/submit", response_model=DataReportResponse)
async def submit_report(
    report_id: int,
    comment: Optional[str] = None,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """提交上报"""
    try:
        report = await service.submit_report(report_id=report_id, submitted_by=current_user.id, comment=comment)

        return DataReportResponse.model_validate(report)

    except ReportNotFoundError:
        raise NotFoundException("上报不存在")
    except ReportStatusError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{report_id}/review", response_model=DataReportResponse)
async def review_report(
    report_id: int,
    review: DataReportReview,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """审批上报"""
    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限：只有目标组织的用户可以审批
    user_org_id = getattr(current_user, "org_id", None)
    if user_org_id != report.target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有上级单位可以审批")

    try:
        report = await service.review_report(report_id=report_id, review=review, reviewed_by=current_user.id)

        return DataReportResponse.model_validate(report)

    except ReportStatusError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{report_id}/cancel", response_model=DataReportResponse)
async def cancel_report(
    report_id: int,
    reason: Optional[str] = None,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """取消上报"""
    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限：只有来源组织的用户可以取消
    user_org_id = getattr(current_user, "org_id", None)
    if user_org_id != report.source_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有提交单位可以取消")

    # 检查状态
    if report.status not in [ReportStatus.DRAFT.value, ReportStatus.REJECTED.value]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许取消")

    report.status = ReportStatus.CANCELLED.value
    report.comment = reason
    safe_commit(service.db)
    service.db.refresh(report)

    return DataReportResponse.model_validate(report)


@router.post("/{report_id}/resubmit", response_model=DataReportResponse)
async def resubmit_report(
    report_id: int,
    comment: Optional[str] = None,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """重新提交被拒绝的上报"""
    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限：只有来源组织的用户可以重新提交
    user_org_id = getattr(current_user, "org_id", None)
    if user_org_id != report.source_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有提交单位可以重新提交")

    # 检查状态
    if report.status != ReportStatus.REJECTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有被拒绝的上报可以重新提交")

    try:
        report = await service.submit_report(report_id=report_id, submitted_by=current_user.id, comment=comment)

        return DataReportResponse.model_validate(report)

    except ReportStatusError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{report_id}/approve", response_model=DataReportResponse)
async def approve_data_report(
    report_id: int,
    comment: Optional[str] = None,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
):
    """批准数据上报并导入数据"""
    from app.models.data_package import DataPackage
    from app.models.data_report import DataReport, ReportStatus
    from app.services.data_package_service import DataPackageService

    report = service.db.query(DataReport).filter(DataReport.id == report_id).first()
    if not report:
        raise NotFoundException("上报不存在")

    if report.status != ReportStatus.SUBMITTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能批准已提交的上报")

    # 检查权限：只有目标组织的用户可以批准
    user_org_id = getattr(current_user, "org_id", None)
    if user_org_id != report.target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有上级单位可以批准")

    # 导入数据包
    package_service = DataPackageService(service.db)
    package = service.db.query(DataPackage).filter(DataPackage.id == report.package_id).first()

    if package:
        try:
            await package_service.confirm_import(
                package_id=package.id, confirmed_by=current_user.id, overwrite_existing=False
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"导入数据包失败: {str(e)}")

    # 更新上报状态
    from datetime import datetime, timezone

    report.status = ReportStatus.APPROVED.value
    report.reviewed_at = datetime.now(timezone.utc)
    report.reviewed_by = current_user.id
    report.comment = comment

    safe_commit(service.db)
    service.db.refresh(report)

    return DataReportResponse.model_validate(report)


@router.get("/{report_id}/package")
async def get_report_package(
    report_id: int,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取上报关联的数据包信息"""
    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限
    user_org_id = get_user_org_id(current_user)
    if user_org_id not in [report.source_org_id, report.target_org_id]:
        if not permission_service.can_access_organization(current_user.id, report.source_org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该上报的数据包")

    # 获取数据包信息

    # 简化返回
    return success_response(data={"report_id": report_id, "package_id": report.package_id})


@router.get("/{report_id}/preview")
async def preview_data_report(
    report_id: int,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """预览上报数据内容"""
    from app.models.data_package import DataPackage

    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限
    user_org_id = get_user_org_id(current_user)
    if user_org_id not in [report.source_org_id, report.target_org_id]:
        if not permission_service.can_access_organization(current_user.id, report.source_org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该上报")

    # 获取关联的数据包信息
    preview_data = {
        "report_id": report.id,
        "report_code": report.report_code,
        "title": report.title,
        "status": report.status,
        "source_org_id": report.source_org_id,
        "target_org_id": report.target_org_id,
        "description": report.description,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

    # 如果有数据包，获取包内的数据摘要
    package = service.db.query(DataPackage).filter(DataPackage.id == report.package_id).first()
    if package:
        preview_data["package"] = {
            "package_id": package.id,
            "package_code": package.package_code,
            "file_name": package.file_name,
            "file_size": package.file_size,
            "record_count": package.record_count,
            "data_types": package.data_types or [],
            "status": package.status.value if hasattr(package.status, "value") else str(package.status),
        }

    return success_response(data=preview_data)


@router.get("/{report_id}/download")
async def download_data_report(
    report_id: int,
    current_user=Depends(get_current_user),
    service: DataReportService = Depends(get_report_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """下载上报数据包文件"""
    from app.models.data_package import DataPackage

    report = service.get_report(report_id)
    if not report:
        raise NotFoundException("上报不存在")

    # 检查权限
    user_org_id = get_user_org_id(current_user)
    if user_org_id not in [report.source_org_id, report.target_org_id]:
        if not permission_service.can_access_organization(current_user.id, report.source_org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权下载该上报")

    # 获取数据包文件
    package = service.db.query(DataPackage).filter(DataPackage.id == report.package_id).first()

    if package and package.file_path:
        if _os.path.exists(package.file_path):
            return FileResponse(
                path=package.file_path,
                filename=package.file_name or f"report_{report_id}.dat",
                media_type="application/octet-stream",
            )

    # 如果没有物理文件，返回 JSON 摘要
    preview_data = {
        "report_id": report.id,
        "report_code": report.report_code,
        "title": report.title,
        "status": report.status,
        "source_org_id": report.source_org_id,
        "target_org_id": report.target_org_id,
        "description": report.description,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
    json_bytes = json.dumps(preview_data, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"report_{report.report_code}_{datetime.now().strftime('%Y%m%d')}.json"

    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
