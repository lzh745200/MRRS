"""定向覆盖测试 — app/services/async_export_service.py 缺失行.

覆盖 coverage.json 中缺失的模块级辅助函数与后台执行体。原
test_async_export_service.py 仅覆盖 AsyncExportService 实例方法，并通过 mock 掉
_fetch_* / _build_* 记录函数跳过了真实查询路径与工具函数，导致以下行未被覆盖：

- _format_datetime / _get_export_dir / _load_user
- _fetch_village_records / _fetch_fund_records / _fetch_project_records
  / _fetch_school_records（含全量筛选分支 + 行映射）
- _get_fetcher / _build_workbook / _build_comprehensive_workbook
- _run_export_task（成功 / 任务不存在 / 失败回写 / 回写再次失败）

全部使用伪 Query（_FakeQuery）与 SimpleNamespace 记录，不连真实数据库、
不提交全局 executor，无挂起线程。
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.async_export_service import (
    _format_datetime,
    _get_export_dir,
    _load_user,
    _fetch_village_records,
    _fetch_fund_records,
    _fetch_project_records,
    _fetch_school_records,
    _get_fetcher,
    _build_workbook,
    _build_comprehensive_workbook,
    _run_export_task,
)


class _FakeQuery:
    """可链式调用的伪 Query：filter/order_by/limit/offset 返回自身。"""

    def __init__(self, records=None, first_value=None, count_value=None, scalar_value=None):
        self._records = list(records or [])
        self._first = first_value
        self._count = count_value
        self._scalar = scalar_value

    def filter(self, *criteria):
        return self

    def order_by(self, *criteria):
        return self

    def limit(self, n):
        return self

    def offset(self, n):
        return self

    def all(self):
        return self._records

    def count(self):
        return self._count if self._count is not None else len(self._records)

    def scalar(self):
        return self._scalar

    def first(self):
        return self._first


def _db_with_records(records):
    """构造 db MagicMock，其 query() 返回含指定记录的伪 Query。"""
    db = MagicMock()
    db.query.return_value = _FakeQuery(records=records)
    return db


def _scope_passthrough():
    """让 filter_by_data_scope 原样返回 query（跳过真实数据权限过滤）。"""
    return patch(
        "app.core.data_permission.filter_by_data_scope",
        side_effect=lambda query, model, user, db=None, org_field="organization_id": query,
    )


def _village(**kw):
    defaults = dict(
        id=1,
        name="测试村",
        sequence_no="SN001",
        province="贵州省",
        city="贵阳市",
        county="花溪区",
        department="某部",
        support_unit="某旅",
        transition_status="completed",
        created_at=datetime(2025, 1, 1, 8, 0, 0),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _fund(**kw):
    defaults = dict(
        id=1,
        name="经费A",
        type="project",
        amount=1000.5,
        source="military",
        purpose="扶贫",
        status="approved",
        operator="张三",
        date=datetime(2025, 2, 1, 9, 30, 0),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _project(**kw):
    defaults = dict(
        id=1,
        name="项目A",
        code="P001",
        type="industry",
        status="in_progress",
        budget=50000,
        progress=60,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _school(**kw):
    defaults = dict(
        id=1,
        name="学校A",
        code="SC001",
        type="primary",
        city="贵阳市",
        student_count=100,
        teacher_count=20,
        support_status=SimpleNamespace(value="active"),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# _format_datetime
# ---------------------------------------------------------------------------


class TestFormatDatetime:
    def test_none_returns_empty_string(self):
        assert _format_datetime(None) == ""

    def test_datetime_formatted(self):
        assert _format_datetime(datetime(2025, 3, 4, 5, 6, 7)) == "2025-03-04 05:06:07"

    def test_other_value_str(self):
        assert _format_datetime(123) == "123"
        assert _format_datetime("already-str") == "already-str"


# ---------------------------------------------------------------------------
# _get_export_dir
# ---------------------------------------------------------------------------


class TestGetExportDir:
    def test_creates_and_returns_dir(self, tmp_path, monkeypatch):
        from app.core.config import settings

        target = tmp_path / "exports" / "nested"
        monkeypatch.setattr(settings, "EXPORT_DIR", str(target))
        result = _get_export_dir()
        assert result == target
        assert target.is_dir()


# ---------------------------------------------------------------------------
# _load_user
# ---------------------------------------------------------------------------


class TestLoadUser:
    def test_no_user_id_returns_none(self):
        assert _load_user(MagicMock(), None) is None

    def test_zero_user_id_returns_none(self):
        assert _load_user(MagicMock(), 0) is None

    def test_returns_user_by_id(self):
        user = SimpleNamespace(id=5, username="u5")
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=user)
        assert _load_user(db, 5) is user
        db.query.assert_called_once()


# ---------------------------------------------------------------------------
# _fetch_village_records
# ---------------------------------------------------------------------------


class TestFetchVillageRecords:
    def test_no_user_basic_mapping(self):
        record = _village(created_at=None)
        db = _db_with_records([record])
        rows = _fetch_village_records(db, None, {})
        assert len(rows) == 1
        assert rows[0]["ID"] == 1
        assert rows[0]["名称"] == "测试村"
        assert rows[0]["编码"] == "SN001"
        assert rows[0]["创建时间"] == ""  # None → 空字符串

    def test_no_user_empty_params(self):
        db = _db_with_records([_village()])
        rows = _fetch_village_records(db, None, {})
        assert rows[0]["省份"] == "贵州省"

    def test_full_filters_and_user_scope(self):
        record = _village()
        db = _db_with_records([record])
        params = {
            "keyword": "测试",
            "status": "completed",
            "department": "某部",
            "support_unit": "某旅",
            "village_name": "测试村",
            "region_scope": "遵义",
            "is_three_regions": True,
            "is_border_area": False,
            "is_revitalization_tier": True,
        }
        with _scope_passthrough():
            rows = _fetch_village_records(db, object(), params)
        assert len(rows) == 1
        assert rows[0]["名称"] == "测试村"
        assert rows[0]["部门"] == "某部"
        assert rows[0]["帮扶单位"] == "某旅"
        assert rows[0]["状态"] == "completed"
        assert rows[0]["创建时间"] == "2025-01-01 08:00:00"

    def test_boolean_filters_false_value_still_apply(self):
        record = _village()
        db = _db_with_records([record])
        params = {
            "is_three_regions": False,
            "is_border_area": False,
            "is_revitalization_tier": False,
        }
        with _scope_passthrough():
            rows = _fetch_village_records(db, object(), params)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# _fetch_fund_records
# ---------------------------------------------------------------------------


class TestFetchFundRecords:
    def test_no_user_basic_mapping(self):
        record = _fund(date=None)
        db = _db_with_records([record])
        rows = _fetch_fund_records(db, None, {})
        assert len(rows) == 1
        assert rows[0]["ID"] == 1
        assert rows[0]["名称"] == "经费A"
        assert rows[0]["金额"] == 1000.5
        assert rows[0]["使用日期"] == ""

    def test_full_filters_and_user_scope(self):
        record = _fund()
        db = _db_with_records([record])
        params = {"keyword": "经费", "fund_type": "project", "status": "approved"}
        with _scope_passthrough():
            rows = _fetch_fund_records(db, object(), params)
        assert len(rows) == 1
        assert rows[0]["类型"] == "project"
        assert rows[0]["状态"] == "approved"
        assert rows[0]["经办人"] == "张三"
        assert rows[0]["使用日期"] == "2025-02-01 09:30:00"


# ---------------------------------------------------------------------------
# _fetch_project_records
# ---------------------------------------------------------------------------


class TestFetchProjectRecords:
    def test_no_user_basic_mapping(self):
        record = _project(start_date=None, end_date=None)
        db = _db_with_records([record])
        rows = _fetch_project_records(db, None, {})
        assert len(rows) == 1
        assert rows[0]["ID"] == 1
        assert rows[0]["名称"] == "项目A"
        assert rows[0]["编码"] == "P001"
        assert rows[0]["预算"] == 50000
        assert rows[0]["进度"] == "60%"
        assert rows[0]["开始日期"] == ""
        assert rows[0]["结束日期"] == ""

    def test_full_filters_and_user_scope(self):
        record = _project()
        db = _db_with_records([record])
        params = {"keyword": "项目", "project_type": "industry", "status": "in_progress"}
        with _scope_passthrough():
            rows = _fetch_project_records(db, object(), params)
        assert len(rows) == 1
        assert rows[0]["类型"] == "industry"
        assert rows[0]["状态"] == "in_progress"
        assert rows[0]["开始日期"] == "2025-01-01 00:00:00"
        assert rows[0]["结束日期"] == "2025-12-31 00:00:00"

    def test_zero_budget_and_progress(self):
        record = _project(budget=0, progress=0)
        db = _db_with_records([record])
        rows = _fetch_project_records(db, None, {})
        assert rows[0]["预算"] == 0
        assert rows[0]["进度"] == "0%"


# ---------------------------------------------------------------------------
# _fetch_school_records
# ---------------------------------------------------------------------------


class TestFetchSchoolRecords:
    def test_no_user_basic_mapping(self):
        record = _school(support_status=None)
        db = _db_with_records([record])
        rows = _fetch_school_records(db, None, {})
        assert len(rows) == 1
        assert rows[0]["ID"] == 1
        assert rows[0]["名称"] == "学校A"
        assert rows[0]["编码"] == "SC001"
        assert rows[0]["学生数"] == 100
        assert rows[0]["状态"] == ""  # support_status 为 None → 空串

    def test_full_filters_and_user_scope(self):
        record = _school()
        db = _db_with_records([record])
        params = {"keyword": "学校", "school_type": "primary"}
        with _scope_passthrough():
            rows = _fetch_school_records(db, object(), params)
        assert len(rows) == 1
        assert rows[0]["类型"] == "primary"
        assert rows[0]["状态"] == "active"


# ---------------------------------------------------------------------------
# _get_fetcher
# ---------------------------------------------------------------------------


class TestGetFetcher:
    def test_known_entity(self):
        from app.services.async_export_service import _fetch_fund_records
        assert _get_fetcher("funds") is _fetch_fund_records

    def test_default_fallback(self):
        from app.services.async_export_service import _fetch_village_records
        assert _get_fetcher("unknown_entity") is _fetch_village_records


# ---------------------------------------------------------------------------
# _build_workbook
# ---------------------------------------------------------------------------


class TestBuildWorkbook:
    @patch("app.services.async_export_service.ExcelExportService")
    def test_village(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_village_list.return_value = b"v"
        assert _build_workbook("supported_villages", [], MagicMock()) == b"v"
        inst.export_village_list.assert_called_once_with([])

    @patch("app.services.async_export_service.ExcelExportService")
    def test_village_alias(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_village_list.return_value = b"v2"
        assert _build_workbook("supported_village", [], MagicMock()) == b"v2"

    @patch("app.services.async_export_service.ExcelExportService")
    def test_funds(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_fund_list.return_value = b"f"
        assert _build_workbook("funds", [], MagicMock()) == b"f"

    @patch("app.services.async_export_service.ExcelExportService")
    def test_projects(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_project_list.return_value = b"p"
        assert _build_workbook("projects", [], MagicMock()) == b"p"

    @patch("app.services.async_export_service.ExcelExportService")
    def test_schools(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_school_list.return_value = b"s"
        assert _build_workbook("schools", [], MagicMock()) == b"s"

    @patch("app.services.async_export_service.ExcelExportService")
    def test_unknown_fallback(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_village_list.return_value = b"d"
        assert _build_workbook("unknown", [], MagicMock()) == b"d"
        inst.export_village_list.assert_called_once_with([])


# ---------------------------------------------------------------------------
# _build_comprehensive_workbook
# ---------------------------------------------------------------------------


class _ComprehensiveDb:
    """模拟综合报表所需的多模型查询（区分模型 / 聚合表达式）。"""

    def __init__(self, villages=(), projects=(), funds=(), funds_sum=0):
        self._villages = list(villages)
        self._projects = list(projects)
        self._funds = list(funds)
        self._funds_sum = funds_sum

    def query(self, arg):
        tablename = getattr(arg, "__tablename__", None)
        if tablename == "supported_villages":
            return _FakeQuery(records=self._villages)
        if tablename == "projects":
            return _FakeQuery(records=self._projects)
        if tablename == "funds":
            return _FakeQuery(records=self._funds)
        if tablename in ("users", "schools"):
            return _FakeQuery(records=[])
        # 聚合表达式（coalesce(sum(Fund.amount), 0)）
        return _FakeQuery(scalar_value=self._funds_sum)


class TestBuildComprehensiveWorkbook:
    @patch("app.services.async_export_service.ExcelExportService")
    def test_no_user(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_comprehensive_report.return_value = b"comp"
        db = _ComprehensiveDb(
            villages=[_village()],
            projects=[_project()],
            funds=[_fund()],
            funds_sum=1000.5,
        )
        content = _build_comprehensive_workbook(db, None)
        assert content == b"comp"
        inst.export_comprehensive_report.assert_called_once()
        summary, vdata, pdata, fdata = inst.export_comprehensive_report.call_args[0]
        assert summary["村庄总数"] == 1
        assert summary["经费总金额"] == "1000.50元"
        assert len(vdata) == 1 and len(pdata) == 1 and len(fdata) == 1

    @patch("app.services.async_export_service.ExcelExportService")
    def test_with_user_scope(self, MockSvc):
        inst = MockSvc.return_value
        inst.export_comprehensive_report.return_value = b"comp"
        db = _ComprehensiveDb(villages=[_village()])
        with _scope_passthrough():
            content = _build_comprehensive_workbook(db, object())
        assert content == b"comp"
        inst.export_comprehensive_report.assert_called_once()


# ---------------------------------------------------------------------------
# _run_export_task
# ---------------------------------------------------------------------------


class TestRunExportTask:
    def _task(self, **kw):
        defaults = dict(
            user_id=1,
            query_params={},
            export_type="funds",
            file_name="test.xlsx",
            status=None,
            started_at=None,
            file_path=None,
            file_size=None,
            record_count=None,
            completed_at=None,
            error_message=None,
        )
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    @patch("app.core.database.SessionLocal")
    def test_task_not_found(self, MockSessionLocal):
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=None)
        MockSessionLocal.return_value = db
        _run_export_task("tid")  # 不抛异常，直接 return
        db.close.assert_called_once()

    @patch("app.services.async_export_service.safe_commit")
    @patch("app.services.async_export_service._load_user", return_value=None)
    @patch("app.services.async_export_service._get_fetcher")
    @patch("app.services.async_export_service._build_workbook", return_value=b"xlsx-content")
    @patch("app.services.async_export_service._get_export_dir")
    @patch("app.core.database.SessionLocal")
    def test_success_non_comprehensive(
        self, MockSessionLocal, mock_dir, mock_build, mock_fetcher, mock_load_user, mock_commit, tmp_path
    ):
        task = self._task()
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=task)
        MockSessionLocal.return_value = db
        mock_dir.return_value = tmp_path
        mock_fetcher.return_value = lambda db, user, params: []

        _run_export_task("tid")

        assert task.status == "completed"
        assert task.error_message is None
        assert task.file_size == len(b"xlsx-content")
        assert task.record_count == 0
        assert task.file_path
        assert list(tmp_path.iterdir()), "应写出导出文件"
        assert mock_commit.call_count == 2  # processing + completed

    @patch("app.services.async_export_service.safe_commit")
    @patch("app.services.async_export_service._load_user", return_value=None)
    @patch("app.services.async_export_service._build_comprehensive_workbook", return_value=b"comp")
    @patch("app.services.async_export_service._get_export_dir")
    @patch("app.core.database.SessionLocal")
    def test_success_comprehensive(
        self, MockSessionLocal, mock_dir, mock_build, mock_load_user, mock_commit, tmp_path
    ):
        task = self._task(export_type="comprehensive", file_name=None)
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=task)
        MockSessionLocal.return_value = db
        mock_dir.return_value = tmp_path

        _run_export_task("tid")

        assert task.status == "completed"
        assert task.record_count == 0
        assert task.file_name == "comprehensive_tid.xlsx"  # 回退生成文件名
        mock_build.assert_called_once()

    @patch("app.services.async_export_service.safe_commit")
    @patch("app.services.async_export_service._load_user", return_value=None)
    @patch("app.services.async_export_service._get_fetcher")
    @patch("app.services.async_export_service._build_workbook", side_effect=RuntimeError("boom"))
    @patch("app.core.database.SessionLocal")
    def test_exception_marks_failed(
        self, MockSessionLocal, mock_build, mock_fetcher, mock_load_user, mock_commit
    ):
        task = self._task()
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=task)
        MockSessionLocal.return_value = db
        mock_fetcher.return_value = lambda db, user, params: []

        _run_export_task("tid")  # 不向上抛

        assert task.status == "failed"
        assert task.error_message == "boom"

    @patch("app.services.async_export_service.safe_commit")
    @patch("app.services.async_export_service._load_user", return_value=None)
    @patch("app.services.async_export_service._get_fetcher")
    @patch("app.services.async_export_service._build_workbook", side_effect=RuntimeError("boom"))
    @patch("app.core.database.SessionLocal")
    def test_failed_writeback_raises(
        self, MockSessionLocal, mock_build, mock_fetcher, mock_load_user, mock_commit
    ):
        task = self._task()
        db = MagicMock()
        db.query.return_value = _FakeQuery(first_value=task)
        MockSessionLocal.return_value = db
        mock_fetcher.return_value = lambda db, user, params: []

        calls = {"n": 0}

        def fake_commit(db):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("commit failed")
            return True

        mock_commit.side_effect = fake_commit

        _run_export_task("tid")  # 回写失败被内层 except 吞掉，不向上抛

        assert task.status == "failed"  # 状态已置 failed（回写提交失败但属性已设置）
        assert mock_commit.call_count == 2
