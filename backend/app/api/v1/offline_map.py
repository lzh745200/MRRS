"""离线地图API路由"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.core.security import require_admin
from app.services.offline_map_service import offline_map_service

router = APIRouter(prefix="/offline-map", tags=["离线地图"])


@router.get("/tiles/{z}/{x}/{y}")
async def get_tile(z: int, x: int, y: int):
    """
    获取地图瓦片
    优先返回本地瓦片,如果不存在则返回404
    """
    try:
        # 验证参数
        if z < 0 or z > 18:
            raise HTTPException(status_code=400, detail="Invalid zoom level")

        tile_data = await offline_map_service.get_tile(z, x, y)

        if tile_data:
            return Response(
                content=tile_data,
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=86400",  # 缓存1天
                },
            )
        else:
            raise HTTPException(status_code=404, detail="Tile not found")

    except HTTPException:
        raise
    except Exception as e:
        raise BusinessError(f"获取地图瓦片失败: {str(e)}")


@router.get("/status")
async def get_status():
    """获取离线地图状态"""
    try:
        coverage = await offline_map_service.get_coverage()
        return success_response(data=coverage)
    except Exception as e:
        raise BusinessError(f"获取离线地图状态失败: {str(e)}")


@router.post("/download")
async def download_tiles(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    min_zoom: int = 4,
    max_zoom: int = 12,
    current_user=Depends(require_admin()),
):
    """
    下载指定区域的瓦片(管理员功能)
    注意: 需要网络连接
    """
    try:
        # 验证参数
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise HTTPException(status_code=400, detail="Invalid latitude")
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise HTTPException(status_code=400, detail="Invalid longitude")
        if not (0 <= min_zoom <= 18 and 0 <= max_zoom <= 18):
            raise HTTPException(status_code=400, detail="Invalid zoom level")
        if min_zoom > max_zoom:
            raise HTTPException(status_code=400, detail="min_zoom must be <= max_zoom")

        # 服务按区域标识记录已下载区域，由请求参数构造区域标识（同步方法）
        region = f"{min_lat},{min_lon}-{max_lat},{max_lon}@{min_zoom}-{max_zoom}"
        success = offline_map_service.download_region(region)
        return success_response(data={"region": region}, success=success)

    except HTTPException:
        raise
    except Exception as e:
        raise BusinessError(f"下载地图瓦片失败: {str(e)}")


@router.delete("/clear")
async def clear_tiles(
    current_user=Depends(require_admin()),
):
    """清理瓦片缓存(管理员功能)，服务层为整体清理，不支持按缩放级别"""
    try:
        offline_map_service.clear_cache()
        return success_response(message="瓦片缓存已清理")

    except Exception as e:
        raise BusinessError(f"清理瓦片缓存失败: {str(e)}")
