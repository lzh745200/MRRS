"""
缓存管理 API
提供缓存状态查询、统计信息和缓存清理功能
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.cache import cache_manager, default_cache
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.permission_utils import require_admin
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["缓存管理"])


@router.get("/stats", summary="获取缓存统计信息")
async def get_cache_stats(
    current_user=Depends(get_current_user),
):
    """获取缓存的使用统计信息

    返回缓存中的键数量、命中率、未命中次数等统计。
    用于监控缓存效率和诊断性能问题。
    """
    try:
        backend = default_cache
        item_count = len(backend._store)
        hits = getattr(backend, '_hits', 0)
        misses = getattr(backend, '_misses', 0)
        total_requests = hits + misses
        hit_rate = round((hits / total_requests) * 100, 1) if total_requests > 0 else 0.0

        # 估算缓存大小
        import sys
        estimated_size = sum(
            sys.getsizeof(k) + sys.getsizeof(v) for k, (_, v) in backend._store.items()
        )

        return success_response(
            data={
                "item_count": item_count,
                "max_size": backend._max_size,
                "hits": hits,
                "misses": misses,
                "total_requests": total_requests,
                "hit_rate": hit_rate,
                "estimated_size_bytes": estimated_size,
                "estimated_size_mb": round(estimated_size / 1024 / 1024, 2),
                "backend_type": "memory",
            },
            message="获取缓存统计成功",
        )
    except Exception as e:
        logger.error("获取缓存统计失败: %s", e)
        raise HTTPException(status_code=500, detail="获取缓存统计失败，请稍后重试或联系管理员")


@router.post("/clear", summary="清除全部缓存")
async def clear_cache(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """清除系统中的所有缓存数据

    清理内存缓存，重置统计数据。用于解决缓存引起的临时问题。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可清除缓存")

    try:
        stats_before = len(default_cache._store)
        await cache_manager.clear()
        # 重置统计计数器
        default_cache._hits = 0
        default_cache._misses = 0

        logger.info(
            "缓存已全部清除，清除前键数: %d，操作人: %s",
            stats_before, getattr(current_user, "username", "unknown"),
        )

        return success_response(
            data={
                "cleared_keys": stats_before,
                "timestamp": time.time(),
            },
            message=f"缓存已清除（清除前共 {stats_before} 个键）",
        )
    except Exception as e:
        logger.error("清除缓存失败: %s", e)
        raise HTTPException(status_code=500, detail="清除缓存失败，请稍后重试或联系管理员")
