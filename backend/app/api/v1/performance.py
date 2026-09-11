"""
性能监控API
提供查询性能分析、慢查询日志等功能
"""

# security-audit: exempt work_log — 超管运维端点（清理慢查询/缓存），无业务实体变更

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_current_active_user
from app.core.response import ok_list, success_response
from app.core.redis_adapter import redis_adapter
from app.models.user import User
from app.services.query_analyzer_service import query_analyzer

router = APIRouter(prefix="/performance")


@router.get("/slow-queries")
async def get_slow_queries(
    limit: int = Query(100, ge=1, le=1000),
    min_duration_ms: Optional[float] = Query(None, ge=0),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取慢查询列表
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    slow_queries = query_analyzer.get_slow_queries(limit=limit, min_duration_ms=min_duration_ms)

    return ok_list(
        items=slow_queries,
        total=len(slow_queries),
        page=1,
        page_size=limit,
        message="成功获取慢查询列表"
    )


@router.get("/query-stats")
async def get_query_stats(current_user: User = Depends(get_current_active_user)):
    """
    获取查询统计信息
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    stats = query_analyzer.get_query_stats()

    return success_response(data=stats, message="成功获取查询统计信息")


@router.delete("/slow-queries")
async def clear_slow_queries(current_user: User = Depends(get_current_active_user)):
    """
    清空慢查询记录
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    query_analyzer.clear_slow_queries()

    return success_response(message="慢查询记录已清空")


@router.get("/cache-stats")
async def get_cache_stats(current_user: User = Depends(get_current_active_user)):
    """
    获取缓存统计信息
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    stats = redis_adapter.get_stats()
    health = redis_adapter.health_check()

    return success_response(data={"stats": stats, "health": health}, message="成功获取缓存统计信息")


@router.post("/cache/clear")
async def clear_cache(current_user: User = Depends(get_current_active_user)):
    """
    清空缓存
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    success = redis_adapter.clear()

    if success:
        return success_response(message="缓存已清空")
    else:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="清空缓存失败")
