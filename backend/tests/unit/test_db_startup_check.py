"""单机数据库自检(T1.3): startup_check + /system/health/database-health"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_startup_check_ok():
    from app.services.database_health_service import DatabaseHealthService

    svc = DatabaseHealthService()
    with patch.object(svc, "quick_check", return_value={"status": "ok", "db_size_mb": 1.0}):
        result = svc.startup_check()
    assert result["status"] == "ok"


def test_startup_check_error_swallowed():
    from app.services.database_health_service import DatabaseHealthService

    svc = DatabaseHealthService()
    with patch.object(svc, "quick_check", side_effect=RuntimeError("boom")):
        result = svc.startup_check()
    assert result["status"] == "error"
    assert "boom" in result["message"]


def test_startup_check_propagates_error_status():
    from app.services.database_health_service import DatabaseHealthService

    svc = DatabaseHealthService()
    with patch.object(svc, "quick_check", return_value={"status": "error", "message": "损坏"}):
        result = svc.startup_check()
    assert result["status"] == "error"


def test_database_health_api():
    from app.main import app

    client = TestClient(app)
    with patch(
        "app.services.database_health_service.database_health_service.get_database_info",
        return_value={"status": "ok", "db_size_mb": 2.5, "table_count": 42},
    ), patch(
        "app.services.database_health_service.database_health_service.get_stats",
        return_value={"last_quick_check": "2026-08-02T00:00:00", "integrity_errors": 0},
    ), patch(
        "app.services.database_health_service.database_health_service.health_status",
        {"status": "ok", "issues": []},
    ):
        resp = client.get("/api/v1/system/health/database-health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["info"]["table_count"] == 42
        assert data["stats"]["integrity_errors"] == 0


def test_database_health_api_error():
    from app.main import app

    client = TestClient(app)
    with patch(
        "app.services.database_health_service.database_health_service.get_database_info",
        side_effect=RuntimeError("boom"),
    ):
        resp = client.get("/api/v1/system/health/database-health")
        # 2026-10-29 审计：失败必须以 503 出站（探针只看状态码）；body 仍保留 code:500
        assert resp.status_code == 503
        assert resp.json()["code"] == 500
        assert resp.json()["data"]["status"] == "error"


def test_main_startup_check_registered():
    import app.main as m

    assert hasattr(m, "_run_database_startup_check")
    assert callable(m._run_database_startup_check)
