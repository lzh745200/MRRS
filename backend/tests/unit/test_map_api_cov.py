"""app.api.v1.map 覆盖率攻坚测试（补充 test_map.py 未覆盖分支）

覆盖点：
- _resolve_tiles_dir：_MEIPASS/env/默认三分支
- /map/search：村+校数据行映射、按类型过滤
- /map/regions：level/parent_code 过滤 + geometry 解析
- /map/distances：真实数据行循环、排序、缓存命中/读写异常
- /map/markers：村/校数据行字段映射
- /map/tile-info：目录存在但无缩放级别
- /map/tiles/{z}/{x}/{y}.png：resolve OSError → 400
- PUT 坐标更新：缓存清理异常降级
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.map as map_mod
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.unified_data_scope import get_org_scope

BASE = "/api/v1/map"


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "limit", "offset", "group_by"):
        getattr(q, attr).return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db_with(queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


@pytest.fixture
def map_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    scope = MagicMock()
    scope.has_full_access = MagicMock(return_value=True)
    scope.filter_by_org_ids = MagicMock(side_effect=lambda q, *a, **k: q)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="admin", role="admin"
    )
    app.dependency_overrides[get_org_scope] = lambda: scope
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _use_db(client, db):
    client.app.dependency_overrides[get_db] = lambda: db


def _village(**kw):
    defaults = dict(
        id=1, village_name="幸福村", latitude=None, longitude=None, county="都匀市",
        department="某部", support_unit="某单位", region_scope="区内",
        is_three_regions=False, is_key_county=True, is_border_area=False,
        is_provincial_demo=False, is_hundred_village_demo=False, is_revitalization_tier=1,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _school(**kw):
    defaults = dict(
        id=2, name="希望小学", latitude=26.2, longitude=107.5, district="都匀",
        type=SimpleNamespace(value="小学"), support_status=SimpleNamespace(value="active"),
        support_unit="某单位", student_count=300, teacher_count=20,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ==================== _resolve_tiles_dir ====================


class TestResolveTilesDir:
    def test_meipass_branch(self, monkeypatch, tmp_path):
        tiles = tmp_path / "resources" / "map-tiles"
        tiles.mkdir(parents=True)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert map_mod._resolve_tiles_dir() == tiles

    def test_meipass_missing_falls_to_env(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "nope"), raising=False)
        monkeypatch.setenv("MAP_TILES_DIR", str(tmp_path))
        assert map_mod._resolve_tiles_dir() == tmp_path

    def test_default_dev_path(self, monkeypatch):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.delenv("MAP_TILES_DIR", raising=False)
        result = map_mod._resolve_tiles_dir()
        assert result.name == "map-tiles"
        assert result.parent.name == "resources"


# ==================== /map/search ====================


class TestSearchMarkers:
    def test_search_all_with_data(self, map_client):
        _use_db(map_client, _db_with([_q(all=[_village()]), _q(all=[_school()])]))
        resp = map_client.get(f"{BASE}/search?q=幸福")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        v = data["villages"][0]
        assert v["name"] == "幸福村"
        assert v["type"] == "village"
        assert isinstance(v["lng"], float)
        s = data["schools"][0]
        assert s["name"] == "希望小学"
        assert s["lng"] == 107.5  # 真实坐标原样返回

    def test_search_villages_only(self, map_client):
        _use_db(map_client, _db_with([_q(all=[_village()])]))
        resp = map_client.get(f"{BASE}/search?q=幸福&marker_type=villages")
        data = resp.json()
        assert data["total"] == 1
        assert data["schools"] == []

    def test_search_schools_only(self, map_client):
        _use_db(map_client, _db_with([_q(all=[_school()])]))
        resp = map_client.get(f"{BASE}/search?q=希望&marker_type=schools")
        data = resp.json()
        assert data["total"] == 1
        assert data["villages"] == []


# ==================== /map/regions 过滤 ====================


class TestRegionsFiltered:
    def test_with_filters_and_geometry(self, map_client):
        region = SimpleNamespace(
            code="522701", name="都匀市", level="county", parent_code="522700",
            center_lng=107.5, center_lat=26.26, geometry_text='{"type": "Polygon"}',
        )
        _use_db(map_client, _db_with([_q(all=[region])]))
        resp = map_client.get(f"{BASE}/regions?level=county&parent_code=522700")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]["items"]
        assert body["data"]["total"] == 1
        assert items[0]["geometry"] == {"type": "Polygon"}
        assert items[0]["parentCode"] == "522700"


# ==================== /map/markers 数据行 ====================


class TestMarkersWithData:
    def test_village_and_school_rows(self, map_client):
        _use_db(map_client, _db_with([_q(all=[_village()]), _q(all=[_school()])]))
        resp = map_client.get(f"{BASE}/markers")
        assert resp.status_code == 200
        data = resp.json()
        v = data["villages"][0]
        assert v["isEstimated"] is True  # 无坐标 → 估算
        assert v["isKeyCounty"] is True
        s = data["schools"][0]
        assert s["isEstimated"] is False
        assert s["type"] == "小学"
        assert s["supportStatus"] == "active"
        assert s["studentCount"] == 300

    def test_school_enum_none_fallback(self, map_client):
        s = _school(type=None, support_status=None)
        # marker_type=schools 时只执行学校查询（源码 line 227）
        _use_db(map_client, _db_with([_q(all=[s])]))
        resp = map_client.get(f"{BASE}/markers?marker_type=schools")
        item = resp.json()["schools"][0]
        assert item["type"] is None
        assert item["supportStatus"] is None


# ==================== /map/distances 数据行与缓存分支 ====================


class TestDistancesBranches:
    def test_with_data_sorted(self, map_client):
        v_far = _village(id=1, village_name="远村", latitude=27.08, longitude=107.47, county="瓮安县")
        v_near = _village(id=2, village_name="近村", latitude=26.26, longitude=107.51, county="都匀市")
        _use_db(map_client, _db_with([_q(all=[v_far, v_near]), _q(all=[_school()])]))
        with patch.object(map_mod, "_map_cache", None):
            resp = map_client.get(f"{BASE}/distances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["base"]["name"] == "区域中心"
        # 按距离排序：近村在前
        assert [v["name"] for v in data["villages"]] == ["近村", "远村"]
        assert data["villages"][0]["road_distance_km"] > data["villages"][0]["distance_km"]
        assert data["schools"][0]["travel_display"]
        assert len(data["county_distances"]) == 13  # 13 个县市全称（简称已过滤）
        assert data["county_distances"][0]["county"] == "都匀市"  # 区域中心所在地最近

    def test_cache_hit(self, map_client):
        mc = MagicMock()
        mc.get.return_value = {"cached": True}
        with patch.object(map_mod, "_map_cache", mc):
            resp = map_client.get(f"{BASE}/distances")
        assert resp.json() == {"cached": True}

    def test_cache_read_write_exception_degrades(self, map_client):
        mc = MagicMock()
        mc.get.side_effect = Exception("read boom")
        mc.set.side_effect = Exception("write boom")
        _use_db(map_client, _db_with([_q(all=[]), _q(all=[])]))
        with patch.object(map_mod, "_map_cache", mc):
            resp = map_client.get(f"{BASE}/distances")
        assert resp.status_code == 200
        assert resp.json()["villages"] == []


# ==================== /map/tile-info 与瓦片服务分支 ====================


class TestTileBranches:
    def test_tile_info_dir_without_zoom_levels(self, map_client, tmp_path):
        (tmp_path / "not-a-zoom").mkdir()
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            resp = map_client.get(f"{BASE}/tile-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["zoomLevels"] == []

    def test_serve_tile_resolve_oserror_400(self, map_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path), patch.object(
            Path, "resolve", side_effect=OSError("bad path")
        ):
            resp = map_client.get(f"{BASE}/tiles/10/512/256.png")
        assert resp.status_code == 400


# ==================== PUT 坐标更新：缓存清理异常 ====================


class TestUpdateCoordsCacheBranch:
    def test_cache_clear_exception_degrades(self, map_client):
        record = _village()
        _use_db(map_client, _db_with([_q(first=record)]))
        mc = MagicMock()
        mc.clear.side_effect = Exception("clear boom")
        with patch.object(map_mod, "safe_commit"), patch.object(map_mod, "_map_cache", mc):
            resp = map_client.put(
                f"{BASE}/markers/village/1/coordinates",
                json={"latitude": 26.5, "longitude": 107.5},
            )
        assert resp.status_code == 200
        assert record.latitude == 26.5


# ==================== 模块级 diskcache 初始化分支（47-59） ====================


class TestCacheInitBranches:
    def test_import_error_disables_cache(self, monkeypatch):
        import importlib

        monkeypatch.setitem(sys.modules, "diskcache", None)
        importlib.reload(map_mod)
        try:
            assert map_mod._map_cache is None
        finally:
            monkeypatch.undo()
            importlib.reload(map_mod)

    def test_init_exception_cleans_bad_dir(self, monkeypatch):
        import importlib

        monkeypatch.setattr(map_mod._dc, "Cache", MagicMock(side_effect=RuntimeError("corrupt")))
        monkeypatch.setattr("shutil.rmtree", MagicMock(side_effect=OSError("locked")))
        importlib.reload(map_mod)
        try:
            assert map_mod._map_cache is None
        finally:
            monkeypatch.undo()
            importlib.reload(map_mod)


# ==================== _get_coords 模糊匹配分支（150-152） ====================


class TestGetCoordsFuzzy:
    def test_substring_match(self):
        lng, lat, estimated = map_mod._get_coords(None, None, "贵州省瓮安县", record_id=7, name="某村")
        assert estimated is True
        # 落在瓮安县基准坐标 ±0.008 范围内
        assert abs(lng - 107.4716) <= 0.008
        assert abs(lat - 27.0785) <= 0.008


# ==================== /map/tile-info 有缩放级别（596-597） ====================


class TestTileInfoWithZoom:
    def test_zoom_levels_and_png_count(self, map_client):
        fake_dir = MagicMock()
        zoom = MagicMock()
        zoom.is_dir.return_value = True
        zoom.name = "12"
        other = MagicMock()
        other.is_dir.return_value = False
        other.name = "readme.txt"
        fake_dir.iterdir.return_value = [zoom, other]
        fake_dir.rglob.return_value = iter(["a.png", "b.png", "c.png"])
        with patch.object(map_mod, "TILES_DIR", fake_dir):
            resp = map_client.get(f"{BASE}/tile-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["tileCount"] == 3
        assert data["zoomLevels"] == [12]
        assert data["minZoom"] == 12
        assert data["maxZoom"] == 12
