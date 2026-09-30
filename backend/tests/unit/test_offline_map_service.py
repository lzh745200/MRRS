"""
完整测试 - app.services.offline_map_service
覆盖率目标: 100%
"""
import pytest
from unittest.mock import patch
import tempfile
from pathlib import Path

class TestOfflineMapService:
    """测试 OfflineMapService 类"""

    def test_service_import(self):
        """测试类可以导入"""
        from app.services.offline_map_service import OfflineMapService
        assert OfflineMapService is not None

    def test_service_creation(self):
        """测试服务创建"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            assert service is not None
            assert service._map_data == {}
            assert service._downloaded_regions == []

    def test_get_tile_path(self):
        """测试获取瓦片路径"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            path = service.get_tile_path(10, 512, 256)
            assert "10" in str(path) and "512" in str(path) and "256.png" in str(path)

    @pytest.mark.asyncio
    async def test_get_tile_not_exists(self):
        """测试获取不存在的瓦片"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            result = await service.get_tile(10, 999, 999)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_tile_exception(self):
        """测试获取瓦片时的异常处理"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            # 创建一个文件路径但模拟读取异常
            tile_path = service.get_tile_path(10, 512, 256)
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile_path.write_bytes(b"test data")
            # 修改权限模拟读取失败（Windows上可能不生效，但会测试异常处理）
            with patch('aiofiles.open', side_effect=PermissionError("Access denied")):
                result = await service.get_tile(10, 512, 256)
                assert result is None

    @pytest.mark.asyncio
    async def test_save_tile(self):
        """测试保存瓦片"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            result = await service.save_tile(10, 512, 256, b"fake_tile_data")
            assert result is True

    @pytest.mark.asyncio
    async def test_save_tile_failure(self):
        """测试保存瓦片失败"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            # 模拟 aiofiles 抛出异常
            with patch('aiofiles.open', side_effect=IOError("Disk full")):
                result = await service.save_tile(10, 512, 256, b"fake_tile_data")
                assert result is False

    @pytest.mark.asyncio
    async def test_get_tile_exists(self):
        """测试获取存在的瓦片"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            await service.save_tile(10, 512, 256, b"fake_tile_data")
            result = await service.get_tile(10, 512, 256)
            assert result == b"fake_tile_data"

    @pytest.mark.asyncio
    async def test_get_coverage_empty(self):
        """测试获取空缓存覆盖范围"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            result = await service.get_coverage()
            assert result["total_tiles"] == 0
            assert result["total_size_mb"] == 0.0
            assert result["zoom_levels"] == []

    @pytest.mark.asyncio
    async def test_get_coverage_with_tiles(self):
        """测试获取有瓦片的覆盖范围"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            await service.save_tile(10, 512, 256, b"fake_tile_data")
            result = await service.get_coverage()
            assert result["total_tiles"] == 1
            assert result["total_size_mb"] >= 0  # 可能为0如果数据太小
            assert 10 in result["zoom_levels"]

    @pytest.mark.asyncio
    async def test_get_coverage_with_invalid_dir(self):
        """测试获取覆盖范围时遇到无效目录名"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            # 创建一个非数字命名的目录（会被跳过）
            invalid_dir = Path(tmpdir) / "not_a_number"
            invalid_dir.mkdir()
            result = await service.get_coverage()
            # 应该跳过无效目录名
            assert result["total_tiles"] == 0

    def test_tile_to_lat_lon(self):
        """测试瓦片坐标转经纬度"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        lat, lon = service.tile_to_lat_lon(0, 0, 0)
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_lat_lon_to_tile(self):
        """测试经纬度转瓦片坐标"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        x, y = service.lat_lon_to_tile(0, 0, 10)
        assert isinstance(x, int)
        assert isinstance(y, int)
        assert x >= 0
        assert y >= 0

    def test_download_region(self):
        """测试下载区域"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        result = service.download_region("beijing")
        assert result is True
        assert "beijing" in service._downloaded_regions

    def test_is_region_available(self):
        """测试检查区域可用性"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        assert service.is_region_available("beijing") is False
        service.download_region("beijing")
        assert service.is_region_available("beijing") is True

    def test_get_downloaded_regions(self):
        """测试获取已下载区域"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        service.download_region("beijing")
        service.download_region("shanghai")
        regions = service.get_downloaded_regions()
        assert "beijing" in regions
        assert "shanghai" in regions

    def test_clear_cache(self):
        """测试清除缓存"""
        from app.services.offline_map_service import OfflineMapService
        service = OfflineMapService()
        service._map_data = {"key": "value"}
        service.clear_cache()
        assert service._map_data == {}


class TestCoverageRobustness:
    """深审 P-1：缓存目录被删除 / 扫描中文件消失时的健壮性。"""

    @pytest.mark.asyncio
    async def test_get_coverage_when_cache_dir_removed(self):
        """__init__ 后目录被外部删除 → 应返回零覆盖而非抛 FileNotFoundError。"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            Path(tmpdir).rmdir()
            result = await service.get_coverage()
            assert result["total_tiles"] == 0
            assert result["zoom_levels"] == []
            # 结果被缓存，二次调用不再打盘
            assert service._coverage_cache is not None

    @pytest.mark.asyncio
    async def test_get_coverage_skips_non_dir_entries(self):
        """z 层目录下混入普通文件不应计数，也不应崩。"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            (Path(tmpdir) / "10" / "1").mkdir(parents=True)
            (Path(tmpdir) / "10" / "1" / "2.png").write_bytes(b"tile")
            (Path(tmpdir) / "10" / "stray.txt").write_text("noise", encoding="utf-8")
            result = await service.get_coverage()
            assert result["total_tiles"] == 1

    @pytest.mark.asyncio
    async def test_get_coverage_survives_stat_failure(self):
        """扫描中某瓦片 stat() 抛 OSError（并发删除/占用）应跳过而非中断。"""
        from app.services.offline_map_service import OfflineMapService
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OfflineMapService(cache_dir=Path(tmpdir))
            (Path(tmpdir) / "10" / "1").mkdir(parents=True)
            bad = Path(tmpdir) / "10" / "1" / "9.png"
            bad.write_bytes(b"tile")

            # 同时放一个好瓦片与一个非 png 文件：
            # 坏瓦片被跳过、非 png 被跳过、好瓦片仍被统计
            (Path(tmpdir) / "10" / "1" / "1.png").write_bytes(b"ok")
            (Path(tmpdir) / "10" / "1" / "readme.txt").write_bytes(b"x")

            real_stat = Path.stat

            def flaky_stat(self, *a, **kw):
                # 只让目标瓦片的 stat 失败；目录枚举（is_dir/iterdir 内部也走 stat）
                # 与好瓦片不受影响
                if self.name == "9.png":
                    raise OSError("vanished")
                return real_stat(self, *a, **kw)

            with patch.object(Path, "stat", flaky_stat):
                result = await service.get_coverage()

            # 坏瓦片被跳过（不中断统计），好瓦片仍计入
            assert result["total_tiles"] == 1
            assert result["zoom_levels"] == [10]

class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from app.services.offline_map_service import offline_map_service
        assert offline_map_service is not None

    def test_global_instance_is_service(self):
        """测试全局实例是服务类型"""
        from app.services.offline_map_service import offline_map_service, OfflineMapService
        assert isinstance(offline_map_service, OfflineMapService)
