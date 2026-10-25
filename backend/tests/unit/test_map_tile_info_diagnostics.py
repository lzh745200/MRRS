"""`/api/v1/map/tile-info` 诊断字段回归（2026-10-25 瓦片底图回退问题的排障支撑）。

覆盖：
- 目录不存在 → ``reason="dir_missing"`` + 默认贵州 bbox；
- 目录存在但无瓦片 → ``reason="no_tiles"``；
- 可用时 → ``reason=None``，``bbox`` 优先取**扫描实测 bounds**（多包并集），
  坐标不可解析时才回退 MANIFEST 的 ``region.bbox`` / 顶层 ``bbox``，最后回退贵州全省 bbox；
- ``source`` 反映瓦片目录解析来源（env / meipass / dev）；
- 原有字段（available/tileCount/zoomLevels/totalBytes/dir/manifest）不回归。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

import app.api.v1.map as map_mod

BASE = "/api/v1/map"
PROVINCE_BBOX = [103.6, 24.6, 109.6, 29.2]
PNG = b"\x89PNG\r\n\x1a\n" + b"tile"


def _tile_bounds(z: int, x: int, y: int):
    """XYZ 瓦片经纬度包围盒 ``[min_lon, min_lat, max_lon, max_lat]``。"""
    n = float(1 << z)
    return [
        x / n * 360.0 - 180.0,
        math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))),
        (x + 1) / n * 360.0 - 180.0,
        math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))),
    ]


def _write_tiles(root: Path, zooms=(5,), count_per_zoom=1) -> None:
    for z in zooms:
        for y in range(count_per_zoom):
            p = root / str(z) / "25" / f"{13 + y}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(PNG)


class TestTileInfoDiagnostics:
    def test_dir_missing_reports_reason_and_default_bbox(self, client, tmp_path):
        absent = tmp_path / "absent"
        with patch.object(map_mod, "TILES_DIR", absent):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["available"] is False
        assert data["reason"] == "dir_missing"
        assert data["bbox"] == PROVINCE_BBOX
        assert data["source"] in {"env", "meipass", "dev"}

    def test_dir_without_tiles_reports_no_tiles(self, client, tmp_path):
        (tmp_path / "not-a-zoom").mkdir()
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["available"] is False
        assert data["reason"] == "no_tiles"
        assert data["bbox"] == PROVINCE_BBOX

    def test_available_uses_measured_bounds_when_no_manifest(self, client, tmp_path):
        _write_tiles(tmp_path, zooms=(5,), count_per_zoom=2)
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["available"] is True
        assert data["reason"] is None
        assert data["manifest"] is None
        expected = _tile_bounds(5, 25, 13)
        expected[1] = _tile_bounds(5, 25, 14)[1]  # 两瓦片纵向并集
        assert data["bbox"] == pytest.approx(expected, abs=1e-6)
        assert data["tileCount"] == 2
        assert data["zoomLevels"] == [5]

    def test_measured_bounds_take_priority_over_manifest_region(self, client, tmp_path):
        """新优先级：实测 bounds 优先于 MANIFEST.region.bbox（多包叠加回归）。"""
        _write_tiles(tmp_path)
        manifest_bbox = [106.0, 25.1, 108.5, 26.9]
        manifest = {
            "schemaVersion": 1,
            "provider": "osm-qiannan",
            "tileCount": 1,
            "zoomLevels": [5],
            "zoom": {"min": 5, "max": 5},
            "bbox": [103.6, 24.6, 109.6, 29.2],
            "region": {"name": "黔南", "bbox": manifest_bbox},
        }
        (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["available"] is True
        assert data["bbox"] == pytest.approx(_tile_bounds(5, 25, 13), abs=1e-6)
        assert data["bbox"] != manifest_bbox

    def test_manifest_bbox_used_when_bounds_unavailable(self, client, tmp_path):
        """坐标目录不可解析（无实测 bounds）时才回退 MANIFEST bbox。"""
        bad = tmp_path / "5" / "not-a-number"
        bad.mkdir(parents=True)
        (bad / "13.png").write_bytes(PNG)
        bbox = [104.0, 25.0, 107.0, 27.0]
        manifest = {"schemaVersion": 1, "provider": "osm", "tileCount": 1, "bbox": bbox}
        (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["bbox"] == bbox

    def test_invalid_manifest_bbox_falls_back_to_province(self, client, tmp_path):
        # 坐标不可解析 → 无实测 bounds；MANIFEST bbox 非法 → 回退贵州全省
        bad = tmp_path / "5" / "not-a-number"
        bad.mkdir(parents=True)
        (bad / "13.png").write_bytes(PNG)
        manifest = {"schemaVersion": 1, "provider": "osm", "bbox": ["bad", 1]}
        (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["bbox"] == PROVINCE_BBOX

    @pytest.mark.parametrize("source", ["env", "meipass", "dev"])
    def test_source_is_reported(self, client, tmp_path, source):
        _write_tiles(tmp_path)
        with patch.object(map_mod, "TILES_DIR", tmp_path), patch.object(
            map_mod, "_TILES_DIR_SOURCE", source
        ):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["source"] == source

    def test_dir_still_public_name_only(self, client, tmp_path):
        """安全口径不回归：只回显目录名，不泄露完整磁盘路径。"""
        store = tmp_path / "map-tiles"
        _write_tiles(store)
        with patch.object(map_mod, "TILES_DIR", store):
            data = client.get(f"{BASE}/tile-info").json()["data"]
        assert data["dir"] == "map-tiles"
        assert "\\" not in data["dir"] and "/" not in data["dir"]


class TestTileServeUnaffected:
    def test_missing_tile_still_404(self, client, tmp_path):
        store = tmp_path / "map-tiles"
        store.mkdir()
        with patch.object(map_mod, "TILES_DIR", store):
            resp = client.get(f"{BASE}/tiles/12/1/1.png")
        assert resp.status_code == 404

    def test_existing_tile_served(self, client, tmp_path):
        store = tmp_path / "map-tiles"
        p = store / "12" / "1" / "1.png"
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        with patch.object(map_mod, "TILES_DIR", store):
            resp = client.get(f"{BASE}/tiles/12/1/1.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"


class TestManifestBboxHelper:
    """_manifest_bbox 纯函数分支：region.bbox 优先 / 顶层 bbox 回退 / 全非法返回 None。"""

    def test_region_bbox_preferred(self):
        from app.api.v1.map import _manifest_bbox

        assert _manifest_bbox({"region": {"bbox": [1.0, 2.0, 3.0, 4.0]}, "bbox": [9, 9, 9, 9]}) == [1.0, 2.0, 3.0, 4.0]

    def test_region_bbox_invalid_falls_back_to_top_level(self):
        """region.bbox 长度不对 → 继续看顶层 bbox（分支 182->184）。"""
        from app.api.v1.map import _manifest_bbox

        assert _manifest_bbox({"region": {"bbox": [1, 2]}, "bbox": [5.0, 6.0, 7.0, 8.0]}) == [5.0, 6.0, 7.0, 8.0]

    def test_top_level_bbox_invalid_returns_none(self):
        """两级 bbox 都不合法 → None（分支 185->187）。"""
        from app.api.v1.map import _manifest_bbox

        assert _manifest_bbox({"region": {"bbox": "oops"}, "bbox": ["x", 1, 2, 3]}) is None

    def test_non_dict_manifest_returns_none(self):
        from app.api.v1.map import _manifest_bbox

        assert _manifest_bbox(None) is None
        assert _manifest_bbox([1, 2, 3, 4]) is None

    def test_tuple_bbox_converted_to_list(self):
        from app.api.v1.map import _manifest_bbox

        assert _manifest_bbox({"bbox": (1, 2, 3, 4)}) == [1, 2, 3, 4]
