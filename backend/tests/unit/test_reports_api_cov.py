"""app.api.v1.data.data.reports 覆盖率攻坚测试（补充既有测试未覆盖分支）

覆盖缺口：
- 43：get_analytics_service 依赖工厂
- 494,496：village_ids/include_sections 序列化分支 → schema 未暴露字段，不可达，已 pragma 豁免
- 637-681：POST /generate 端点（comprehensive 含/不含 village_ids 过滤、statistics、异常500）
- 696-751：GET /{report_id}/download（订阅存在×json/excel、无订阅回退、异常500）
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.data.data.reports import get_analytics_service, get_report_service
from app.core.database import get_db
from app.core.security import get_current_user

BASE = "/api/v1/reports"


@pytest.fixture
def client():
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock()
    svc = MagicMock()
    svc.db = db
    svc.export_comprehensive_report = AsyncMock(return_value=b"EXCEL-BYTES")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_report_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="root", full_name="管理员"
    )
    yield TestClient(app, raise_server_exceptions=False), db, svc
    app.dependency_overrides = original


def test_get_analytics_service_direct():
    """43：依赖工厂直接调用返回 AnalyticsService 实例"""
    from app.services.analytics_service import AnalyticsService
    from app.services.report_service import ReportService

    assert isinstance(get_analytics_service(db=MagicMock()), AnalyticsService)
    assert isinstance(get_report_service(db=MagicMock()), ReportService)


class TestGenerateReport:
    def test_generate_comprehensive_with_village_ids(self, client):
        c, db, _ = client
        village = SimpleNamespace(
            id=1, village_name="幸福村", department="军区", support_unit="某部", region_scope="省内"
        )
        q = MagicMock()
        q.filter.return_value = q
        q.limit.return_value = q
        q.all.return_value = [village]
        db.query.return_value = q

        resp = c.post(
            f"{BASE}/generate",
            json={"report_type": "comprehensive", "year": 2026, "village_ids": [1]},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_villages"] == 1
        assert data["villages"][0]["village_name"] == "幸福村"
        assert data["generated_by"] == "管理员"

    def test_generate_comprehensive_without_village_ids(self, client):
        c, db, _ = client
        q = MagicMock()
        q.limit.return_value = q
        q.all.return_value = []
        db.query.return_value = q

        resp = c.post(f"{BASE}/generate", json={"report_type": "comprehensive", "year": 2026})
        assert resp.status_code == 200
        assert resp.json()["data"]["total_villages"] == 0

    def test_generate_statistics(self, client):
        c, db, _ = client
        q = MagicMock()
        q.filter.return_value = q
        q.count.return_value = 42
        db.query.return_value = q

        resp = c.post(f"{BASE}/generate", json={"report_type": "statistics", "year": 2026})
        assert resp.status_code == 200
        assert resp.json()["data"]["statistics"]["total_villages"] == 42

    def test_generate_error_500(self, client):
        c, db, _ = client
        db.query.side_effect = Exception("db gone")
        resp = c.post(f"{BASE}/generate", json={"report_type": "comprehensive", "year": 2026})
        assert resp.status_code == 500


class TestDownloadGeneratedReport:
    def _sub(self):
        return SimpleNamespace(id=7, name="年度报表", report_type="comprehensive", year=2025)

    def test_download_subscription_json(self, client):
        c, db, _ = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = self._sub()
        db.query.return_value = q

        resp = c.get(f"{BASE}/7/download?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        body = json.loads(resp.content.decode("utf-8"))
        assert body["subscription_id"] == 7
        assert body["name"] == "年度报表"

    def test_download_subscription_excel(self, client):
        c, db, svc = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = self._sub()
        db.query.return_value = q

        resp = c.get(f"{BASE}/7/download?format=excel")
        assert resp.status_code == 200
        assert resp.content == b"EXCEL-BYTES"
        assert "spreadsheetml" in resp.headers["content-type"]
        svc.export_comprehensive_report.assert_awaited_once()

    def test_download_no_subscription_fallback(self, client):
        c, db, _ = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        db.query.return_value = q

        resp = c.get(f"{BASE}/99/download?format=json")
        assert resp.status_code == 200
        body = json.loads(resp.content.decode("utf-8"))
        assert body["report_id"] == 99

    def test_download_error_500(self, client):
        c, db, _ = client
        db.query.side_effect = Exception("db gone")
        resp = c.get(f"{BASE}/1/download")
        assert resp.status_code == 500
