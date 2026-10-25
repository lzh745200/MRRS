"""`/api/v1/map/tile-info` 覆盖 bbox 回归（P0：多包叠加后 bbox＝最后导入包）。

现场缺陷：`bbox` 原优先取 `MANIFEST.region.bbox`，而多包叠加导入时 MANIFEST 只是
"最后导入的那个包"。先导贵阳、再导遵义后 bbox 变遵义 → 前端 `maxBounds` 把贵阳瓦片
挡在视野外（数据在库、却看不到）。

目标契约：
- `scan_tiles_dir()` 在遍历瓦片时顺带累计**真实覆盖范围** `bounds`
  （`[min_lon, min_lat, max_lon, max_lat]`；无瓦片为 ``None``），不额外遍历目录；
- `tile-info.bbox` 优先级：**扫描实测 bounds → MANIFEST region.bbox/bbox → 贵州兜底**；
- 目录不存在分支保持现状（省 bbox + ``dir_missing``）。

多包并集用例坐标（z=10）：
- 贵阳组：(815, 429) + (817, 432)
- 遵义组：(810, 425) + (815, 431)
期望 bbox = [104.765625, 26.74561, 107.578125, 29.22889]（由 XYZ 墨卡托换算，
见 ``_tile_bounds``）。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

import app.api.v1.map as map_mod
from app.services.offline_map_service import scan_tiles_dir

BASE = "/api/v1/map"
PROVINCE_BBOX = [103.6, 24.6, 109.6, 29.2]
PNG = b"\x89PNG\r\n\x1a\n" + b"tile"

# 贵阳组 / 遵义组（z=10，模拟两个不同市州包）
GUIYANG_TILES = [(10, 815, 429), (10, 817, 432)]
ZUNYI_TILES = [(10, 810, 425), (10, 815, 431)]
ALL_TILES = GUIYANG_TILES + ZUNYI_TILES

GUIYANG_EXPECTED = [106.523438, 26.74561, 107.578125, 27.994401]
UNION_EXPECTED = [104.765625, 26.74561, 107.578125, 29.22889]


def _tile_bounds(z: int, x: int, y: int):
    """XYZ 瓦片经纬度包围盒 ``[min_lon, min_lat, max_lon, max_lat]``。"""
    n = float(1 << z)
    min_lon = x / n * 360.0 - 180.0
    max_lon = (x + 1) / n * 360.0 - 180.0
    max_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    min_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return [min_lon, min_lat, max_lon, max_lat]


def _write_tile(root: Path, z: int, x: int, y: int) -> None:
    path = root / str(z) / str(x) / f"{y}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)


def _union(tiles) -> list:
    boxes = [_tile_bounds(z, x, y) for z, x, y in tiles]
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _write_manifest(root: Path, bbox, region_bbox=None) -> None:
    manifest = {"schemaVersion": 1, "provider": "osm-test", "tileCount": 0, "bbox": bbox}
    if region_bbox is not None:
        manifest["region"] = {"name": "最后导入包", "bbox": region_bbox}
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")


def _tile_info(client, root: Path) -> dict:
    with patch.object(map_mod, "TILES_DIR", root):
        return client.get(f"{BASE}/tile-info").json()["data"]


# ==================== 底层扫描：bounds 累计 ====================


class TestScanTilesDirBounds:
    def test_bounds_union_of_all_tiles(self, tmp_path):
        for z, x, y in ALL_TILES:
            _write_tile(tmp_path, z, x, y)
        stats = scan_tiles_dir(tmp_path)
        assert stats["bounds"] == pytest.approx(UNION_EXPECTED, abs=1e-6)

    def test_existing_keys_kept(self, tmp_path):
        for z, x, y in GUIYANG_TILES:
            _write_tile(tmp_path, z, x, y)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 2
        assert stats["zoom_levels"] == [10]
        assert stats["total_bytes"] == len(PNG) * 2
        assert "total_size_mb" in stats

    def test_empty_dir_bounds_none(self, tmp_path):
        (tmp_path / "not-a-zoom").mkdir()
        assert scan_tiles_dir(tmp_path)["bounds"] is None

    def test_missing_dir_bounds_none(self, tmp_path):
        stats = scan_tiles_dir(tmp_path / "absent")
        assert stats["bounds"] is None
        assert stats["total_tiles"] == 0

    def test_non_numeric_dirs_do_not_break_bounds(self, tmp_path):
        # 合法瓦片 + 非法坐标目录混放：合法瓦片决定 bounds
        _write_tile(tmp_path, 10, 815, 429)
        bad = tmp_path / "10" / "not-a-number"
        bad.mkdir(parents=True)
        (bad / "1.png").write_bytes(PNG)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 2
        assert stats["bounds"] == pytest.approx(_tile_bounds(10, 815, 429), abs=1e-6)

    def test_out_of_range_zoom_dir_skips_bounds(self, tmp_path):
        """z 超出 0..MAX_TILE_ZOOM：仍计数（既有行为），但不参与 bounds。"""
        for z in (23, 99):
            p = tmp_path / str(z) / "1" / "1.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(PNG)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 2
        assert stats["bounds"] is None

    def test_out_of_range_x_dir_skips_bounds(self, tmp_path):
        """x 越界（>= 2**z）：仍计数，但坐标不可用于 bounds。"""
        p = tmp_path / "5" / "99" / "1.png"  # z=5 时 x 合法范围 0..31
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 1
        assert stats["bounds"] is None

    def test_non_numeric_y_file_skips_bounds(self, tmp_path):
        p = tmp_path / "5" / "1" / "abc.png"
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 1
        assert stats["bounds"] is None

    def test_out_of_range_y_file_skips_bounds(self, tmp_path):
        p = tmp_path / "5" / "1" / "99.png"  # z=5 时 y 合法范围 0..31
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 1
        assert stats["bounds"] is None


# ==================== 单包：实测 bounds 覆盖包范围 ====================


class TestSinglePackageBbox:
    def test_single_package_bbox_matches_tiles(self, client, tmp_path):
        for tile in GUIYANG_TILES:
            _write_tile(tmp_path, *tile)
        # MANIFEST 自称"另一个包"（模拟多包叠加时 MANIFEST 是最后导入包）
        _write_manifest(tmp_path, [105.609, 27.14, 108.214, 29.221])
        data = _tile_info(client, tmp_path)
        assert data["available"] is True
        assert data["bbox"] == pytest.approx(GUIYANG_EXPECTED, abs=1e-6)


# ==================== 核心回归：多包叠加 → bbox 覆盖并集 ====================


class TestMultiPackageUnionBbox:
    def test_bbox_covers_both_packages_not_last_manifest(self, client, tmp_path):
        """先导贵阳、再导遵义（MANIFEST 只剩遵义）→ bbox 仍须覆盖贵阳+遵义并集。"""
        for tile in GUIYANG_TILES + ZUNYI_TILES:
            _write_tile(tmp_path, *tile)
        # 遵义包（最后导入）的 MANIFEST：region.bbox 仅覆盖遵义
        _write_manifest(
            tmp_path,
            [103.6, 24.6, 109.6, 29.2],
            region_bbox=[105.609, 27.14, 108.214, 29.221],
        )
        data = _tile_info(client, tmp_path)
        assert data["bbox"] == pytest.approx(UNION_EXPECTED, abs=1e-6)
        # 回归点：若仍取 MANIFEST region.bbox，贵阳瓦片（lat < 27.14）会被 maxBounds 挡住
        assert data["bbox"][1] < 27.14

    def test_bbox_not_shrunk_by_last_package_manifest(self, client, tmp_path):
        """叠加导入后省会等低纬瓦片（贵阳）仍落在 bbox 内（视野不被裁掉）。"""
        for tile in GUIYANG_TILES + ZUNYI_TILES:
            _write_tile(tmp_path, *tile)
        _write_manifest(
            tmp_path,
            [105.609, 27.14, 108.214, 29.221],
            region_bbox=[105.609, 27.14, 108.214, 29.221],
        )
        data = _tile_info(client, tmp_path)
        guiyang_box = _tile_bounds(*GUIYANG_TILES[0])
        assert data["bbox"][1] <= guiyang_box[1]
        assert data["bbox"][0] <= guiyang_box[0]


# ==================== MANIFEST 缺失/非法 → 实测 bounds ====================


class TestManifestFallback:
    def test_manifest_missing_uses_measured_bounds(self, client, tmp_path):
        for tile in ALL_TILES:
            _write_tile(tmp_path, *tile)
        data = _tile_info(client, tmp_path)
        assert data["manifest"] is None
        assert data["bbox"] == pytest.approx(UNION_EXPECTED, abs=1e-6)

    def test_manifest_invalid_json_uses_measured_bounds(self, client, tmp_path):
        for tile in ALL_TILES:
            _write_tile(tmp_path, *tile)
        (tmp_path / "MANIFEST.json").write_text("{broken", encoding="utf-8")
        data = _tile_info(client, tmp_path)
        assert data["manifest"] is None
        assert data["bbox"] == pytest.approx(UNION_EXPECTED, abs=1e-6)

    def test_manifest_used_only_when_bounds_unavailable(self, client, tmp_path):
        """无法从目录解析坐标时（非数字 x 目录）才回退 MANIFEST。"""
        bad = tmp_path / "10" / "not-a-number"
        bad.mkdir(parents=True)
        (bad / "1.png").write_bytes(PNG)
        manifest_bbox = [104.0, 25.0, 107.0, 27.0]
        _write_manifest(tmp_path, manifest_bbox, region_bbox=manifest_bbox)
        data = _tile_info(client, tmp_path)
        assert data["tileCount"] == 1
        assert data["bbox"] == manifest_bbox


# ==================== MANIFEST bbox/region 解析（bbox 回退链的输入校验） ====================


class TestManifestBboxParsing:
    """锁定 bbox 回退链所依赖的 MANIFEST 归一化分支（防脏数据透给 Leaflet）。"""

    def test_valid_bbox_returns_floats(self):
        from app.services import offline_map_service as oms

        assert oms._valid_bbox(["103.6", "24.6", 109.6, 29.2]) == [103.6, 24.6, 109.6, 29.2]

    def test_invalid_bbox_types_rejected(self):
        from app.services import offline_map_service as oms

        assert oms._valid_bbox(["bad", 1, 2, 3]) is None
        assert oms._valid_bbox([1, 2]) is None
        assert oms._valid_bbox("not-a-list") is None

    def test_non_finite_and_inverted_bbox_rejected(self):
        from app.services import offline_map_service as oms

        assert oms._valid_bbox([103.6, 24.6, float("inf"), 29.2]) is None
        # min_lon >= max_lon 或者 min_lat >= max_lat
        assert oms._valid_bbox([109.6, 24.6, 103.6, 29.2]) is None
        assert oms._valid_bbox([103.6, 29.2, 109.6, 24.6]) is None

    def test_region_normalized_whitelist(self):
        from app.services import offline_map_service as oms

        region = oms._normalize_region(
            {"name": " 贵阳 ", "bbox": [106.1, 26.1, 107.3, 27.4], "secret": "drop"}
        )
        assert region == {"name": "贵阳", "bbox": [106.1, 26.1, 107.3, 27.4]}
        # 空 name / 非法 bbox / 非法缩放列表：字段被丢弃而非抛错
        assert oms._normalize_region({"name": "   ", "bbox": "bad"}) is None
        assert oms._normalize_region({"name": "x", "overviewZooms": ["a"]}) == {"name": "x"}
        assert oms._normalize_region("not-a-dict") is None


# ==================== 无瓦片 / 目录缺失：保持现状 ====================


class TestEmptyStates:
    def test_no_tiles_province_bbox_and_reason(self, client, tmp_path):
        (tmp_path / "not-a-zoom").mkdir()
        data = _tile_info(client, tmp_path)
        assert data["available"] is False
        assert data["reason"] == "no_tiles"
        assert data["bbox"] == PROVINCE_BBOX

    def test_dir_missing_province_bbox_and_reason(self, client, tmp_path):
        data = _tile_info(client, tmp_path / "absent")
        assert data["reason"] == "dir_missing"
        assert data["bbox"] == PROVINCE_BBOX

    def test_existing_fields_not_regressed(self, client, tmp_path):
        for tile in GUIYANG_TILES:
            _write_tile(tmp_path, *tile)
        data = _tile_info(client, tmp_path)
        expected_keys = {
            "available", "tileCount", "zoomLevels", "totalBytes",
            "dir", "manifest", "source", "reason", "bbox",
        }
        assert expected_keys.issubset(data)
        assert data["tileCount"] == 2
        assert data["zoomLevels"] == [10]
        assert data["reason"] is None
        assert data["dir"] == tmp_path.name
