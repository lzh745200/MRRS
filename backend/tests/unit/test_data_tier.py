"""
Tests for app.api.v1.monitoring.data_tier — API endpoints
"""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

import pytest
from fastapi import Depends, HTTPException, status

BASE = "/api/v1/data-tier"


def _make_admin_checker(client):
    """Install a proper admin-checking dependency for require_admin on the client."""
    from app.core.security import require_admin, get_current_active_user

    async def _check_admin(current_user=Depends(get_current_active_user)):
        role = getattr(current_user, "role", "")
        is_superuser = getattr(current_user, "is_superuser", False)
        if role not in ("admin", "super_admin") and not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限",
            )
        return current_user

    original_override = client.app.dependency_overrides.get(require_admin)
    client.app.dependency_overrides[require_admin] = _check_admin
    return client, require_admin, original_override


@pytest.fixture
def admin_client(client_with_mocked_auth):
    client = client_with_mocked_auth
    client, require_admin, original = _make_admin_checker(client)
    yield client
    if original is not None:
        client.app.dependency_overrides[require_admin] = original
    else:
        client.app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def regular_client(client_with_regular_user_auth):
    client = client_with_regular_user_auth
    client, require_admin, original = _make_admin_checker(client)
    yield client
    if original is not None:
        client.app.dependency_overrides[require_admin] = original
    else:
        client.app.dependency_overrides.pop(require_admin, None)


# ─────── GET /stats ───────


class TestGetStorageStats:
    """GET /api/v1/data-tier/stats — get_storage_stats"""

    def test_success_admin(self, admin_client):
        mock_stats = {
            "total_records": 5000,
            "by_tier": {
                "hot": {"count": 3000, "files": []},
                "warm": {"count": 1500, "files": []},
                "cold": {"count": 500, "files": []},
            },
            "storage": {"hot_db_size": 1048576, "warm_db_size": 524288, "cold_archive_size": 262144},
        }
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.get_archive_stats",
                   return_value=mock_stats):
            resp = admin_client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records"] == 5000
        assert data["by_tier"]["hot"]["count"] == 3000
        assert data["storage"]["cold_archive_size"] == 262144

    def test_success_regular_user(self, regular_client):
        mock_stats = {"total_records": 100, "by_tier": {}, "storage": {}}
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.get_archive_stats",
                   return_value=mock_stats):
            resp = regular_client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_records"] == 100

    def test_empty_stats(self, admin_client):
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.get_archive_stats",
                   return_value={"total_records": 0, "by_tier": {}, "storage": {}}):
            resp = admin_client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_records"] == 0


# ─────── GET /summary ───────


class TestGetStorageSummary:
    """GET /api/v1/data-tier/summary — get_storage_summary"""

    def test_success_admin(self, admin_client):
        mock_summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tiers": {"hot": 3000, "warm": 1500, "cold": 500},
            "storage_sizes": {"hot_db_size": 1048576, "warm_db_size": 524288, "cold_archive_size": 262144},
            "recommendations": ["考虑归档旧数据"],
        }
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.get_storage_summary",
                   return_value=mock_summary):
            resp = admin_client.get(f"{BASE}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiers"]["hot"] == 3000
        assert len(data["recommendations"]) == 1

    def test_forbidden_regular_user(self, regular_client):
        resp = regular_client.get(f"{BASE}/summary")
        assert resp.status_code == 403

    def test_no_recommendations(self, admin_client):
        mock_summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tiers": {"hot": 10, "warm": 5, "cold": 2},
            "storage_sizes": {"hot_db_size": 100, "warm_db_size": 100, "cold_archive_size": 100},
            "recommendations": [],
        }
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.get_storage_summary",
                   return_value=mock_summary):
            resp = admin_client.get(f"{BASE}/summary")
        assert resp.status_code == 200
        assert resp.json()["recommendations"] == []


# ─────── GET /tier/{tier} ───────


class TestGetTierInfo:
    """GET /api/v1/data-tier/tier/{tier} — get_tier_info"""

    def test_hot_tier(self, admin_client):
        resp = admin_client.get(f"{BASE}/tier/hot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "hot"
        assert data["hot_threshold_days"] is not None
        assert data["warm_threshold_days"] is None

    def test_warm_tier(self, admin_client):
        resp = admin_client.get(f"{BASE}/tier/warm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "warm"
        assert data["hot_threshold_days"] is None
        assert data["warm_threshold_days"] is not None

    def test_cold_tier(self, admin_client):
        resp = admin_client.get(f"{BASE}/tier/cold")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "cold"
        assert data["hot_threshold_days"] is None
        assert data["warm_threshold_days"] is None

    def test_case_insensitive(self, admin_client):
        resp = admin_client.get(f"{BASE}/tier/HOT")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "hot"

    def test_invalid_tier(self, admin_client):
        resp = admin_client.get(f"{BASE}/tier/invalid_tier")
        assert resp.status_code == 400
        assert "无效的数据分级" in resp.json()["detail"]

    def test_regular_user(self, regular_client):
        resp = regular_client.get(f"{BASE}/tier/hot")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "hot"


# ─────── POST /archive/{model_name} ───────


class TestArchiveModel:
    """POST /api/v1/data-tier/archive/{model_name} — archive_model"""

    def test_success(self, admin_client):
        mock_result = (100, "成功归档 100 条记录到温存储")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.archive_records",
                   return_value=mock_result):
            resp = admin_client.post(f"{BASE}/archive/auditlog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["archived_count"] == 100
        assert data["model"] == "auditlog"
        assert "before_date" in data

    def test_with_params(self, admin_client):
        mock_result = (50, "成功归档 50 条记录到温存储")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.archive_records",
                   return_value=mock_result):
            resp = admin_client.post(f"{BASE}/archive/worklog?before_days=180&batch_size=500")
        assert resp.status_code == 200
        assert resp.json()["archived_count"] == 50

    def test_invalid_model(self, admin_client):
        resp = admin_client.post(f"{BASE}/archive/invalid_model")
        assert resp.status_code == 400
        assert "不支持的模型" in resp.json()["detail"]

    def test_model_import_error(self, admin_client):
        with patch("app.api.v1.monitoring.data_tier.getattr",
                   side_effect=AttributeError("not found")):
            resp = admin_client.post(f"{BASE}/archive/auditlog")
        assert resp.status_code == 400
        assert "模型未找到" in resp.json()["detail"]

    def test_forbidden_regular_user(self, regular_client):
        resp = regular_client.post(f"{BASE}/archive/auditlog")
        assert resp.status_code == 403

    def test_zero_records(self, admin_client):
        mock_result = (0, "没有需要归档的记录")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.archive_records",
                   return_value=mock_result):
            resp = admin_client.post(f"{BASE}/archive/auditlog")
        assert resp.status_code == 200
        assert resp.json()["archived_count"] == 0


# ─────── GET /archives ───────


class TestListArchives:
    """GET /api/v1/data-tier/archives — list_archives"""

    def test_empty_archives(self, admin_client):
        """Both cold and warm paths don't exist — returns empty arrays."""
        from app.api.v1.monitoring.data_tier import data_tier_service
        with patch.object(data_tier_service.config, 'COLD_ARCHIVE_PATH', '/nonexistent/cold'):
            with patch.object(data_tier_service.config, 'WARM_DATA_PATH', '/nonexistent/warm'):
                resp = admin_client.get(f"{BASE}/archives")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cold_archives"] == []
        assert data["warm_archives"] == []

    def test_with_cold_archive_files(self, admin_client):
        """Cold path has .gz files — archives appear in result."""
        from app.api.v1.monitoring.data_tier import data_tier_service
        with tempfile.TemporaryDirectory() as tmpdir:
            cold_dir = Path(tmpdir) / "cold_archives"
            cold_dir.mkdir()
            gz_file = cold_dir / "test_archive.gz"
            gz_file.write_text("test data")

            warm_file = Path(tmpdir) / "warm_data.db"
            warm_file.write_text("warm data")

            with patch.object(data_tier_service.config, 'COLD_ARCHIVE_PATH', str(cold_dir)):
                with patch.object(data_tier_service.config, 'WARM_DATA_PATH', str(warm_file)):
                    resp = admin_client.get(f"{BASE}/archives")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cold_archives"]) == 1
        assert data["cold_archives"][0]["name"] == "test_archive.gz"
        assert data["cold_archives"][0]["size"] > 0

    def test_tier_filter_cold(self, admin_client):
        from app.api.v1.monitoring.data_tier import data_tier_service
        with tempfile.TemporaryDirectory() as tmpdir:
            cold_dir = Path(tmpdir) / "cold"
            cold_dir.mkdir()
            gz_file = cold_dir / "data.gz"
            gz_file.write_text("data")

            with patch.object(data_tier_service.config, 'COLD_ARCHIVE_PATH', str(cold_dir)):
                with patch.object(data_tier_service.config, 'WARM_DATA_PATH', '/nonexistent/warm'):
                    resp = admin_client.get(f"{BASE}/archives?tier=cold")
        assert resp.status_code == 200
        data = resp.json()
        assert "cold_archives" in data
        assert len(data["cold_archives"]) == 1

    def test_tier_filter_warm(self, admin_client):
        from app.api.v1.monitoring.data_tier import data_tier_service
        with tempfile.TemporaryDirectory() as tmpdir:
            warm_file = Path(tmpdir) / "warm.db"
            warm_file.write_text("data")

            with patch.object(data_tier_service.config, 'COLD_ARCHIVE_PATH', '/nonexistent/cold'):
                with patch.object(data_tier_service.config, 'WARM_DATA_PATH', str(warm_file)):
                    resp = admin_client.get(f"{BASE}/archives?tier=warm")
        assert resp.status_code == 200
        data = resp.json()
        assert "warm_archives" in data

    def test_tier_filter_invalid(self, admin_client):
        from app.api.v1.monitoring.data_tier import data_tier_service
        with patch.object(data_tier_service.config, 'COLD_ARCHIVE_PATH', '/nonexistent/cold'):
            with patch.object(data_tier_service.config, 'WARM_DATA_PATH', '/nonexistent/warm'):
                resp = admin_client.get(f"{BASE}/archives?tier=unknown")
        assert resp.status_code == 200
        data = resp.json()
        assert "cold_archives" in data
        assert "warm_archives" in data

    def test_forbidden_regular_user(self, regular_client):
        resp = regular_client.get(f"{BASE}/archives")
        assert resp.status_code == 403


# ─────── POST /restore ───────


class TestRestoreFromArchive:
    """POST /api/v1/data-tier/restore — restore_from_archive"""

    def test_success(self, admin_client):
        mock_result = (50, "成功恢复 50 条记录")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.restore_from_archive",
                   return_value=mock_result):
            resp = admin_client.post(
                f"{BASE}/restore",
                params={"archive_file": "auditlog_20240101.gz", "model_name": "auditlog"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restored_count"] == 50
        assert data["archive_file"] == "auditlog_20240101.gz"

    def test_invalid_model(self, admin_client):
        resp = admin_client.post(
            f"{BASE}/restore",
            params={"archive_file": "test.gz", "model_name": "invalid"},
        )
        assert resp.status_code == 400
        assert "不支持的模型" in resp.json()["detail"]

    def test_model_import_error(self, admin_client):
        with patch(
            "app.api.v1.monitoring.data_tier.getattr",
            side_effect=AttributeError("not found"),
        ):
            resp = admin_client.post(
                f"{BASE}/restore",
                params={"archive_file": "test.gz", "model_name": "auditlog"},
            )
        assert resp.status_code == 400
        assert "模型未找到" in resp.json()["detail"]

    def test_forbidden_regular_user(self, regular_client):
        resp = regular_client.post(
            f"{BASE}/restore",
            params={"archive_file": "test.gz", "model_name": "auditlog"},
        )
        assert resp.status_code == 403

    def test_zero_records(self, admin_client):
        mock_result = (0, "没有可恢复的记录")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.restore_from_archive",
                   return_value=mock_result):
            resp = admin_client.post(
                f"{BASE}/restore",
                params={"archive_file": "empty.gz", "model_name": "message"},
            )
        assert resp.status_code == 200
        assert resp.json()["restored_count"] == 0


# ─────── DELETE /cleanup ───────


class TestCleanupOldArchives:
    """DELETE /api/v1/data-tier/cleanup — cleanup_old_archives"""

    def test_success(self, admin_client):
        mock_result = (10, "成功清理 10 个归档文件")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.cleanup_old_archives",
                   return_value=mock_result):
            resp = admin_client.delete(f"{BASE}/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 10
        assert data["max_age_days"] == 365

    def test_with_custom_days(self, admin_client):
        mock_result = (5, "成功清理 5 个归档文件")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.cleanup_old_archives",
                   return_value=mock_result):
            resp = admin_client.delete(f"{BASE}/cleanup?max_age_days=180")
        assert resp.status_code == 200
        assert resp.json()["max_age_days"] == 180
        assert resp.json()["deleted_count"] == 5

    def test_zero_deleted(self, admin_client):
        mock_result = (0, "没有需要清理的文件")
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.cleanup_old_archives",
                   return_value=mock_result):
            resp = admin_client.delete(f"{BASE}/cleanup")
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 0

    def test_forbidden_regular_user(self, regular_client):
        resp = regular_client.delete(f"{BASE}/cleanup")
        assert resp.status_code == 403


# ─────── GET /tier-for-record/{date} ───────


class TestGetTierForRecord:
    """GET /api/v1/data-tier/tier-for-record/{date} — get_tier_for_record"""

    def test_hot_record(self, admin_client):
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        date_str = recent_date.strftime("%Y-%m-%dT%H:%M:%S")
        from app.services.data_tier_service import DataTier
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.determine_tier",
                   return_value=DataTier.HOT):
            resp = admin_client.get(f"{BASE}/tier-for-record/{date_str}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "hot"
        assert isinstance(data["age_days"], int)

    def test_warm_record(self, admin_client):
        old_date = datetime.now(timezone.utc) - timedelta(days=500)
        date_str = old_date.strftime("%Y-%m-%dT%H:%M:%S")
        from app.services.data_tier_service import DataTier
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.determine_tier",
                   return_value=DataTier.WARM):
            resp = admin_client.get(f"{BASE}/tier-for-record/{date_str}")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "warm"

    def test_cold_record(self, admin_client):
        old_date = datetime.now(timezone.utc) - timedelta(days=1500)
        date_str = old_date.strftime("%Y-%m-%dT%H:%M:%S")
        from app.services.data_tier_service import DataTier
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.determine_tier",
                   return_value=DataTier.COLD):
            resp = admin_client.get(f"{BASE}/tier-for-record/{date_str}")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "cold"

    def test_regular_user(self, regular_client):
        date_str = "2024-01-01T00:00:00"
        from app.services.data_tier_service import DataTier
        with patch("app.api.v1.monitoring.data_tier.data_tier_service.determine_tier",
                   return_value=DataTier.HOT):
            resp = regular_client.get(f"{BASE}/tier-for-record/{date_str}")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "hot"
