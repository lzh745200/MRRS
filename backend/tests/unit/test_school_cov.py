"""app.api.v1.school 覆盖率攻坚测试（补充既有测试未覆盖分支）

覆盖点：
- _parse_scholarship_status：状态映射/回退/短行
- import_schools_excel：通用异常行、提交失败 500
- import_scholarship_students：全循环分支（跳行/正常/格式错/通用错）+ 临时文件清理降级
- import_school_scholarship_students：通用异常行
- list_schools：缓存命中/未命中回写/TypeError 降级（删除 PYTEST_CURRENT_TEST 解锁缓存块）
- create_school：school_type/school_level 字段映射
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from openpyxl import Workbook

import app.api.v1.school as sch
from app.models.school import ScholarshipStatus, SchoolLevel, SchoolType
from app.schemas.school import SchoolCreate


# ==================== 公共设施 ====================


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit"):
        getattr(q, attr).return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


def _db(*queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


def _user(**kw):
    defaults = dict(
        id=1, username="admin", role="admin", is_superuser=True, organization_id=1,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ==================== _parse_scholarship_status ====================


class TestParseScholarshipStatus:
    def test_status_from_row(self):
        row = (1, "张三", None, None, None, None, None, None, "approved")
        assert sch._parse_scholarship_status(row) == ScholarshipStatus.APPROVED

    def test_unknown_status_defaults_pending(self):
        row = (1, "张三", None, None, None, None, None, None, "weird")
        assert sch._parse_scholarship_status(row) == ScholarshipStatus.PENDING

    def test_short_row_defaults_pending(self):
        assert sch._parse_scholarship_status((1, "张三")) == ScholarshipStatus.PENDING


# ==================== 非法文件魔数 → 400 ====================


class TestImportInvalidFile:
    async def test_import_schools_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            await sch.import_schools_excel(
                UploadFile(file=BytesIO(b"garbage"), filename="t.xlsx"), _user(), MagicMock())
        assert exc_info.value.status_code == 400

    async def test_import_scholarship_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            await sch.import_scholarship_students(
                UploadFile(file=BytesIO(b"garbage"), filename="t.xlsx"), MagicMock(), _user())
        assert exc_info.value.status_code == 400

    async def test_import_school_scholarship_invalid(self):
        with (
            patch.object(sch, "_get_school_and_check_permission"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sch.import_school_scholarship_students(
                1, UploadFile(file=BytesIO(b"garbage"), filename="t.xlsx"), _user(), MagicMock())
        assert exc_info.value.status_code == 400


# ==================== import_schools_excel ====================


class TestImportSchoolsExcel:
    async def test_generic_error_row(self):
        good = (0, "学校甲", "CODE1", "小学", "贵州", "黔南", "都匀", "地址",
                "300", "20", "帮扶中", "单位", "校长", "电话")
        bad = (0, "学校乙",) + (None,) * 13
        content = _xlsx_bytes([["h"] * 14, good, bad])
        with (
            patch.object(sch, "safe_commit"),
            patch.object(sch, "School", side_effect=[SimpleNamespace(), RuntimeError("boom")]),
        ):
            result = await sch.import_schools_excel(
                UploadFile(file=BytesIO(content), filename="t.xlsx"), _user(), MagicMock())
        assert result["data"]["imported"] == 1
        assert result["data"]["failed"] == 1
        assert "boom" in result["data"]["errors"][0]

    async def test_cache_invalidation_degrades(self):
        """覆盖 school.py:703-704（列表缓存清理失败降级）与 309-310（仪表盘缓存失效降级）"""
        good = (0, "学校甲", "CODE1", "小学", "贵州", "黔南", "都匀", "地址",
                "300", "20", "帮扶中", "单位", "校长", "电话")
        content = _xlsx_bytes([["h"] * 14, good])
        cache_mgr = MagicMock()
        cache_mgr.delete_by_prefix = AsyncMock(side_effect=Exception("cache down"))
        with (
            patch.object(sch, "safe_commit"),
            patch.object(sch, "School", return_value=SimpleNamespace()),
            patch("app.core.cache.cache_manager", cache_mgr),
            patch("app.api.v1.data.data.dashboard.invalidate_dashboard_cache",
                  side_effect=Exception("dash boom")),
            patch.object(sch, "submit_entity_change_approval", return_value=77),
        ):
            result = await sch.import_schools_excel(
                UploadFile(file=BytesIO(content), filename="t.xlsx"), _user(), MagicMock())
        assert result["data"]["imported"] == 1
        assert result["data"]["failed"] == 0

    async def test_commit_failure_500(self):
        content = _xlsx_bytes([["h"], (0, "学校甲")])
        with (
            patch.object(sch, "safe_commit", side_effect=RuntimeError("db err")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sch.import_schools_excel(
                UploadFile(file=BytesIO(content), filename="t.xlsx"), _user(), MagicMock())
        assert exc_info.value.status_code == 500
        assert "导入失败" in exc_info.value.detail


# ==================== 审批回写 no-op / 非 approved 早退 ====================


class TestApprovalApplyHandlers:
    def test_school_noop_handler(self):
        # 覆盖 school.py:59 —— 学校审批回写 no-op 处理器
        assert sch._apply_school_approval_result(MagicMock(), MagicMock()) is None

    def test_scholarship_not_approved_early_return(self):
        # 覆盖 school.py:68 —— task.status != approved 时直接返回（不查库）
        db = MagicMock()
        task = SimpleNamespace(status="rejected", entity_id=1)
        assert sch._apply_scholarship_approval_result(db, task) is None
        db.query.assert_not_called()


# ==================== import_scholarship_students ====================


class TestImportScholarshipStudents:
    async def test_full_loop_branches(self):
        rows = [
            ["h"] * 9,
            (None,),                                    # 跳行
            (2, "张三", "SID1", 2026, 1000, "校", "年级", "理由", "approved"),  # 正常
            (3, "李四", None, None, "abc"),             # 金额非法 → ValueError
            (4, "王五",),                               # 触发通用异常
        ]
        content = _xlsx_bytes(rows)
        with (
            patch.object(sch, "safe_commit"),
            patch.object(sch, "ScholarshipStudent", side_effect=[SimpleNamespace(), RuntimeError("boom")]),
            patch.object(sch.os, "unlink", side_effect=FileNotFoundError("gone")),
        ):
            result = await sch.import_scholarship_students(
                UploadFile(file=BytesIO(content), filename="t.xlsx"), MagicMock(), _user())
        assert result["data"]["imported"] == 1
        assert result["data"]["failed"] == 2
        assert any("数据格式错误" in e for e in result["data"]["errors"])
        assert any("boom" in e for e in result["data"]["errors"])


# ==================== import_school_scholarship_students ====================


class TestImportSchoolScholarshipStudents:
    async def test_generic_error_row(self):
        rows = [["h", "h"], ("学生甲", "一年级")]
        content = _xlsx_bytes(rows)
        _db = MagicMock()
        # 重复学生去重查询：无重复 → first() 返回 None，继续走构造分支触发 boom
        _db.query.return_value.filter.return_value.first.return_value = None
        with (
            patch.object(sch, "_get_school_and_check_permission"),
            patch.object(sch, "safe_commit"),
            patch.object(sch, "ScholarshipStudent", side_effect=RuntimeError("boom")),
        ):
            result = await sch.import_school_scholarship_students(
                1, UploadFile(file=BytesIO(content), filename="t.xlsx"), _user(), _db)
        assert result["data"]["imported"] == 0
        assert any("boom" in e for e in result["data"]["errors"])

    async def test_duplicate_student_skipped(self):
        """覆盖 school.py:1380-1381 —— 同校同名同年级学生重复导入 → 记错误并跳过"""
        rows = [["h", "h"], ("学生乙", "二年级")]
        content = _xlsx_bytes(rows)
        _db = MagicMock()
        # 去重查询命中已有记录 → 跳过
        _db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=5)
        with (
            patch.object(sch, "_get_school_and_check_permission"),
            patch.object(sch, "safe_commit"),
        ):
            result = await sch.import_school_scholarship_students(
                1, UploadFile(file=BytesIO(content), filename="t.xlsx"), _user(), _db)
        assert result["data"]["imported"] == 0
        assert any("已存在，跳过" in e for e in result["data"]["errors"])
        # 学生行未入库：db.add 仅被审批留痕(ApprovalTask/Message)调用
        added = [str(c.args[0]) for c in _db.add.call_args_list]
        assert not any("ScholarshipStudent" in a for a in added)


# ==================== list_schools 缓存分支 ====================


class TestListSchoolsCache:
    async def _call(self, cache, db):
        scope = MagicMock()
        scope.filter_by_org_ids = MagicMock(side_effect=lambda q, *a, **k: q)
        with patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)):
            return await sch.list_schools(
                page=1, page_size=20, keyword=None, name=None, type=None,
                support_status=None, supportStatus=None, include_deleted=False,
                current_user=_user(), data_scope=scope, db=db,
            )

    async def test_cache_hit(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.get = AsyncMock(return_value={"cached": True})
        result = await self._call(cache, MagicMock())
        assert result == {"cached": True}

    async def test_cache_miss_and_writeback(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        db = _db(_q(count=0, all=[]))
        result = await self._call(cache, db)
        assert result["data"]["total"] == 0
        cache.set.assert_awaited_once()

    async def test_cache_type_error_degrades(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.get = AsyncMock(side_effect=TypeError("bad"))
        db = _db(_q(count=0, all=[]))
        result = await self._call(cache, db)
        assert result["data"]["total"] == 0


# ==================== create_school 字段映射 ====================


class TestCreateSchool:
    async def test_school_type_level_mapping(self):
        data = SchoolCreate(
            name="新学校", code="SCH-1",
            school_type=SchoolType.PRIMARY, school_level=SchoolLevel.COUNTY,
        )
        db = _db(_q(first=None))  # 编码唯一
        with (
            patch.object(sch, "safe_commit"),
            patch.object(sch, "write_work_log"),
        ):
            result = await sch.create_school(data, _user(), db)
        assert result is not None
