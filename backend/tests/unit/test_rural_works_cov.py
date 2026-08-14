"""app.api.v1.rural_works 覆盖率攻坚测试

覆盖点：
- _parse_query_date：空值/各格式解析/非法回退 None
- 全部 10 个端点：service 委托 + NotFound 分支
- batch_delete：空 ids、工作日志异常降级
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.api.v1.rural_works as rw
from app.core.exceptions import NotFoundException


def _user():
    return SimpleNamespace(id=1, username="admin", role="admin")


@pytest.fixture
def svc():
    with patch.object(rw, "RuralWorkService") as m:
        yield m.return_value


class TestParseQueryDate:
    def test_empty_returns_none(self):
        assert rw._parse_query_date(None) is None
        assert rw._parse_query_date("   ") is None

    def test_valid_formats(self):
        assert rw._parse_query_date("2026-01-01") is not None
        assert rw._parse_query_date("2026-01-01T10:30") is not None
        assert rw._parse_query_date("2026-01-01T10:30:00") is not None
        assert rw._parse_query_date("2026-01-01 10:30:00") is not None

    def test_invalid_returns_none(self):
        assert rw._parse_query_date("not-a-date") is None


class TestEndpoints:
    async def test_list(self, svc):
        svc.get_rural_works.return_value = ([{"id": 1}], 1)
        result = await rw.list_rural_works(
            skip=0, limit=10, status="done", type="t", village_id=1,
            search="k", start_date="2026-01-01", end_date="bad", year=2026,
            order_by="created_at", order_desc=True, db=MagicMock(), current_user=_user(),
        )
        assert result["data"]["total"] == 1

    async def test_statistics(self, svc):
        svc.get_statistics.return_value = SimpleNamespace(model_dump=lambda: {"a": 1})
        result = await rw.get_statistics(MagicMock(), _user())
        assert result.data == {"a": 1}

    async def test_villages(self, svc):
        svc.get_villages_for_select.return_value = [{"id": 1}]
        result = await rw.get_villages_for_select(MagicMock(), _user())
        assert result.data == [{"id": 1}]

    async def test_report(self, svc):
        svc.generate_work_report.return_value = {"summary": 1}
        result = await rw.generate_work_report(2026, "2026-01-01", None, MagicMock(), _user())
        assert result.data == {"summary": 1}

    async def test_years(self, svc):
        svc.get_available_years.return_value = [2026]
        result = await rw.get_available_years(MagicMock(), _user())
        assert result.data == [2026]

    async def test_get_found(self, svc):
        svc.get_rural_work_by_id.return_value = {"id": 1}
        result = await rw.get_rural_work(1, MagicMock(), _user())
        assert result.data == {"id": 1}

    async def test_get_not_found(self, svc):
        svc.get_rural_work_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await rw.get_rural_work(99, MagicMock(), _user())

    async def test_create(self, svc):
        svc.create_rural_work.return_value = {"id": 1}
        result = await rw.create_rural_work(SimpleNamespace(), MagicMock(), _user())
        assert result.message == "创建成功"

    async def test_update_found(self, svc):
        svc.update_rural_work.return_value = {"id": 1}
        result = await rw.update_rural_work(1, SimpleNamespace(), MagicMock(), _user())
        assert result.message == "更新成功"

    async def test_update_not_found(self, svc):
        svc.update_rural_work.return_value = None
        with pytest.raises(NotFoundException):
            await rw.update_rural_work(99, SimpleNamespace(), MagicMock(), _user())

    async def test_delete_found(self, svc):
        svc.delete_rural_work.return_value = True
        result = await rw.delete_rural_work(1, MagicMock(), _user())
        assert result.message == "删除成功"

    async def test_delete_not_found(self, svc):
        svc.delete_rural_work.return_value = False
        with pytest.raises(NotFoundException):
            await rw.delete_rural_work(99, MagicMock(), _user())

    async def test_batch_delete_with_worklog(self, svc):
        svc.batch_delete.return_value = 2
        with patch("app.services.work_log_service.write_work_log") as m_log:
            result = await rw.batch_delete_rural_works({"ids": [1, 2]}, MagicMock(), _user())
        # 批量删除同时生成审批留痕任务（approval_task_id 字段）
        assert result.data["deleted"] == 2
        assert "approval_task_id" in result.data
        m_log.assert_called_once()

    async def test_batch_delete_worklog_exception_degrades(self, svc):
        svc.batch_delete.return_value = 1
        with patch("app.services.work_log_service.write_work_log", side_effect=RuntimeError("boom")):
            result = await rw.batch_delete_rural_works({"ids": [1]}, MagicMock(), _user())
        assert result.data["deleted"] == 1

    async def test_batch_delete_non_dict_payload(self, svc):
        result = await rw.batch_delete_rural_works([], MagicMock(), _user())
        assert result.data == {"deleted": 0}
