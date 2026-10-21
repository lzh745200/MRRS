"""离线地图API路由

说明（F 区，瓦片真功能改造）：
- ``GET /offline-map/tiles/{z}/{x}/{y}``：读历史瓦片缓存目录（``data/offline_tiles``）；
- ``GET /offline-map/status``：读取**真实**瓦片仓（安装包预置 / 导入后的
  ``resources/map-tiles``）统计，不再返回内存假数据；
- ``POST /offline-map/download``：单机离线版**不支持**在线抓取，显式 501；
- ``DELETE /offline-map/clear``：清理缓存目录（管理员）。

新的瓦片导入入口为 ``POST /api/v1/map/tiles/import``（管理员，见 map.py）。
"""

# security-audit: exempt work_log — 管理员运维端点（地图瓦片缓存清理/导入），无业务实体变更

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api.v1.map import TILES_DIR
from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.core.security import require_admin
from app.services.offline_map_service import offline_map_service, scan_tiles_dir

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
    """获取离线地图状态（真实目录统计）。

    返回预置/导入瓦片仓（与 ``/map/tile-info`` 同一目录）的计数、体积与缩放
    级别，并附带历史缓存目录的覆盖统计；不返回任何磁盘绝对路径。
    """
    try:
        cache_coverage = await offline_map_service.get_coverage()
        store = scan_tiles_dir(TILES_DIR)
        return success_response(
            data={
                "available": store["total_tiles"] > 0,
                "tileCount": store["total_tiles"],
                "totalBytes": store["total_bytes"],
                "zoomLevels": store["zoom_levels"],
                # 兼容旧字段（前端历史版本 / 运维脚本按 snake_case 读取）
                "total_tiles": store["total_tiles"],
                "total_size_mb": store["total_size_mb"],
                "zoom_levels": store["zoom_levels"],
                "downloadSupported": False,
                "cache": cache_coverage,
            }
        )
    except Exception as e:
        raise BusinessError(f"获取离线地图状态失败: {str(e)}")


@router.post("/download")
async def download_tiles(
    min_lat: float = None,
    max_lat: float = None,
    min_lon: float = None,
    max_lon: float = None,
    min_zoom: int = 4,
    max_zoom: int = 12,
    current_user=Depends(require_admin()),
):
    """在线抓取瓦片（已下线）：单机离线部署无外网，显式 501 而非假成功。

    历史实现在此返回 ``success=True`` 只把区域写进内存列表，前端据此弹出
    "下载完成"（假成功）。现改为明确失败，并指向正确流程：
    运维在联网机器用 ``scripts/tiles/fetch_tiles.py`` / ``slice_tiles.py``
    生成瓦片包 → U 盘拷入 → ``POST /map/tiles/import`` 导入。
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "单机离线版不支持在线抓取瓦片；请由运维生成瓦片包后使用「导入瓦片包」"
            "（POST /api/v1/map/tiles/import）"
        ),
    )


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
