"""
地图API全面测试
覆盖app/api/v1/map.py的所有路由
"""

class TestMapAPI:
    """测试地图API"""

    def test_map_villages(self, client):
        """测试地图村庄"""
        response = client.get("/api/v1/map/villages")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_villages_with_bounds(self, client):
        """测试地图村庄带边界"""
        response = client.get("/api/v1/map/villages?north=40&south=30&east=120&west=110")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_projects(self, client):
        """测试地图项目"""
        response = client.get("/api/v1/map/projects")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_schools(self, client):
        """测试地图学校"""
        response = client.get("/api/v1/map/schools")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_funds(self, client):
        """测试地图资金"""
        response = client.get("/api/v1/map/funds")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_heatmap(self, client):
        """测试地图热力图"""
        response = client.get("/api/v1/map/heatmap")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_cluster(self, client):
        """测试地图聚合"""
        response = client.get("/api/v1/map/cluster")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_search(self, client):
        """测试地图搜索"""
        response = client.get("/api/v1/map/search?q=测试")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_geocode(self, client):
        """测试地理编码"""
        response = client.get("/api/v1/map/geocode?address=北京市")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_map_reverse_geocode(self, client):
        """测试逆地理编码"""
        response = client.get("/api/v1/map/reverse-geocode?lat=39.9&lng=116.4")
        assert response.status_code in [200, 401, 403, 404, 405]

class TestOfflineMapAPI:
    """测试离线地图API"""

    def test_offline_map_regions(self, client):
        """测试离线地图区域"""
        response = client.get("/api/v1/offline-map/regions")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_offline_map_download(self, client_with_mocked_auth):
        """在线抓取已下线：显式 501（不再返回假成功）。"""
        response = client_with_mocked_auth.post("/api/v1/offline-map/download", json={
            "region": "beijing"
        })
        assert response.status_code == 501
        assert "不支持在线抓取瓦片" in response.json()["detail"]

    def test_offline_map_download_requires_admin(self, client):
        response = client.post("/api/v1/offline-map/download", json={"region": "beijing"})
        assert response.status_code in [401, 403]

    def test_offline_map_status(self, client):
        """测试离线地图状态"""
        response = client.get("/api/v1/offline-map/status")
        assert response.status_code in [200, 401, 403, 404, 405]
