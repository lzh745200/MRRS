"""覆盖 data/data/statistics.py 的 overview / villages/distribution / dashboard 端点。

此前这些端点无任何测试真实调用（test_api_data_statistics_full.py 用带 /data
前缀的错误路径 + 宽容断言，实际全部 404）。2026-08 迁移 SupportedVillage 后，
overview 的 villages_count/distribution 错表、dashboard 的 total_villages 错表、
以及新增的 filing_rates/users 字段均无覆盖，导致覆盖率余量收缩。

用内存 SQLite + auth_client（admin Mock user）真实调用正确路径，空库即可覆盖
各分支（count=0 / 空列表 / filing_rates 兜底值）。
"""


class TestStatisticsOverviewCov:
    def test_overview(self, auth_client):
        resp = auth_client.get("/api/v1/statistics/overview")
        assert resp.status_code == 200
        body = resp.json()
        # 空库下各计数为 0，但字段齐全
        for key in ("villages", "projects", "schools", "users", "funds_amount",
                    "completeness", "health_score", "modules", "filing_rates",
                    "trend", "recent_logs"):
            assert key in body, f"overview 缺少字段 {key}"
        assert isinstance(body["filing_rates"], list)
        assert len(body["filing_rates"]) == 4
        assert body["filing_rates"][0]["module"] == "帮扶村"

    def test_villages_distribution(self, auth_client):
        resp = auth_client.get("/api/v1/statistics/villages/distribution")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)
        for key in ("by_status", "top_population", "by_province"):
            assert key in data, f"distribution 缺少字段 {key}"
        assert data["top_population"] == []

    def test_dashboard(self, auth_client):
        resp = auth_client.get("/api/v1/statistics/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_villages" in body
        assert body["total_villages"] == 0

    def test_summary(self, auth_client):
        resp = auth_client.get("/api/v1/statistics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_villages" in body
