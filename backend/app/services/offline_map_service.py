"""
离线地图服务

提供离线地图功能
"""

import math
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging

from app.utils.paths import get_data_path

logger = logging.getLogger(__name__)

# 单张瓦片 PNG 的读取上限（256x256 瓦片实测 5~50KB；上限只为把"文件被替换成
# 巨型文件"这类异常挡在内存之外，见 P-1 check_unbounded_read 门禁）
MAX_TILE_BYTES = 5 * 1024 * 1024

# 模块级别获取瓦片缓存目录。
# 使用 try/except 防护：如果 get_data_path() 因权限问题失败，
# 回退到用户临时目录，避免整个路由模块加载失败（crash log 中曾导致 41/42 路由加载）。
try:
    TILE_CACHE_DIR = get_data_path("offline_tiles")
except Exception as _e:
    import tempfile
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "离线地图缓存目录初始化失败，回退到临时目录: %s", _e
    )
    TILE_CACHE_DIR = Path(tempfile.gettempdir()) / "bumofu_offline_tiles"


class OfflineMapService:
    """
    离线地图服务

    管理离线地图的下载和使用
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or TILE_CACHE_DIR
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"创建离线地图缓存目录失败: {e}")
        self._map_data = {}
        self._downloaded_regions = []
        self._coverage_cache: Optional[Dict[str, Any]] = None

    def get_tile_path(self, z: int, x: int, y: int) -> Path:
        """获取瓦片文件路径"""
        return self.cache_dir / f"{z}/{x}/{y}.png"

    async def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        """获取瓦片数据"""
        tile_path = self.get_tile_path(z, x, y)
        if not tile_path.exists():
            return None
        try:
            async with aiofiles.open(tile_path, "rb") as f:
                data = await f.read(MAX_TILE_BYTES)
            return data
        except Exception:
            logger.warning("离线地图瓦片读取失败: %s", tile_path, exc_info=True)
            return None

    async def save_tile(self, z: int, x: int, y: int, data: bytes) -> bool:
        """保存瓦片数据"""
        try:
            tile_path = self.get_tile_path(z, x, y)
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(tile_path, "wb") as f:
                await f.write(data)
            self._coverage_cache = None  # 覆盖范围变更，刷新缓存
            return True
        except Exception as e:
            logger.error(f"Failed to save tile: {e}")
            return False

    async def get_coverage(self) -> Dict[str, Any]:
        """获取地图覆盖范围统计（带缓存）"""
        if self._coverage_cache is not None:
            return self._coverage_cache

        total_tiles = 0
        total_size = 0
        zoom_levels = set()

        for z_dir in self.cache_dir.iterdir():
            if z_dir.is_dir():
                try:
                    zoom_level = int(z_dir.name)
                    zoom_levels.add(zoom_level)
                    for x_dir in z_dir.iterdir():
                        if x_dir.is_dir():
                            for tile_file in x_dir.iterdir():
                                if tile_file.suffix == ".png":
                                    total_tiles += 1
                                    total_size += tile_file.stat().st_size
                except ValueError:
                    continue

        self._coverage_cache = {
            "total_tiles": total_tiles,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "zoom_levels": sorted(list(zoom_levels)),
        }
        return self._coverage_cache

    def tile_to_lat_lon(self, x: int, y: int, z: int) -> Tuple[float, float]:
        """将瓦片坐标转换为经纬度"""
        n = 2.0**z
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)

    def lat_lon_to_tile(self, lat: float, lon: float, z: int) -> Tuple[int, int]:
        """将经纬度转换为瓦片坐标"""
        lat_rad = math.radians(lat)
        n = 2.0**z
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)

    def download_region(self, region: str) -> bool:
        """下载区域地图"""
        if region not in self._downloaded_regions:
            self._downloaded_regions.append(region)
        return True

    def is_region_available(self, region: str) -> bool:
        """检查区域地图是否可用"""
        return region in self._downloaded_regions

    def get_downloaded_regions(self) -> List[str]:
        """获取已下载的区域列表"""
        return self._downloaded_regions.copy()

    def clear_cache(self):
        """清除地图缓存"""
        self._map_data.clear()
        self._coverage_cache = None


# 全局单例
offline_map_service = OfflineMapService()
