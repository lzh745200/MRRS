"""Tests for app/services/rural_work_service.py — 目标 100% 覆盖。"""
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.rural_work import RuralWork, WorkStatus, WorkType
from app.schemas.rural_work import RuralWorkStatistics


# ---------------------------------------------------------------------------
# 纯函数测试
# ---------------------------------------------------------------------------

class TestIso:
    def test_none(self):
        from app.services.rural_work_service import _iso
        assert _iso(None) is None

    def test_datetime(self):
        from app.services.rural_work_service import _iso
        dt = datetime(2025, 6, 1, 12, 0, 0)
        assert _iso(dt) == "2025-06-01T12:00:00"


class TestSafeEnumValue:
    def test_none(self):
        from app.services.rural_work_service import _safe_enum_value
        assert _safe_enum_value(None) is None

    def test_with_value(self):
        from app.services.rural_work_service import _safe_enum_value
        assert _safe_enum_value(WorkStatus.planned) == "planned"

    def test_no_value(self):
        from app.services.rural_work_service import _safe_enum_value
        assert _safe_enum_value("plain_string") == "plain_string"


class TestToWorkType:
    def test_already_worktype(self):
        from app.services.rural_work_service import _to_work_type
        assert _to_work_type(WorkType.infrastructure) is WorkType.infrastructure

    def test_none(self):
        from app.services.rural_work_service import _to_work_type
        assert _to_work_type(None) is WorkType.infrastructure

    def test_valid_string(self):
        from app.services.rural_work_service import _to_work_type
        assert _to_work_type("education") is WorkType.education

    def test_invalid_string(self):
        from app.services.rural_work_service import _to_work_type
        assert _to_work_type("invalid_type") is WorkType.infrastructure

    def test_empty_string(self):
        from app.services.rural_work_service import _to_work_type
        assert _to_work_type("") is WorkType.infrastructure


class TestToWorkStatus:
    def test_already_workstatus(self):
        from app.services.rural_work_service import _to_work_status
        assert _to_work_status(WorkStatus.planned) is WorkStatus.planned

    def test_none(self):
        from app.services.rural_work_service import _to_work_status
        assert _to_work_status(None) is WorkStatus.planned

    def test_valid_string(self):
        from app.services.rural_work_service import _to_work_status
        assert _to_work_status("completed") is WorkStatus.completed

    def test_invalid_string(self):
        from app.services.rural_work_service import _to_work_status
        assert _to_work_status("bogus") is WorkStatus.planned

    def test_empty_string(self):
        from app.services.rural_work_service import _to_work_status
        assert _to_work_status("") is WorkStatus.planned


class TestCoerceDatetime:
    def test_datetime_passthrough(self):
        from app.services.rural_work_service import _coerce_datetime
        dt = datetime(2025, 6, 1)
        assert _coerce_datetime(dt) is dt

    def test_valid_iso_string(self):
        from app.services.rural_work_service import _coerce_datetime
        result = _coerce_datetime("2025-06-01T12:00:00")
        assert result == datetime(2025, 6, 1, 12, 0, 0)

    def test_invalid_string_fallback(self):
        from app.services.rural_work_service import _coerce_datetime
        result = _coerce_datetime("not-a-date")
        assert isinstance(result, datetime)

    def test_none_fallback(self):
        from app.services.rural_work_service import _coerce_datetime
        result = _coerce_datetime(None)
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# 辅助：mock RuralWork 对象
# ---------------------------------------------------------------------------

def _make_mock_work(**overrides):
    """创建 RuralWork ORM mock 对象。"""
    now = datetime(2025, 6, 1, 12, 0, 0)
    village_mock = MagicMock()
    village_mock.name = "测试村"
    attrs = {
        "id": 1,
        "code": "RW-ABC123",
        "name": "测试工作",
        "description": "描述",
        "type": WorkType.infrastructure,
        "status": WorkStatus.planned,
        "village_id": 10,
        "village": village_mock,
        "responsible_person": "张三",
        "contact_phone": "13800138000",
        "start_date": now,
        "end_date": now,
        "target": "目标",
        "progress": 50,
        "created_at": now,
        "updated_at": now,
        "created_by": 1,
        "updated_by": 1,
    }
    attrs.update(overrides)
    mock = MagicMock(spec=RuralWork)
    for k, v in attrs.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# RuralWorkService 服务类测试
# ---------------------------------------------------------------------------

class TestRuralWorkService:
    @pytest.fixture
    def svc(self):
        from app.services.rural_work_service import RuralWorkService
        return RuralWorkService(db=MagicMock())

    def test_init(self):
        from app.services.rural_work_service import RuralWorkService
        db = MagicMock()
        assert RuralWorkService(db=db).db is db

    # ── _to_dict ──

    def test_to_dict_with_village(self, svc):
        mock = _make_mock_work()
        result = svc._to_dict(mock)
        assert result["id"] == 1
        assert result["code"] == "RW-ABC123"
        assert result["village_name"] == "测试村"

    def test_to_dict_without_village(self, svc):
        mock = _make_mock_work(village=None)
        result = svc._to_dict(mock)
        assert result["village_name"] is None

    # ── get_rural_works ──

    def test_get_works_default(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        items, total = svc.get_rural_works()
        assert items == [] and total == 0

    def test_get_works_with_all_filters(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value = q
        q.count.return_value = 2
        mock1 = _make_mock_work(id=1)
        mock2 = _make_mock_work(id=2)
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock1, mock2]
        items, total = svc.get_rural_works(status="planned", type="education", village_id=10,
                                            search="测试", start_date="2025-01-01", end_date="2025-12-31",
                                            year=2025)
        assert total == 2
        assert items[0]["id"] == 1

    def test_get_works_asc_order(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [_make_mock_work()]
        q.count.return_value = 1
        items, total = svc.get_rural_works(order_by="name", order_desc=False)
        assert total == 1

    def test_get_works_invalid_dates_ignored(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value = q
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        items, total = svc.get_rural_works(start_date="bad-date", end_date="bad-date")
        assert total == 0

    # ── get_rural_work_by_id ──

    def test_get_work_by_id_found(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        result = svc.get_rural_work_by_id(1)
        assert result is not None
        assert result["id"] == 1

    def test_get_work_by_id_not_found(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert svc.get_rural_work_by_id(999) is None

    # ── delete_rural_work ──

    def test_delete_not_found(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert svc.delete_rural_work(999) is False

    def _setup_delete_mocks(self, svc, work_name="测试工作"):
        mock = _make_mock_work(name=work_name)
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        return mock

    def test_delete_without_user_id(self, svc):
        self._setup_delete_mocks(svc)
        assert svc.delete_rural_work(1) is True

    def test_delete_with_user_id(self, svc):
        self._setup_delete_mocks(svc)
        with patch("app.services.rural_work_service.write_work_log") as mock_log:
            assert svc.delete_rural_work(1, user_id=1) is True
            mock_log.assert_called_once()

    def test_delete_log_exception(self, svc):
        self._setup_delete_mocks(svc)
        with patch("app.services.rural_work_service.write_work_log", side_effect=Exception("boom")):
            assert svc.delete_rural_work(1, user_id=1) is True

    # ── create_rural_work ──

    def test_create_with_schema(self, svc):
        """Pydantic schema model_dump 路径。"""
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "新工作", "village_id": 10}
        svc.db.add = MagicMock()
        svc.db.commit = MagicMock()
        svc.db.refresh = lambda x: setattr(x, "id", 1)
        with patch("app.services.rural_work_service.RuralWork", return_value=_make_mock_work(id=1)) as MockRW:
            with patch.object(svc, '_generate_code', return_value='RW-8888'):
                result = svc.create_rural_work(payload, user_id=1)
                assert result["id"] == 1

    def test_create_with_dict(self, svc):
        data = {"name": "dict工作", "village_id": 10}
        svc.db.add = MagicMock()
        svc.db.commit = MagicMock()
        svc.db.refresh = lambda x: setattr(x, "id", 2)
        with patch("app.services.rural_work_service.RuralWork", return_value=_make_mock_work(id=2)):
            with patch.object(svc, '_generate_code', return_value='RW-9999'):
                result = svc.create_rural_work(data, user_id=None)
                assert result["id"] == 2

    def test_create_log_exception(self, svc):
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "新工作", "village_id": 10}
        svc.db.add = MagicMock()
        svc.db.commit = MagicMock()
        svc.db.refresh = lambda x: setattr(x, "id", 1)
        with patch("app.services.rural_work_service.RuralWork", return_value=_make_mock_work(id=1)):
            with patch("app.services.rural_work_service.write_work_log", side_effect=Exception("log fail")):
                result = svc.create_rural_work(payload, user_id=1)
                assert result["id"] == 1

    # ── update_rural_work ──

    def test_update_not_found(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert svc.update_rural_work(999, {"name": "新"}) is None

    def test_update_with_schema(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        svc.db.refresh = MagicMock()
        data = MagicMock()
        data.model_dump.return_value = {"name": "更新名", "status": "completed"}
        result = svc.update_rural_work(1, data=data, user_id=1)
        assert result["name"] == "更新名"
        assert mock.name == "更新名"

    def test_update_with_kwargs(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        svc.db.refresh = MagicMock()
        result = svc.update_rural_work(1, name="更新名", status="completed", user_id=1)
        assert result is not None

    def test_update_rejects_bad_field(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        svc.db.refresh = MagicMock()
        result = svc.update_rural_work(1, nonexistent="ignored")
        assert result is not None

    def test_update_without_user_id(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        svc.db.refresh = MagicMock()
        result = svc.update_rural_work(1, name="新名", user_id=None)
        assert result is not None

    def test_update_log_exception(self, svc):
        mock = _make_mock_work()
        svc.db.query.return_value.filter.return_value.first.return_value = mock
        svc.db.commit = MagicMock()
        svc.db.refresh = MagicMock()
        with patch("app.services.rural_work_service.write_work_log", side_effect=Exception("log fail")):
            result = svc.update_rural_work(1, name="新名", user_id=1)
            assert result is not None

    # ── get_statistics ──

    def test_get_statistics_with_data(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.count.return_value = 10
        q.filter.return_value.count.return_value = 5
        q.group_by.return_value.all.return_value = [("education", 5), ("infrastructure", 5)]
        stats = svc.get_statistics()
        assert stats.total == 10
        assert stats.completed == 5

    def test_get_statistics_zero_total(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.count.return_value = 0
        q.filter.return_value.count.return_value = 0
        q.group_by.return_value.all.return_value = []
        stats = svc.get_statistics()
        assert stats.total == 0
        assert stats.completion_rate == 0.0
        assert isinstance(stats, RuralWorkStatistics)

    # ── get_villages_for_select ──

    def test_get_villages_for_select(self, svc):
        """村庄下拉：从 supported_villages 读取并 upsert 到 villages 表（保持外键一致）"""
        mock_db = MagicMock()
        sv1 = MagicMock()
        sv1.name = "村1"
        sv1.county = "某县"
        sv1.township = "某镇"
        sv1.organization_id = 1
        sv2 = MagicMock()
        sv2.name = "村2"
        sv2.county = None
        sv2.township = None
        sv2.organization_id = None

        def _query(model):
            if model.__name__ == "SupportedVillage":
                q = MagicMock()
                q.filter.return_value = q
                q.order_by.return_value.all.return_value = [sv1, sv2]
                return q
            # Village 查询：仅村2 已存在（id=2），村1 需新增
            v2 = MagicMock()
            v2.name = "村2"
            v2.id = 2
            q = MagicMock()
            q.all.return_value = [v2]
            return q

        mock_db.query.side_effect = _query
        # flush 模拟真实数据库为主键赋值
        def _flush():
            added = mock_db.add.call_args[0][0]
            if getattr(added, "id", None) is None:
                added.id = 100

        mock_db.flush.side_effect = _flush
        # get_villages_for_select 内部懒导入 SessionLocal → patch 源模块
        with patch("app.core.database.SessionLocal", return_value=mock_db):
            result = svc.get_villages_for_select()
        assert len(result) == 2
        assert result[0]["name"] == "村1"
        assert result[0]["id"] == 100
        assert result[1] == {"id": 2, "name": "村2", "county": None}
        # 村1 被 upsert 进 villages 表
        added = mock_db.add.call_args[0][0]
        assert added.name == "村1"
        mock_db.commit.assert_called_once()

    # ── generate_work_report ──

    def test_generate_report_no_filters(self, svc):
        mock = _make_mock_work()
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [mock]
        result = svc.generate_work_report()
        assert result["total"] == 1
        assert "by_status" in result

    def test_generate_report_with_year(self, svc):
        mock = _make_mock_work(status=WorkStatus.completed)
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [mock]
        result = svc.generate_work_report(year=2025)
        assert result["total"] == 1
        assert result["completion_rate"] == 1.0

    def test_generate_report_with_date_filters(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = []
        with patch("app.services.rural_work_service._coerce_datetime") as mock_cd:
            mock_cd.return_value = datetime(2025, 1, 1)
            result = svc.generate_work_report(start_date="2025-01-01", end_date="2025-12-31")
            assert result["total"] == 0

    # ── get_available_years ──

    def test_get_available_years(self, svc):
        q1 = MagicMock()
        q2 = MagicMock()
        q3 = MagicMock()
        svc.db.query.return_value = q1
        q1.filter.return_value = q2
        q2.distinct.return_value = q3
        r1 = MagicMock()
        r1.year = 2025
        r2 = MagicMock()
        r2.year = 2024
        q3.order_by.return_value.all.return_value = [r1, r2]
        result = svc.get_available_years()
        assert result == [2025, 2024]

    def test_get_available_years_filters_none(self, svc):
        q1 = MagicMock()
        q2 = MagicMock()
        q3 = MagicMock()
        svc.db.query.return_value = q1
        q1.filter.return_value = q2
        q2.distinct.return_value = q3
        r1 = MagicMock()
        r1.year = 2025
        r2 = MagicMock()
        r2.year = None
        q3.order_by.return_value.all.return_value = [r1, r2]
        result = svc.get_available_years()
        assert result == [2025]

    # ── batch_delete ──

    def test_batch_delete_empty_list(self, svc):
        assert svc.batch_delete([]) == 0

    def test_batch_delete_with_ids(self, svc):
        q = MagicMock()
        svc.db.query.return_value = q
        q.filter.return_value.delete.return_value = 3
        svc.db.commit = MagicMock()
        assert svc.batch_delete([1, 2, 3]) == 3

    # ── _generate_code ──

    def test_generate_code(self):
        from app.services.rural_work_service import RuralWorkService
        code = RuralWorkService._generate_code()
        assert code.startswith("RW-")
        assert len(code) == 11  # "RW-" + 8 hex chars


# ---------------------------------------------------------------------------
# 数据权限（2026-08-14）：_apply_work_scope / _can_access_work
# ---------------------------------------------------------------------------

def _make_user(role="user", organization_id=5, data_scope=None, uid=7):
    user = MagicMock()
    user.id = uid
    user.role = role
    user.is_superuser = False
    user.organization_id = organization_id
    user.org_id = organization_id
    if data_scope is not None:
        user.data_scope = data_scope
    return user


@pytest.fixture
def rural_svc():
    from app.services.rural_work_service import RuralWorkService
    return RuralWorkService(db=MagicMock())


class TestWorkScope:
    def test_admin_not_filtered(self, rural_svc):
        from app.services.rural_work_service import _apply_work_scope

        q = MagicMock()
        assert _apply_work_scope(q, _make_user(role="admin"), rural_svc.db) is q

    def test_none_user_not_filtered(self, rural_svc):
        from app.services.rural_work_service import _apply_work_scope

        q = MagicMock()
        assert _apply_work_scope(q, None, rural_svc.db) is q

    def test_self_scope_filters_by_owner(self, rural_svc):
        from app.services.rural_work_service import _apply_work_scope

        q = MagicMock()
        result = _apply_work_scope(q, _make_user(data_scope="self"), rural_svc.db)
        assert result is q.filter.return_value
        assert q.filter.call_count == 1

    def test_own_dept_filters_by_org_with_legacy_fallback(self, rural_svc):
        from app.services.rural_work_service import _apply_work_scope

        # 遗留角色 manager：is_admin=False 但 get_data_scope 归一化为 OWN_DEPT
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            q = MagicMock()
            result = _apply_work_scope(q, _make_user(role="manager"), rural_svc.db)
            assert result is q.filter.return_value
            assert q.filter.call_count == 1

    def test_own_scope_without_org_filters_by_owner(self, rural_svc):
        from app.services.rural_work_service import _apply_work_scope

        q = MagicMock()
        result = _apply_work_scope(q, _make_user(organization_id=None), rural_svc.db)
        assert result is q.filter.return_value
        assert q.filter.call_count == 1


class TestCanAccessWork:
    def test_admin_always_allowed(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(organization_id=99, created_by=99)
        assert _can_access_work(work, _make_user(role="admin"), rural_svc.db) is True

    def test_none_user_allowed(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(organization_id=99, created_by=99)
        assert _can_access_work(work, None, rural_svc.db) is True

    def test_owner_allowed(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(created_by=7)
        assert _can_access_work(work, _make_user(uid=7), rural_svc.db) is True

    def test_self_scope_denies_others(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(created_by=99, organization_id=5)
        assert _can_access_work(work, _make_user(data_scope="self"), rural_svc.db) is False

    def test_same_org_allowed(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(created_by=99, organization_id=6)
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            assert _can_access_work(work, _make_user(role="manager"), rural_svc.db) is True

    def test_other_org_denied(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(created_by=99, organization_id=8)
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            assert _can_access_work(work, _make_user(role="manager"), rural_svc.db) is False

    def test_no_org_legacy_row_denied_for_stranger(self, rural_svc):
        from app.services.rural_work_service import _can_access_work

        work = _make_mock_work(created_by=99, organization_id=None)
        with patch("app.core.unified_data_scope._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            assert _can_access_work(work, _make_user(role="manager"), rural_svc.db) is False
