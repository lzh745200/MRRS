"""app.services.update_log_service.UpdateLogService 覆盖补充测试（真实 SQLite 会话）。

覆盖 record_update / get_update_logs / get_latest_update / get_update_by_version /
is_version_recorded / get_update_count / _build_version_description /
_create_version_entry / initialize_version_history（force/skip/create）/
sync_version_history / check_and_record_version_change（三分支）。
"""
from datetime import datetime

import pytest

from app.models.system_config import SystemUpdateLog
from app.services.update_log_service import (
    VERSION_HISTORY_DATA,
    UpdateLogService,
)


@pytest.fixture
def svc(real_db_session):
    return UpdateLogService(real_db_session)


def _mklog(db, version, created_at=None, updated_by="tester"):
    log = SystemUpdateLog(
        id=f"id-{version}",
        version=version,
        description=f"desc {version}",
        updated_by=updated_by,
    )
    if created_at is not None:
        log.created_at = created_at
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


class TestRecordUpdate:
    def test_creates_and_persists(self, svc, real_db_session):
        entry = svc.record_update("2.0.0", "新版本", updated_by="admin")
        assert entry.version == "2.0.0"
        assert entry.id
        assert real_db_session.get(SystemUpdateLog, entry.id) is not None

    def test_default_args(self, svc):
        entry = svc.record_update("2.0.1")
        assert entry.description == ""
        assert entry.updated_by is None


class TestQueries:
    def test_get_update_logs_desc_and_asc(self, svc, real_db_session):
        _mklog(real_db_session, "1.0.0", datetime(2026, 1, 1))
        _mklog(real_db_session, "2.0.0", datetime(2026, 2, 1))
        desc = svc.get_update_logs()
        assert desc[0].version == "2.0.0"
        asc = svc.get_update_logs(order_by_desc=False)
        assert asc[0].version == "1.0.0"

    def test_get_update_logs_skip_limit(self, svc, real_db_session):
        for i in range(5):
            _mklog(real_db_session, f"v{i}", datetime(2026, 1, i + 1))
        out = svc.get_update_logs(skip=1, limit=2)
        assert len(out) == 2

    def test_get_latest_update(self, svc, real_db_session):
        _mklog(real_db_session, "1.0.0", datetime(2026, 1, 1))
        _mklog(real_db_session, "3.0.0", datetime(2026, 3, 1))
        assert svc.get_latest_update().version == "3.0.0"

    def test_get_latest_update_none(self, svc):
        assert svc.get_latest_update() is None

    def test_get_update_by_version(self, svc, real_db_session):
        _mklog(real_db_session, "1.2.3")
        assert svc.get_update_by_version("1.2.3").version == "1.2.3"
        assert svc.get_update_by_version("9.9.9") is None

    def test_is_version_recorded(self, svc, real_db_session):
        _mklog(real_db_session, "1.0.0")
        assert svc.is_version_recorded("1.0.0") is True
        assert svc.is_version_recorded("2.0.0") is False

    def test_get_update_count(self, svc, real_db_session):
        assert svc.get_update_count() == 0
        _mklog(real_db_session, "1.0.0")
        assert svc.get_update_count() == 1


class TestBuildDescription:
    def test_with_features(self, svc):
        text = svc._build_version_description(
            {"description": "标题", "features": ["功能A", "功能B"]})
        assert "更新内容" in text
        assert "- 功能A" in text

    def test_without_features(self, svc):
        assert svc._build_version_description({"description": "仅标题"}) == "仅标题"


class TestCreateVersionEntry:
    def test_entry_fields(self, svc):
        entry = svc._create_version_entry(
            {"version": "1.0.0", "date": "2026-02-20",
             "description": "d", "features": ["f"]},
            updated_by="sys",
        )
        assert entry.version == "1.0.0"
        assert entry.updated_by == "sys"
        assert entry.created_at == datetime.fromisoformat("2026-02-20T00:00:00")


class TestInitializeVersionHistory:
    def test_creates_all_when_empty(self, svc, real_db_session):
        result = svc.initialize_version_history(updated_by="sys")
        assert result["status"] == "success"
        assert result["initialized_count"] == len(VERSION_HISTORY_DATA)
        assert svc.get_update_count() == len(VERSION_HISTORY_DATA)

    def test_skips_when_existing(self, svc, real_db_session):
        _mklog(real_db_session, "0.1.0")
        result = svc.initialize_version_history()
        assert result["status"] == "skipped"
        assert result["existing_count"] == 1
        assert result["initialized_count"] == 0

    def test_force_clears_then_refills(self, svc, real_db_session):
        _mklog(real_db_session, "stale")
        result = svc.initialize_version_history(force=True)
        assert result["status"] == "success"
        assert result["initialized_count"] == len(VERSION_HISTORY_DATA)
        assert svc.is_version_recorded("stale") is False

    def test_empty_data_else_branch(self, svc, monkeypatch):
        monkeypatch.setattr("app.services.update_log_service.VERSION_HISTORY_DATA", [])
        result = svc.initialize_version_history()
        assert result["status"] == "success"
        assert result["initialized_count"] == 0


class TestSyncVersionHistory:
    def test_supplements_missing_only(self, svc, real_db_session):
        first = VERSION_HISTORY_DATA[0]["version"]
        _mklog(real_db_session, first)
        result = svc.sync_version_history()
        assert result["status"] == "success"
        assert result["synced_count"] == len(VERSION_HISTORY_DATA) - 1

    def test_no_sync_when_complete(self, svc, real_db_session):
        for v in VERSION_HISTORY_DATA:
            _mklog(real_db_session, v["version"])
        result = svc.sync_version_history()
        assert result["synced_count"] == 0

    def test_sync_all_when_empty(self, svc):
        result = svc.sync_version_history()
        assert result["synced_count"] == len(VERSION_HISTORY_DATA)


class TestCheckAndRecordVersionChange:
    def test_no_latest_initializes(self, svc):
        out = svc.check_and_record_version_change("1.0.0")
        assert out["action"] == "initialize"

    def test_version_changed_unknown_version(self, svc, real_db_session):
        _mklog(real_db_session, "1.0.0", datetime(2026, 1, 1))
        out = svc.check_and_record_version_change("9.9.9")
        assert out["action"] == "record_change"
        assert out["old_version"] == "1.0.0"
        assert out["new_version"] == "9.9.9"
        assert svc.is_version_recorded("9.9.9") is True

    def test_version_changed_known_version(self, svc, real_db_session):
        _mklog(real_db_session, "0.1.0", datetime(2026, 1, 1))
        known = VERSION_HISTORY_DATA[-1]["version"]
        out = svc.check_and_record_version_change(known)
        assert out["action"] == "record_change"
        # 已知版本 → 描述取自 VERSION_HISTORY_DATA
        rec = svc.get_update_by_version(known)
        assert "更新内容" in rec.description

    def test_version_unchanged_returns_none(self, svc, real_db_session):
        _mklog(real_db_session, "1.0.0", datetime(2026, 1, 1))
        assert svc.check_and_record_version_change("1.0.0") is None
