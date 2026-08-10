"""app.api.v1.supported_village_export 覆盖率攻坚测试

覆盖：
- _parse_id_list：None / 合法列表 / 非法 400
- GET /modules、/formats：静态清单
- GET ""（导出）：格式非法 400 / xlsx / csv 内容类型
- GET /preview：统计返回
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user

BASE = "/api/v1/supported-villages/export"


@pytest.fixture
def client():
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="root")
    yield TestClient(app, raise_server_exceptions=False), db
    app.dependency_overrides = original


class TestParseIdList:
    def test_none_input(self):
        from app.api.v1.supported_village_export import _parse_id_list

        assert _parse_id_list(None, "x") is None
        assert _parse_id_list("", "x") is None

    def test_valid_list(self):
        from app.api.v1.supported_village_export import _parse_id_list

        assert _parse_id_list("1, 2,,3", "x") == [1, 2, 3]

    def test_invalid_raises_400(self):
        from fastapi import HTTPException

        from app.api.v1.supported_village_export import _parse_id_list

        with pytest.raises(HTTPException) as exc:
            _parse_id_list("1,abc", "帮扶村ID列表")
        assert exc.value.status_code == 400


class TestStaticEndpoints:
    def test_modules(self, client):
        c, _ = client
        resp = c.get(f"{BASE}/modules")
        assert resp.status_code == 200
        assert len(resp.json()["modules"]) > 0

    def test_formats(self, client):
        c, _ = client
        resp = c.get(f"{BASE}/formats")
        assert resp.status_code == 200
        keys = [f["key"] for f in resp.json()["formats"]]
        assert keys == ["xlsx", "csv"]


class TestExport:
    def test_invalid_format_400(self, client):
        c, _ = client
        resp = c.get(f"{BASE}?format=pdf")
        assert resp.status_code == 400

    def _mk_svc(self):
        svc = MagicMock()
        svc.export.return_value = (b"DATA", "export.xlsx", {"rows": 1})
        return svc

    def test_export_xlsx(self, client):
        c, _ = client
        with patch(
            "app.services.supported_village_export_service.SupportedVillageExportService",
            return_value=self._mk_svc(),
        ):
            resp = c.get(f"{BASE}?year=2026&modules=basic,population&village_ids=1,2&format=xlsx")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert resp.content == b"DATA"

    def test_export_csv(self, client):
        c, _ = client
        svc = self._mk_svc()
        svc.export.return_value = (b"a,b\n1,2\n", "export.csv", {"rows": 1})
        with patch(
            "app.services.supported_village_export_service.SupportedVillageExportService",
            return_value=svc,
        ):
            resp = c.get(f"{BASE}?format=csv&department=军区&support_unit=某部&tiered_level=示范级")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")


class TestPreview:
    def test_preview_success(self, client):
        c, _ = client
        svc = MagicMock()
        svc._query_villages.return_value = ["v1", "v2"]
        svc._collect_export_data.return_value = {"basic": [1, 2]}
        svc._generate_statistics.return_value = {"total_rows": 2}
        with patch(
            "app.services.supported_village_export_service.SupportedVillageExportService",
            return_value=svc,
        ):
            resp = c.get(f"{BASE}/preview?year=2025&modules=basic&village_ids=3,4")
        assert resp.status_code == 200
        assert resp.json()["statistics"]["total_rows"] == 2
