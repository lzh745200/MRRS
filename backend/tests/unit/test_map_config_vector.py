"""``/api/v1/map/config`` 必须如实报告「矢量离线地图」而不是高德在线底图。

背景（离线适配审计 A8 关联）：系统实际渲染 `components/map/OfflineMap.vue` 的
ECharts 离线矢量地图，前端无任何 `map_type` 消费方；对外声明 `gaode` 属误导字段。
"""

BASE = "/api/v1/map"


class TestMapConfigReportsVector:
    def test_map_type_is_vector(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/config")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["map_type"] == "vector"

    def test_gaode_is_never_advertised(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/config")

        assert "gaode" not in resp.text.lower()

    def test_other_fields_preserved(self, client_with_mocked_auth):
        """仅改 map_type，其余字段（中心点/缩放/离线开关/瓦片地址）保持不变。"""
        data = client_with_mocked_auth.get(f"{BASE}/config").json()["data"]

        assert data["zoom"] == 9
        assert data["offline_enabled"] is True
        assert data["tiles_url"] == "/api/v1/map/tiles"
        assert isinstance(data["center"]["lng"], (int, float))
        assert isinstance(data["center"]["lat"], (int, float))
