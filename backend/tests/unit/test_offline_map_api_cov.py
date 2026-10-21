"""app.api.v1.offline_map 覆盖率攻坚测试

覆盖 4 个端点全部分支：
- GET /tiles/{z}/{x}/{y}：缩放非法400 / 命中200 / 未命中404 / 服务异常
- GET /status：真实瓦片目录统计 / 异常
- POST /download：在线抓取已下线 → 显式 501（管理员）
- DELETE /clear：成功 / 异常（管理员）
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_active_user

BASE = "/api/v1/offline-map"


@pytest.fixture
def client(tmp_path):
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=1, username="admin", role="admin", is_superuser=True
    )
    svc = MagicMock()
    svc.get_tile = AsyncMock(return_value=b"\x89PNG-tile")
    svc.get_coverage = AsyncMock(return_value={"tiles": 100})
    with patch("app.api.v1.offline_map.offline_map_service", svc), patch(
        "app.api.v1.offline_map.TILES_DIR", tmp_path / "tiles-store"
    ):
        yield TestClient(app, raise_server_exceptions=False), svc
    app.dependency_overrides = original


class TestGetTile:
    def test_zoom_too_low_400(self, client):
        c, _ = client
        assert c.get(f"{BASE}/tiles/-1/0/0").status_code == 400

    def test_zoom_too_high_400(self, client):
        c, _ = client
        assert c.get(f"{BASE}/tiles/19/0/0").status_code == 400

    def test_tile_found_200(self, client):
        c, _ = client
        resp = c.get(f"{BASE}/tiles/10/1/2")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert "max-age=86400" in resp.headers["cache-control"]
        assert resp.content == b"\x89PNG-tile"

    def test_tile_not_found_404(self, client):
        c, svc = client
        svc.get_tile = AsyncMock(return_value=None)
        assert c.get(f"{BASE}/tiles/10/1/2").status_code == 404

    def test_tile_service_error(self, client):
        c, svc = client
        svc.get_tile = AsyncMock(side_effect=RuntimeError("io fail"))
        resp = c.get(f"{BASE}/tiles/10/1/2")
        assert resp.status_code in (400, 500)
        assert "获取地图瓦片失败" in resp.text


class TestGetStatus:
    def test_status_success(self, client):
        c, _ = client
        resp = c.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 瓦片仓目录不存在 → 计数为零；历史缓存覆盖仍原样透传
        assert data["available"] is False
        assert data["tileCount"] == 0
        assert data["downloadSupported"] is False
        assert data["cache"]["tiles"] == 100

    def test_status_error(self, client):
        c, svc = client
        svc.get_coverage = AsyncMock(side_effect=RuntimeError("x"))
        resp = c.get(f"{BASE}/status")
        assert resp.status_code in (400, 500)
        assert "获取离线地图状态失败" in resp.text


class TestDownloadTiles:
    def test_download_returns_501(self, client):
        c, _ = client
        resp = c.post(
            f"{BASE}/download",
            params={
                "min_lat": 30.0,
                "max_lat": 31.0,
                "min_lon": 120.0,
                "max_lon": 121.0,
                "min_zoom": 4,
                "max_zoom": 12,
            },
        )
        assert resp.status_code == 501
        assert "不支持在线抓取瓦片" in resp.json()["detail"]

    def test_download_params_ignored_still_501(self, client):
        """参数不再校验：一律显式失败，避免前端误以为有抓取能力。"""
        c, _ = client
        assert c.post(f"{BASE}/download").status_code == 501


class TestClearTiles:
    def test_clear_success(self, client):
        c, _ = client
        resp = c.delete(f"{BASE}/clear")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_clear_error(self, client):
        c, svc = client
        svc.clear_cache.side_effect = RuntimeError("locked")
        resp = c.delete(f"{BASE}/clear")
        assert resp.status_code in (400, 500)
        assert "清理瓦片缓存失败" in resp.text
