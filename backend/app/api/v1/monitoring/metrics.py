"""
监控指标 API
提供业务指标查询和 Prometheus 格式导出
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.middleware.metrics_middleware import metrics_store
from app.models.user import User
from app.services.business_metrics_service import business_metrics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["监控指标"])


@router.get("/business")
async def get_business_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取业务指标
    - 资金审批成功率
    - 资金拨付率
    - 数据上报完成率
    - 用户活跃度
    - 系统错误率
    """
    return business_metrics_service.get_all_metrics()


@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    获取 Prometheus 格式的指标
    用于 Grafana 等监控工具集成
    """
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        content=business_metrics_service.to_prometheus_format(), media_type="text/plain; charset=utf-8"
    )


@router.get("/performance-dashboard")
async def get_performance_dashboard(
    current_user: User = Depends(get_current_active_user),
):
    """
    性能监控面板 — 综合展示 HTTP 请求指标、慢请求、错误率等
    需要管理员权限
    """
    if not current_user.is_superuser:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="需要管理员权限")

    summary = metrics_store.get_summary()

    # 慢请求 / 慢 SQL（P2-3：来自 SlowRequestMiddleware 环形缓冲，阈值可配置）
    from app.middleware.slow_request_monitor import (
        get_slow_api_records,
        get_slow_sql_records,
        get_slow_stats,
    )

    slow_api = get_slow_api_records(limit=50)
    slow_sql = get_slow_sql_records(limit=50)
    slow_stats = get_slow_stats()

    # 数据库统计
    db_stats = {}
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            # 表行数统计（tables 为硬编码白名单，不接收任何外部输入，无注入风险）
            tables = ["users", "funds", "projects", "supported_villages", "schools", "audit_logs"]
            for table in tables:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))  # nosec B608 - table 来自上方硬编码白名单
                db_stats[table] = result.scalar() or 0
            # 数据库文件大小（SQLite）
            from app.core.database import IS_SQLITE
            if IS_SQLITE:
                result = db.execute(text("PRAGMA page_count"))
                page_count = result.scalar() or 0
                result2 = db.execute(text("PRAGMA page_size"))
                page_size = result2.scalar() or 0
                db_stats["db_size_mb"] = round(page_count * page_size / 1024 / 1024, 2)
        finally:
            db.close()
    except Exception as e:
        # 数据库统计收集失败不应拖垮整个监控接口，但必须留痕
        logger.warning("数据库统计收集失败，返回空统计: %s", e, exc_info=True)

    return {
        "code": 200,
        "success": True,
        "message": "成功",
        "data": {
            "http_metrics": summary,
            "db_stats": db_stats,
            "slow_api": slow_api,
            "slow_sql": slow_sql,
            "slow_stats": slow_stats,
        }
    }
