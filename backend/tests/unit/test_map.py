"""Tests for map.py — map visualization API."""
from unittest.mock import MagicMock, patch
import pytest

BASE = "/api/v1/map"


# ── Internal function tests ──────────────────────────────────────────

class TestGetCoords:
    def test_returns_exact_when_provided(self):
        from app.api.v1.map import _get_coords
        result = _get_coords(26.5, 107.5, "都匀市", 1, "test")
        assert result == (107.5, 26.5, False)

    def test_estimated_with_county_match(self):
        from app.api.v1.map import _get_coords
        result = _get_coords(None, None, "都匀市", 1, "test")
        lng, lat, estimated = result
        assert estimated is True
        assert 107.51 < lng < 107.53
        assert 26.25 < lat < 26.27

    def test_estimated_partial_match(self):
        from app.api.v1.map import _get_coords
        result = _get_coords(None, None, "都匀", 1, "test")
        lng, lat, estimated = result
        assert estimated is True

    def test_estimated_no_match_fallback(self):
        from app.api.v1.map import _get_coords
        result = _get_coords(None, None, "未知县", 1, "test")
        lng, lat, estimated = result
        assert estimated is True
        assert 107.45 < lng < 107.55
        assert 26.25 < lat < 26.35

    def test_deterministic_same_seed(self):
        from app.api.v1.map import _get_coords
        r1 = _get_coords(None, None, "荔波县", 42, "相同名称")
        r2 = _get_coords(None, None, "荔波县", 42, "相同名称")
        assert r1 == r2

    def test_deterministic_different_seed(self):
        from app.api.v1.map import _get_coords
        r1 = _get_coords(None, None, "荔波县", 1, "a")
        r2 = _get_coords(None, None, "荔波县", 2, "b")
        assert r1 != r2  # different seed → different offset

    def test_exact_lat_only(self):
        from app.api.v1.map import _get_coords
        result = _get_coords(26.5, None, "福泉市", 1, "test")
        lng, lat, estimated = result
        assert estimated is True
        # lat=None means fallback to 福泉市 center (26.6868) ± 0.008 offset
        assert 26.678 < lat < 26.695
        assert 107.505 < lng < 107.522


class TestHaversine:
    def test_zero_distance(self):
        from app.api.v1.map import _haversine
        d = _haversine(107.5, 26.3, 107.5, 26.3)
        assert d == 0.0

    def test_known_distance(self):
        from app.api.v1.map import _haversine
        d = _haversine(107.5, 26.3, 108.0, 26.3)
        assert 45 < d < 55  # ~49km at this latitude

    def test_symmetry(self):
        from app.api.v1.map import _haversine
        d1 = _haversine(107.0, 26.0, 108.0, 27.0)
        d2 = _haversine(108.0, 27.0, 107.0, 26.0)
        assert abs(d1 - d2) < 0.001

    def test_large_distance(self):
        from app.api.v1.map import _haversine
        d = _haversine(0, 0, 180, 0)
        assert 20000 < d < 21000  # half circumference ~20015km


class TestEstimateTravel:
    def test_under_one_hour(self):
        from app.api.v1.map import _estimate_travel
        road_km, hours, display = _estimate_travel(10)
        assert road_km == 14.0
        assert "min" in display
        assert "h" not in display

    def test_over_one_hour(self):
        from app.api.v1.map import _estimate_travel
        road_km, hours, display = _estimate_travel(80)
        assert road_km == 112.0
        assert "h" in display

    def test_zero_distance(self):
        from app.api.v1.map import _estimate_travel
        road_km, hours, display = _estimate_travel(0)
        assert road_km == 0.0
        assert hours == 0.0
        assert "0min" in display

    def test_road_factor_14(self):
        from app.api.v1.map import _estimate_travel
        road_km, _, _ = _estimate_travel(100)
        assert road_km == 140.0


class TestInvalidateMapCache:
    def test_cache_cleared_when_available(self):
        with patch("app.api.v1.map._map_cache") as mock_cache:
            from app.api.v1.map import invalidate_map_cache
            invalidate_map_cache()
            mock_cache.clear.assert_called_once()

    def test_cache_none_does_not_crash(self):
        from app.api.v1.map import invalidate_map_cache
        with patch("app.api.v1.map._map_cache", None):
            invalidate_map_cache()  # should not raise


# ── API endpoint tests ───────────────────────────────────────────────

class TestGetMapConfig:
    def test_requires_auth(self, client):
        """地图配置接口需要认证"""
        resp = client.get(f"{BASE}/config")
        assert resp.status_code == 401

    def test_success_with_auth(self, client_with_mocked_auth):
        """认证后可获取地图配置"""
        resp = client_with_mocked_auth.get(f"{BASE}/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data


class TestGetMapMarkers:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/markers")
        assert resp.status_code == 401

    def test_all_marker_types(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/markers")
        assert resp.status_code == 200
        data = resp.json()
        assert "villages" in data
        assert "schools" in data

    def test_villages_only(self, client_with_mocked_auth):
        # 管理员用户经真实 get_org_scope 依赖获得 is_admin 全量数据权限，
        # 直接走测试库即可（与 test_all_marker_types 一致）
        resp = client_with_mocked_auth.get(f"{BASE}/markers", params={"marker_type": "villages"})
        assert resp.status_code == 200
        data = resp.json()
        assert "villages" in data
        assert "schools" not in data

    def test_schools_only(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/markers", params={"marker_type": "schools"})
        assert resp.status_code == 200
        data = resp.json()
        assert "schools" in data
        assert "villages" not in data


class TestGetCountyCoordinates:
    def test_success(self, client):
        resp = client.get(f"{BASE}/county-coords")
        assert resp.status_code == 200
        data = resp.json()
        assert "center" in data
        assert "counties" in data
        assert "都匀市" in data["counties"]
        assert "都匀" not in data["counties"]  # should only contain full names with 县/市


class TestGetRegions:
    def test_success_without_auth(self, client):
        """行政区划接口无需认证，直接返回数据"""
        resp = client.get(f"{BASE}/regions")
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data or "items" in data or isinstance(data, list)


class TestUpdateMarkerCoordinates:
    def test_requires_auth(self, client):
        resp = client.put(f"{BASE}/markers/village/1/coordinates", json={"latitude": 26.5, "longitude": 107.5})
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.put(
            f"{BASE}/markers/village/1/coordinates", json={"latitude": 26.5, "longitude": 107.5}
        )
        assert resp.status_code == 403

    def test_invalid_coordinates(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.put(
            f"{BASE}/markers/village/1/coordinates", json={"latitude": 200, "longitude": 107.5}
        )
        assert resp.status_code == 400

    def test_village_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.map.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            resp = client_with_mocked_auth.put(
                f"{BASE}/markers/village/999/coordinates", json={"latitude": 26.5, "longitude": 107.5}
            )
            assert resp.status_code == 404

    def test_school_not_found(self, client_with_mocked_auth):
        from app.models.school import School
        mock_db = MagicMock()
        def query_side(model):
            q = MagicMock()
            f = MagicMock()
            f.first.return_value = None
            q.filter.return_value = f
            return q
        mock_db.query.side_effect = query_side

        with patch("app.api.v1.map.get_db") as mock_get_db:
            mock_get_db.return_value = mock_db
            resp = client_with_mocked_auth.put(
                f"{BASE}/markers/school/999/coordinates", json={"latitude": 26.5, "longitude": 107.5}
            )
            assert resp.status_code == 404

    def test_invalid_marker_type(self, client_with_mocked_auth):
        with patch("app.api.v1.map.get_db") as mock_get_db:
            mock_get_db.return_value = MagicMock()
            resp = client_with_mocked_auth.put(
                f"{BASE}/markers/invalid/1/coordinates", json={"latitude": 26.5, "longitude": 107.5}
            )
            assert resp.status_code == 400

    def test_village_success(self, client_with_mocked_auth):
        from app.core.database import get_db

        mock_village = MagicMock()
        mock_village.id = 1

        db_query = MagicMock()
        db_filter = MagicMock()
        db_filter.first.return_value = mock_village
        db_query.filter.return_value = db_filter

        mock_db = MagicMock()
        mock_db.query.return_value = db_query

        original_override = client_with_mocked_auth.app.dependency_overrides.get(get_db)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.v1.map._map_cache", None):
                resp = client_with_mocked_auth.put(
                    f"{BASE}/markers/village/1/coordinates", json={"latitude": 26.5, "longitude": 107.5}
                )
                assert resp.status_code == 200
                assert resp.json()["success"] is True
                assert mock_village.latitude == 26.5
                assert mock_village.longitude == 107.5
                # safe_commit + write_work_log 可能导致多次 commit
                assert mock_db.commit.call_count >= 1
        finally:
            if original_override:
                client_with_mocked_auth.app.dependency_overrides[get_db] = original_override
            else:
                del client_with_mocked_auth.app.dependency_overrides[get_db]

    def test_school_success(self, client_with_mocked_auth):
        from app.core.database import get_db

        mock_school = MagicMock()
        mock_school.id = 1

        from app.models.school import School
        db_query = MagicMock()
        db_filter = MagicMock()
        db_filter.first.return_value = mock_school
        db_query.filter.return_value = db_filter

        mock_db = MagicMock()
        mock_db.query.return_value = db_query

        original_override = client_with_mocked_auth.app.dependency_overrides.get(get_db)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("app.api.v1.map._map_cache", None):
                resp = client_with_mocked_auth.put(
                    f"{BASE}/markers/school/1/coordinates", json={"latitude": 26.5, "longitude": 107.5}
                )
                assert resp.status_code == 200
                assert mock_school.latitude == 26.5
        finally:
            if original_override:
                client_with_mocked_auth.app.dependency_overrides[get_db] = original_override
            else:
                del client_with_mocked_auth.app.dependency_overrides[get_db]


class TestGetDistances:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/distances")
        assert resp.status_code == 401

    def test_success_with_cache(self, client_with_mocked_auth):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"cached": True}
        mock_cache.set.return_value = None

        # 缓存命中时端点直接返回缓存内容，不会触达数据库/数据权限
        with patch("app.api.v1.map._map_cache", mock_cache):
            resp = client_with_mocked_auth.get(f"{BASE}/distances")
            assert resp.status_code == 200
            assert resp.json()["cached"] is True

    def test_success_no_cache(self, client_with_mocked_auth):
        # _map_cache=None 时走真实测试库（空表），返回完整结构
        with patch("app.api.v1.map._map_cache", None):
            resp = client_with_mocked_auth.get(f"{BASE}/distances")
            assert resp.status_code == 200
            data = resp.json()
            assert "base" in data
            assert "villages" in data
            assert "schools" in data
            assert "county_distances" in data
            # county_distances should only include full names
            county_names = [c["county"] for c in data["county_distances"]]
            assert "都匀市" in county_names
            assert "都匀" not in county_names


class TestGetTileInfo:
    def test_tiles_not_available(self, client):
        with patch("app.api.v1.map.TILES_DIR") as mock_dir:
            mock_dir.exists.return_value = False
            resp = client.get(f"{BASE}/tile-info")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is False

    def test_tiles_available(self, client):
        with patch("app.api.v1.map.TILES_DIR") as mock_dir:
            mock_dir.exists.return_value = True
            mock_dir.iterdir.return_value = []
            mock_dir.rglob.return_value = []
            resp = client.get(f"{BASE}/tile-info")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is False


class TestServeTile:
    def test_tile_found(self, client):
        import tempfile
        from pathlib import Path as _Path
        tmp = tempfile.mkdtemp()
        tiles_path = _Path(tmp)
        (tiles_path / "10" / "512").mkdir(parents=True)
        (tiles_path / "10" / "512" / "256.png").write_text("fake-png")
        with patch("app.api.v1.map.TILES_DIR", tiles_path):
            resp = client.get(f"{BASE}/tiles/10/512/256.png")
            assert resp.status_code == 200

    def test_tile_not_found(self, client):
        import tempfile
        from pathlib import Path as _Path
        tmp = tempfile.mkdtemp()
        tiles_path = _Path(tmp)
        (tiles_path / "10" / "512").mkdir(parents=True)
        (tiles_path / "10" / "512" / "256.png").write_text("fake-png")
        with patch("app.api.v1.map.TILES_DIR", tiles_path):
            resp = client.get(f"{BASE}/tiles/10/512/999.png")
            assert resp.status_code == 404

    def test_path_traversal_blocked(self, client):
        """Simulate a resolved path outside TILES_DIR via mock."""
        from pathlib import Path as _Path
        mock_tiles = MagicMock()
        mock_tiles.resolve.return_value = _Path("C:\\safe\\tiles")

        level1 = MagicMock()
        level2 = MagicMock()
        tile_path = MagicMock()
        tile_path.resolve.return_value = _Path("C:\\outside\\evil.png")
        tile_path.is_file.return_value = True
        mock_tiles.__truediv__.return_value = level1
        level1.__truediv__.return_value = level2
        level2.__truediv__.return_value = tile_path

        with patch("app.api.v1.map.TILES_DIR", mock_tiles):
            resp = client.get(f"{BASE}/tiles/1/2/3.png")
            assert resp.status_code == 400
