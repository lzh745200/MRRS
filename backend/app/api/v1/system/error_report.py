"""
错误报告API
提供系统错误收集、上报、查询和统计功能
用于帮扶管理信息系统的运维监控

P2-6: 已从内存存储迁移到数据库持久化（error_reports 表）。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func

from app.core.database import SessionLocal
from app.core.security import get_current_user
from app.models.error_report import ErrorReport
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/error-reports", tags=["错误报告"])


# ==================== Pydantic 模型 ====================

class ErrorReportCreate(BaseModel):
    """创建错误报告请求体"""
    source: str = Field(..., description="错误来源模块")
    error_type: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    stack_trace: Optional[str] = Field(None, description="堆栈跟踪信息")
    context: Optional[dict] = Field(None, description="上下文信息")
    severity: str = Field("warning", description="严重程度: info/warning/error/critical")


class ErrorReportUpdate(BaseModel):
    """更新错误报告状态"""
    status: str = Field(..., description="状态: resolved/ignored/in_progress")
    resolution_note: Optional[str] = Field(None, description="处理备注")


# ==================== API 端点 ====================

@router.post("", summary="上报系统错误")
async def report_error(
    report: ErrorReportCreate,
    request: Request,
    current_user=Depends(get_current_user),
):
    """上报系统错误信息"""
    db = SessionLocal()
    try:
        record = ErrorReport(
            source=report.source,
            error_type=report.error_type,
            message=report.message,
            stack_trace=report.stack_trace,
            context=json.dumps(report.context, ensure_ascii=False) if report.context else None,
            severity=report.severity,
            status="open",
            reporter=getattr(current_user, "username", "anonymous"),
        )
        db.add(record)
        safe_commit(db)
        db.refresh(record)

        logger.warning(
            "错误报告 #%d [%s/%s]: %s (来源: %s)",
            record.id, report.severity, report.error_type, report.message, report.source,
        )

        return {
            "success": True,
            "message": "错误报告已提交，运维人员将尽快处理",
            "data": {"report_id": record.id},
        }
    except Exception as e:
        db.rollback()
        logger.error("错误报告写入失败: %s", e)
        raise HTTPException(status_code=500, detail="错误报告写入失败")
    finally:
        db.close()


@router.get("", summary="获取错误报告列表")
async def list_error_reports(
    source: Optional[str] = Query(None, description="按来源筛选"),
    severity: Optional[str] = Query(None, description="按严重程度筛选"),
    status: Optional[str] = Query("open", description="按状态筛选: open/resolved/ignored/all"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user=Depends(get_current_user),
):
    """获取错误报告列表"""
    db = SessionLocal()
    try:
        query = db.query(ErrorReport)
        if source:
            query = query.filter(ErrorReport.source == source)
        if severity:
            query = query.filter(ErrorReport.severity == severity)
        if status and status != "all":
            query = query.filter(ErrorReport.status == status)

        total = query.count()
        items = (
            query.order_by(ErrorReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "success": True,
            "data": {
                "items": [r.to_dict() for r in items],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    finally:
        db.close()


@router.get("/stats", summary="获取错误统计")
async def get_error_stats(current_user=Depends(get_current_user)):
    """获取错误报告统计数据"""
    db = SessionLocal()
    try:
        total = db.query(func.count(ErrorReport.id)).scalar() or 0
        open_errors = db.query(func.count(ErrorReport.id)).filter(ErrorReport.status == "open").scalar() or 0
        critical_errors = db.query(func.count(ErrorReport.id)).filter(ErrorReport.severity == "critical").scalar() or 0

        by_source_rows = (
            db.query(ErrorReport.source, func.count(ErrorReport.id))
            .group_by(ErrorReport.source)
            .all()
        )
        by_source = {row[0]: row[1] for row in by_source_rows}

        by_severity_rows = (
            db.query(ErrorReport.severity, func.count(ErrorReport.id))
            .group_by(ErrorReport.severity)
            .all()
        )
        by_severity = {row[0]: row[1] for row in by_severity_rows}

        return {
            "success": True,
            "data": {
                "total": total,
                "open": open_errors,
                "critical": critical_errors,
                "by_source": by_source,
                "by_severity": by_severity,
            },
        }
    finally:
        db.close()


@router.get("/{report_id}", summary="获取错误报告详情")
async def get_error_report(
    report_id: int,
    current_user=Depends(get_current_user),
):
    """获取指定错误报告的详细信息"""
    db = SessionLocal()
    try:
        record = db.query(ErrorReport).filter(ErrorReport.id == report_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="错误报告不存在")
        return {"success": True, "data": record.to_dict()}
    finally:
        db.close()


@router.put("/{report_id}", summary="更新错误报告状态")
async def update_error_report(
    report_id: int,
    update: ErrorReportUpdate,
    current_user=Depends(get_current_user),
):
    """更新错误报告处理状态（仅本人或管理员）"""
    db = SessionLocal()
    try:
        record = db.query(ErrorReport).filter(ErrorReport.id == report_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="错误报告不存在")

        # 归属校验: 仅报告提交者本人或管理员可修改
        from app.core.permission_utils import is_admin

        is_owner = getattr(record, "user_id", None) is None or getattr(record, "user_id", None) == getattr(
            current_user, "id", None
        )
        if not is_owner and not is_admin(current_user):
            raise HTTPException(status_code=403, detail="无权修改该错误报告")

        record.status = update.status
        record.resolution_note = update.resolution_note
        if update.status == "resolved":
            record.resolved_at = datetime.now(timezone.utc)
        safe_commit(db)

        return {
            "success": True,
            "message": f"错误报告 #{report_id} 状态已更新为 {update.status}",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("更新错误报告失败: %s", e)
        raise HTTPException(status_code=500, detail="更新失败")
    finally:
        db.close()


@router.post("/report-exception", summary="报告当前异常")
async def report_current_exception(
    source: str = Query(..., description="异常来源模块"),
    message: str = Query(..., description="异常描述"),
    current_user=Depends(get_current_user),
):
    """简化版异常上报接口"""
    db = SessionLocal()
    try:
        record = ErrorReport(
            source=source,
            error_type="runtime_exception",
            message=message,
            severity="error",
            status="open",
            reporter=getattr(current_user, "username", "anonymous"),
        )
        db.add(record)
        safe_commit(db)
        db.refresh(record)

        logger.error("异常上报 #%d [%s]: %s", record.id, source, message)

        return {
            "success": True,
            "message": "异常已记录，感谢您的反馈",
            "data": {"report_id": record.id},
        }
    except Exception as e:
        db.rollback()
        logger.error("异常上报写入失败: %s", e)
        raise HTTPException(status_code=500, detail="异常上报写入失败")
    finally:
        db.close()
