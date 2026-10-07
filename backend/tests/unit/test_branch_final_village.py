"""supported_village.py 终局分支清零（Group A 之后的收尾轮）。

直调函数/端点级用例，针对 coverage.py 报告的缺失分支弧（A->B）。
不修改任何 app/ 源码；不可达弧在用例注释中说明。

覆盖目标（基线缺失弧/行）：
- _resolve_village_sort 96/98（三元两分支）
- _apply_village_approval_result 107
- _get_section_data 委员会成员子表分支
- _copy_section_data 279->280（目标年已存在）
- _save_section_data 未知字段告警分支 + 委员会成员写入分支
- _invalidate_village_cache 411->413 / 417->418
- _find_village_header_row 431->432 / 435->430 / 437->428 / 437->438 / 440
- _process_import_row 457 / 469->470 / 480->483
- list_villages 521->522 缓存命中/未命中、537、549->552、568/570/572、623->624
- batch_delete_villages 817->821（deleted_count=0 不触发备份）
- delete_village 958（回收站记录重复删除 409）
- preview_purge_village / restore_village / purge_village 主体与密码校验分支
- validate_yearly_data 1200->1229 / 1221->1216
- _section_label_map 1493->1500 / 1496->1498
- _coerce_section_value 1506/1510/1513-1518/1519->1520/1521
- _import_section_sheet 1528->1529 / 1546->1547 / 1552->1553 / 1554->1555 /
  1560->1557 / 1564->1565 / 1570->1571
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Float, Integer, String

import app.api.v1.supported_village as sv
from app.models.supported_village import (
    SupportedVillage,
    VillageCommitteeInfo,
    VillageCommitteeMember,
    VillagePopulation,
)


# ==================== 公共设施 ====================


def q(**kw):
    """通用查询链 mock：链式调用自返回，scalar/first/all/count/update 可配。"""
    m = MagicMock()
    for attr in (
        "filter", "options", "order_by", "offset", "limit",
        "with_entities", "distinct", "delete", "subquery",
    ):
        getattr(m, attr).return_value = m
    m.scalar.return_value = kw.get("scalar")
    m.first.return_value = kw.get("first")
    m.all.return_value = kw.get("all", [])
    m.count.return_value = kw.get("count", 0)
    m.update.return_value = kw.get("update")
    return m


class _Columns:
    """可迭代 + 可 get 的列集合替身（供 _section_label_map / _coerce_section_value）。"""

    def __init__(self, cols):
        self._cols = list(cols)

    def __iter__(self):
        return iter(self._cols)

    def get(self, key):
        for c in self._cols:
            if c.name == key:
                return c
        return None


def fake_model(columns, name="FakeSectionModel"):
    """columns: [(col_name, comment, sqlalchemy_type), ...]"""
    cols = [
        SimpleNamespace(name=n, comment=c, type=t) for n, c, t in columns
    ]
    return SimpleNamespace(__name__=name, __tablename__=name.lower(),
                           __table__=SimpleNamespace(columns=_Columns(cols)))


def fake_model_from(real_model):
    """由真实模型构造同构替身（列名/注释/类型一致，避免实例化约束）。"""
    cols = [
        (c.name, getattr(c, "comment", None), c.type)
        for c in real_model.__table__.columns
    ]
    return fake_model(cols, name=real_model.__name__)


class FakeWS:
    """openpyxl 工作表替身：iter_rows 支持 min_row/max_row/values_only。"""

    def __init__(self, rows):
        self.rows = list(rows)

    def iter_rows(self, *a, **kw):
        rows = self.rows
        max_row = kw.get("max_row")
        if max_row is not None:
            rows = rows[:max_row]
        return iter(rows)


def record_for(model, **vals):
    """按模型列名构造行替身（未指定列一律 None，避免 getattr 无默认值报错）。"""
    rec = SimpleNamespace()
    for col in model.__table__.columns:
        setattr(rec, col.name, vals.get(col.name, None))
    return rec


def make_village(**extra):
    v = SimpleNamespace(
        id=1, village_name="示范村", is_active=True, deleted_at=None,
        transition_status="none", organization_id=1, created_by=1,
        transition_fund_items=None, transition_fund_military_total=0,
        transition_fund_local_total=0,
    )
    for k, val in extra.items():
        setattr(v, k, val)
    return v


# ==================== 排序 & 审批处理器 ====================


class TestSortAndHandler:
    def test_resolve_sort_no_sort_by_returns_id_desc(self):
        col = sv._resolve_village_sort(None, None)
        assert col is not None

    def test_resolve_sort_unknown_column_falls_back_to_id_desc(self):
        assert sv._resolve_village_sort("not_a_column", "asc") is not None

    def test_resolve_sort_mapped_column_desc(self):
        desc_col = sv._resolve_village_sort("village_name", "desc")
        asc_col = sv._resolve_village_sort("village_name", "ASC")
        # 两个方向解析为不同表达式（desc/asc 三元两分支）
        assert str(desc_col).endswith("DESC")
        assert str(asc_col).endswith("ASC")
        assert str(desc_col) != str(asc_col)

    def test_apply_village_approval_result_returns_none(self):
        # 107：审批终态回写处理器为空实现（帮扶村无 pending 门）
        assert sv._apply_village_approval_result(MagicMock(), MagicMock()) is None


# ==================== 年度数据辅助函数 ====================


class TestSectionDataHelpers:
    def test_get_section_data_committee_loads_members(self):
        row = record_for(VillageCommitteeInfo, id=5)
        member = SimpleNamespace(
            name="张三", position="书记", phone="13800000000",
            is_veteran=True, remark="示范",
        )
        db = MagicMock()
        db.query.side_effect = [
            q(first=row),           # 主表行
            q(all=[member]),        # 成员子表
        ]
        result = sv._get_section_data(db, VillageCommitteeInfo, 1, 2024)
        assert result is not None
        assert len(result["members"]) == 1
        assert result["members"][0]["name"] == "张三"
        # camelCase 归一：isVeteran 键存在（is_veteran → isVeteran）
        assert result["members"][0]["isVeteran"] is True
        # 跳过列不进入结果
        assert "id" not in result

    def test_get_section_data_missing_row_returns_none(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        assert sv._get_section_data(db, VillagePopulation, 1, 2024) is None

    def test_copy_section_data_target_year_exists_returns_false(self):
        db = MagicMock()
        db.query.side_effect = [
            q(first=SimpleNamespace(id=1)),  # 源行存在
            q(first=SimpleNamespace(id=2)),  # 目标年已存在 → 不覆盖
        ]
        assert sv._copy_section_data(db, VillagePopulation, 1, 2023, 2024) is False

    def test_copy_section_data_no_source_returns_false(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        assert sv._copy_section_data(db, VillagePopulation, 1, 2023, 2024) is False

    def test_copy_section_data_creates_target_row(self):
        db = MagicMock()
        db.query.side_effect = [
            q(first=SimpleNamespace(id=1)),
            q(first=None),
        ]
        assert sv._copy_section_data(db, VillagePopulation, 1, 2023, 2024) is True
        db.add.assert_called_once()

    def test_save_section_data_unknown_field_logs_warning(self, caplog):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        with caplog.at_level(logging.WARNING, logger="app.api.v1.supported_village"):
            row = sv._save_section_data(
                db, VillagePopulation, 1, 2024, {"totally_unknown_field_xyz": 1}
            )
        assert row is not None
        assert any(
            "totally_unknown_field_xyz" in r.getMessage() for r in caplog.records
        )
        db.add.assert_called()  # 新行被加入会话

    def test_save_section_data_committee_members_written(self):
        db = MagicMock()
        db.query.side_effect = [
            q(first=None),      # 主表行不存在 → 新建
            q(),                # 清除旧成员查询
        ]
        row = sv._save_section_data(
            db, VillageCommitteeInfo, 1, 2024,
            {"members": [{"name": "李四", "position": "主任", "isVeteran": True}]},
        )
        assert row is not None
        db.flush.assert_called()          # 新行先 flush 拿主键（row.id is None）
        # 成员子表写入：row + member 两次 add
        assert db.add.call_count == 2

    def test_save_section_data_committee_skips_non_dict_member(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None), q()]
        sv._save_section_data(
            db, VillageCommitteeInfo, 1, 2024, {"members": ["not-a-dict"]}
        )
        # 仅主表新行被加入，非 dict 成员被跳过
        assert db.add.call_count == 1


# ==================== 缓存失效 ====================


class TestInvalidateVillageCache:
    async def test_returns_early_under_pytest(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
        cache_holder = {"called": False}

        async def _gc():
            cache_holder["called"] = True
            return MagicMock()

        monkeypatch.setattr("app.core.cache.get_cache_service", _gc)
        await sv._invalidate_village_cache()
        assert cache_holder["called"] is False  # 411->412

    async def test_deletes_cache_prefix_when_not_pytest(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.delete_by_prefix = AsyncMock()

        async def _gc():
            return cache

        monkeypatch.setattr("app.core.cache.get_cache_service", _gc)
        await sv._invalidate_village_cache()
        cache.delete_by_prefix.assert_awaited_once_with("villages:list:")

    async def test_swallows_cache_error(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.delete_by_prefix = AsyncMock(side_effect=RuntimeError("cache down"))

        async def _gc():
            return cache

        monkeypatch.setattr("app.core.cache.get_cache_service", _gc)
        # 不抛异常（417->418 兜底）
        await sv._invalidate_village_cache()


# ==================== Excel 表头探测 & 单行解析 ====================


class TestHeaderDetectionAndRow:
    def test_header_row_with_none_cells_and_duplicate_labels(self):
        ws = FakeWS([
            (None, "帮扶村名称", "部门单位", "帮扶村名称"),  # None 跳过 + 重复标签去重
        ])
        idx, col_map = sv._find_village_header_row(ws)
        assert idx == 1
        assert col_map["village_name"] == 1
        assert col_map["department"] == 2

    def test_header_not_found_falls_back_to_positional(self):
        ws = FakeWS([
            ("无关列A", "无关列B"),
            ("x", "y"),
        ])
        idx, col_map = sv._find_village_header_row(ws)
        assert idx == 1  # 440 回退
        assert col_map["village_name"] == 0
        assert len(col_map) == len(sv._FIELD_NAMES)

    def test_process_import_row_bool_parsed_and_not_none(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        col_map = {"village_name": 0, "county": 1, "is_three_regions": 2}
        ok, err = sv._process_import_row(
            ("示范村", "某县", "是"), col_map, db, 2, current_user=None
        )
        assert ok is True and err is None
        added = db.add.call_args.args[0]
        assert added.is_three_regions is True

    def test_process_import_row_bool_empty_stays_none(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        col_map = {"village_name": 0, "is_three_regions": 1}
        ok, _ = sv._process_import_row(
            ("示范村", ""), col_map, db, 2, current_user=None
        )
        assert ok is True
        added = db.add.call_args.args[0]
        assert added.is_three_regions is None

    def test_process_import_row_length_exceeded_rejected(self):
        db = MagicMock()
        col_map = {"village_name": 0}
        ok, err = sv._process_import_row(
            ("超长" * 200,), col_map, db, 3, current_user=None
        )
        assert ok is False
        assert "长度超过" in err
        db.add.assert_not_called()

    def test_process_import_row_without_current_user_skips_ownership(self):
        # 480->483：current_user 为 None 时跳过归属字段赋值，直接入库
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        col_map = {"village_name": 0}
        ok, err = sv._process_import_row(("示范村",), col_map, db, 4, current_user=None)
        assert ok is True and err is None
        added = db.add.call_args.args[0]
        assert added.organization_id is None
        assert added.created_by is None

    def test_process_import_row_with_user_sets_ownership(self):
        db = MagicMock()
        db.query.side_effect = [q(first=None)]
        user = SimpleNamespace(id=9, organization_id=3)
        ok, _ = sv._process_import_row(("示范村",), {"village_name": 0}, db, 5, user)
        assert ok is True
        added = db.add.call_args.args[0]
        assert added.organization_id == 3
        assert added.created_by == 9

    def test_process_import_row_missing_name_rejected(self):
        db = MagicMock()
        ok, err = sv._process_import_row((None,), {"village_name": 0}, db, 6)
        assert ok is False
        assert "不能为空" in err

    def test_process_import_row_duplicate_rejected(self):
        db = MagicMock()
        db.query.side_effect = [q(first=SimpleNamespace(id=1))]
        ok, err = sv._process_import_row(("示范村",), {"village_name": 0}, db, 7)
        assert ok is False
        assert "已存在" in err


# ==================== list_villages ====================


class TestListVillages:
    def _db(self, items, total=1):
        query = q(count=total, all=items)
        db = MagicMock()
        db.query.return_value = query
        return db, query

    async def test_cache_hit_returns_cached_without_query(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cached = {"code": 200, "data": {"items": [], "total": 0}}
        cache = MagicMock()
        cache.get = AsyncMock(return_value=cached)
        cache.set = AsyncMock()

        async def _gc():
            return cache

        monkeypatch.setattr("app.core.cache.get_cache_service", _gc)
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        db, query = self._db([], total=0)
        user = SimpleNamespace(id=1, organization_id=1, role="user", is_superuser=False)
        resp = await sv.list_villages(
            page=1, page_size=20, with_summary=False, include_deleted=False,
            current_user=user, db=db,
        )
        assert resp is cached
        db.query.assert_not_called()

    async def test_cache_miss_queries_and_writes_cache(self, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()

        async def _gc():
            return cache

        monkeypatch.setattr("app.core.cache.get_cache_service", _gc)
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        item = SimpleNamespace(to_dict=lambda: {"id": 1, "village_name": "示范村"})
        db, query = self._db([item], total=1)
        user = SimpleNamespace(id=1, organization_id=1, role="user", is_superuser=False)
        resp = await sv.list_villages(
            page=1, page_size=20, with_summary=False, include_deleted=False,
            current_user=user, db=db,
        )
        assert resp["code"] == 200
        assert resp["data"]["total"] == 1
        assert resp["data"]["items"][0]["village_name"] == "示范村"
        cache.set.assert_awaited()  # 623->624 写回缓存

    async def test_filters_applied_when_all_params_given(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        item = SimpleNamespace(to_dict=lambda: {"id": 2, "village_name": "乙村"})
        db, query = self._db([item], total=1)
        user = SimpleNamespace(id=1, organization_id=1, role="user", is_superuser=False)
        resp = await sv.list_villages(
            page=1, page_size=10, keyword="乙", department="农业局", county="某县",
            is_revitalization_tier=True, is_three_regions=False,
            is_ethnic_area=False, is_key_county=True, year_start=2024,
            sort_by="village_name", sort_order="desc",
            include_deleted=True, with_summary=False,
            current_user=user, db=db,
        )
        assert resp["code"] == 200
        # 每个筛选参数各触发一次 filter 调用（含 keyword/department/county/year/
        # tier/three_regions/ethnic/key_county）；include_deleted=True 跳过软删过滤
        assert query.filter.call_count >= 8

    async def test_with_summary_aggregates(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        item = SimpleNamespace(to_dict=lambda: {"id": 3, "village_name": "丙村"})
        db, query = self._db([item], total=1)
        query.first.side_effect = [(1000.0, 500.0), (1, 2, 3)]
        user = SimpleNamespace(id=1, organization_id=1, role="user", is_superuser=False)
        resp = await sv.list_villages(
            page=1, page_size=10, with_summary=True, include_deleted=False,
            current_user=user, db=db,
        )
        summary = resp["data"]["summary"]
        assert summary["total"] == 1
        assert summary["total_investment"] == 1500.0
        assert summary["county_count"] == 2
        assert summary["department_count"] == 3

    async def test_items_without_to_dict_uses_fallback(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        item = SimpleNamespace(id=8, village_name="丁村")
        db, query = self._db([item], total=1)
        user = SimpleNamespace(id=1, organization_id=1, role="user", is_superuser=False)
        resp = await sv.list_villages(
            page=1, page_size=10, with_summary=False, include_deleted=False,
            current_user=user, db=db,
        )
        assert resp["data"]["items"] == [{"id": 8, "village_name": "丁村"}]


# ==================== 批量删除 / 单个删除 ====================


class TestDeleteFlows:
    async def test_batch_delete_zero_affected_skips_backup(self, monkeypatch):
        # 817->821：delete_count 为 0 时不触发即时备份
        monkeypatch.setattr("app.core.security.verify_password", lambda *a, **k: True)
        monkeypatch.setattr(sv, "apply_scope_filter", lambda query, *a, **k: query)
        submitted = {}
        monkeypatch.setattr(
            sv, "submit_entity_change_approval",
            lambda *a, **k: submitted.setdefault("task", 55),
        )
        backup = MagicMock()
        monkeypatch.setattr(
            "app.services.immediate_backup.trigger_immediate_backup", backup
        )

        async def _noop():
            return None

        monkeypatch.setattr(sv, "_invalidate_village_cache", _noop)

        db = MagicMock()
        db.query.return_value = q(update=0)
        data = sv.BatchDeleteRequest(ids=[1, 2], confirm_password="pw")
        user = SimpleNamespace(id=1, hashed_password="h", organization_id=1,
                               role="admin", is_superuser=True)
        resp = await sv.batch_delete_villages(data, current_user=user, db=db)
        assert resp["data"]["deleted"] == 0
        assert resp["data"]["approval_task_id"] == 55
        backup.assert_not_called()

    async def test_batch_delete_wrong_password_raises(self, monkeypatch):
        monkeypatch.setattr("app.core.security.verify_password", lambda *a, **k: False)
        db = MagicMock()
        data = sv.BatchDeleteRequest(ids=[1], confirm_password="bad")
        user = SimpleNamespace(id=1, hashed_password="h")
        with pytest.raises(HTTPException) as ei:
            await sv.batch_delete_villages(data, current_user=user, db=db)
        assert ei.value.status_code == 400

    async def test_batch_delete_empty_ids_raises(self):
        db = MagicMock()
        data = sv.BatchDeleteRequest(ids=[], confirm_password="pw")
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as ei:
            await sv.batch_delete_villages(data, current_user=user, db=db)
        assert ei.value.status_code == 400

    async def test_delete_village_already_recycled_conflicts(self, monkeypatch):
        # 958：已在回收站的记录重复 DELETE → 409
        monkeypatch.setattr(
            sv, "_get_village_or_404",
            lambda *a, **k: make_village(is_active=False),
        )
        db = MagicMock()
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as ei:
            await sv.delete_village(1, current_user=user, db=db)
        assert ei.value.status_code == 409

    async def test_delete_village_soft_deletes(self, monkeypatch):
        village = make_village(is_active=True)
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: village)

        async def _noop():
            return None

        monkeypatch.setattr(sv, "_invalidate_village_cache", _noop)
        monkeypatch.setattr(sv, "_record_village_change", MagicMock())

        async def _submit(*a, **k):
            return 1

        monkeypatch.setattr(sv, "submit_entity_change_approval", _submit)
        db = MagicMock()
        user = SimpleNamespace(id=1)
        resp = await sv.delete_village(1, current_user=user, db=db)
        assert resp["code"] == 200
        assert village.is_active is False
        assert village.deleted_at is not None


# ==================== 回收站：预览 / 恢复 / 彻底删除 ====================


class TestRecycleBinFlows:
    def test_require_village_in_recycle_bin_raises_for_active(self):
        with pytest.raises(HTTPException) as ei:
            sv._require_village_in_recycle_bin(make_village(is_active=True))
        assert ei.value.status_code == 400

    async def test_preview_purge_returns_cascade_refs(self, monkeypatch):
        monkeypatch.setattr("app.core.permission_utils.require_admin", lambda u: None)
        valley = make_village(is_active=False)
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: valley)
        cascade = MagicMock()
        cascade.return_value.check_village_references.return_value = {"records": 3}
        monkeypatch.setattr(
            "app.services.village_cascade_delete_service.VillageCascadeDeleteService",
            cascade,
        )
        db = MagicMock()
        resp = await sv.preview_purge_village(
            1, current_user=SimpleNamespace(id=1, role="admin"), db=db
        )
        assert resp["data"]["id"] == 1
        assert resp["data"]["records"] == 3

    async def test_restore_village_reactivates(self, monkeypatch):
        monkeypatch.setattr("app.core.permission_utils.require_admin", lambda u: None)
        valley = make_village(is_active=False, deleted_at="2024-01-01")
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: valley)

        async def _noop():
            return None

        monkeypatch.setattr(sv, "_invalidate_village_cache", _noop)
        monkeypatch.setattr(sv, "_record_village_change", MagicMock())
        monkeypatch.setattr(sv, "submit_entity_change_approval", lambda *a, **k: 11)
        db = MagicMock()
        resp = await sv.restore_village(
            1, current_user=SimpleNamespace(id=1, role="admin"), db=db
        )
        assert resp["data"]["approval_task_id"] == 11
        assert valley.is_active is True
        assert valley.deleted_at is None

    async def test_purge_village_success(self, monkeypatch):
        monkeypatch.setattr("app.core.permission_utils.require_admin", lambda u: None)
        monkeypatch.setattr("app.core.security.verify_password", lambda *a, **k: True)
        valley = make_village(is_active=False)
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: valley)
        cascade = MagicMock()
        cascade.return_value.delete_village_cascade.return_value = {
            "success": True, "deleted_records": 5, "details": {"x": 1},
        }
        monkeypatch.setattr(
            "app.services.village_cascade_delete_service.VillageCascadeDeleteService",
            cascade,
        )
        monkeypatch.setattr("app.utils.audit_logger.AuditLogger.log", MagicMock())
        monkeypatch.setattr(
            "app.services.immediate_backup.trigger_immediate_backup", MagicMock()
        )

        async def _noop():
            return None

        monkeypatch.setattr(sv, "_invalidate_village_cache", _noop)
        db = MagicMock()
        resp = await sv.purge_village(
            1, data=sv.PurgeRequest(confirm_password="pw"),
            current_user=SimpleNamespace(id=1, role="admin", username="admin"), db=db,
        )
        assert resp["data"]["deleted_records"] == 5

    async def test_purge_village_wrong_password_raises(self, monkeypatch):
        monkeypatch.setattr("app.core.permission_utils.require_admin", lambda u: None)
        monkeypatch.setattr("app.core.security.verify_password", lambda *a, **k: False)
        db = MagicMock()
        with pytest.raises(HTTPException) as ei:
            await sv.purge_village(
                1, data=sv.PurgeRequest(confirm_password="bad"),
                current_user=SimpleNamespace(id=1, role="admin"), db=db,
            )
        assert ei.value.status_code == 400

    async def test_purge_village_cascade_failure_raises_404(self, monkeypatch):
        monkeypatch.setattr("app.core.permission_utils.require_admin", lambda u: None)
        monkeypatch.setattr("app.core.security.verify_password", lambda *a, **k: True)
        monkeypatch.setattr(sv, "_get_village_or_404",
                            lambda *a, **k: make_village(is_active=False))
        cascade = MagicMock()
        cascade.return_value.delete_village_cascade.return_value = {
            "success": False, "message": "级联删除失败",
        }
        monkeypatch.setattr(
            "app.services.village_cascade_delete_service.VillageCascadeDeleteService",
            cascade,
        )
        db = MagicMock()
        with pytest.raises(HTTPException) as ei:
            await sv.purge_village(
                1, data=sv.PurgeRequest(confirm_password="pw"),
                current_user=SimpleNamespace(id=1, role="admin"), db=db,
            )
        assert ei.value.status_code == 404


# ==================== 年度数据校验 ====================


class TestValidateYearlyData:
    async def test_year_zero_skips_yoy_warning(self, monkeypatch):
        # 1200->1229：year 不满足 >0，跳过同比预警
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: MagicMock())
        db = MagicMock()
        db.query.return_value = q(first=None)  # 所有板块当年均无数据
        resp = await sv.validate_yearly_data(
            1, 0, current_user=SimpleNamespace(id=1), db=db
        )
        assert resp["data"]["warnings"] == []
        assert resp["data"]["valid"] is False
        assert len(resp["data"]["errors"]) == len(sv._SECTION_MODEL)

    async def test_small_yoy_change_no_warning(self, monkeypatch):
        # 1221->1216：同比变动在 ±50% 内不产生预警
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: MagicMock())
        sections = list(sv._SECTION_MODEL.values())
        cur_records = []
        prev_records = []
        for model in sections:
            if model is VillagePopulation:
                cur_records.append(record_for(model, total_population=101))
                prev_records.append(record_for(model, total_population=100))
            else:
                cur_records.append(record_for(model))
                prev_records.append(record_for(model))
        db = MagicMock()
        db.query.side_effect = (
            [q(first=r) for r in cur_records] + [q(first=r) for r in prev_records]
        )
        resp = await sv.validate_yearly_data(
            1, 2024, current_user=SimpleNamespace(id=1), db=db
        )
        assert resp["data"]["warnings"] == []

    async def test_large_yoy_change_produces_warning(self, monkeypatch):
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: MagicMock())
        sections = list(sv._SECTION_MODEL.values())
        cur_records, prev_records = [], []
        for model in sections:
            if model is VillagePopulation:
                cur_records.append(record_for(model, total_population=300))
                prev_records.append(record_for(model, total_population=100))
            else:
                cur_records.append(record_for(model))
                prev_records.append(record_for(model))
        db = MagicMock()
        db.query.side_effect = (
            [q(first=r) for r in cur_records] + [q(first=r) for r in prev_records]
        )
        resp = await sv.validate_yearly_data(
            1, 2024, current_user=SimpleNamespace(id=1), db=db
        )
        assert any("同比变动" in w["message"] for w in resp["data"]["warnings"])

    async def test_negative_value_produces_error(self, monkeypatch):
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: MagicMock())
        sections = list(sv._SECTION_MODEL.values())
        cur_records = [
            record_for(m, total_population=-5) if m is VillagePopulation else record_for(m)
            for m in sections
        ]
        db = MagicMock()
        db.query.side_effect = [q(first=r) for r in cur_records]
        resp = await sv.validate_yearly_data(
            1, 0, current_user=SimpleNamespace(id=1), db=db
        )
        assert resp["data"]["valid"] is False
        assert any("不能为负数" in e["message"] for e in resp["data"]["errors"])


# ==================== 标签映射 / 类型转换 ====================


class TestSectionLabelAndCoerce:
    def test_section_label_map_with_and_without_comment(self):
        model = fake_model([
            ("plain_col", None, String()),          # 无注释 → 1493->1500
            ("备注列", "（）", String()),             # 注释去括号后为空 → 1496->1498
            ("with_comment", "总户数（户）", Integer()),
        ])
        mapping = sv._section_label_map(model)
        assert mapping["plain_col"] == "plain_col"
        assert mapping["with_comment"] == "with_comment"
        assert mapping["总户数"] == "with_comment"
        # 空标签不产生空字符串键
        assert "" not in mapping

    def test_coerce_none_and_blank_return_none(self):
        model = fake_model([("cnt", "数量", Integer())])
        assert sv._coerce_section_value(model, "cnt", None) is None
        assert sv._coerce_section_value(model, "cnt", "   ") is None

    def test_coerce_unknown_column_returns_raw_value(self):
        model = fake_model([("cnt", "数量", Integer())])
        assert sv._coerce_section_value(model, "no_such", "raw") == "raw"

    def test_coerce_boolean(self):
        model = fake_model([("flag", "标记", Boolean())])
        assert sv._coerce_section_value(model, "flag", "是") is True
        assert sv._coerce_section_value(model, "flag", "no") is False

    def test_coerce_integer_and_float(self):
        model = fake_model([
            ("cnt", "数量", Integer()),
            ("amt", "金额", Float()),
        ])
        assert sv._coerce_section_value(model, "cnt", "12.0") == 12
        assert sv._coerce_section_value(model, "amt", "3.5") == 3.5

    def test_coerce_invalid_number_returns_none(self):
        model = fake_model([("cnt", "数量", Integer())])
        assert sv._coerce_section_value(model, "cnt", "不是数字") is None

    def test_coerce_string_fallback_strips(self):
        model = fake_model([("name", "名称", String())])
        assert sv._coerce_section_value(model, "name", "  值  ") == "值"
        assert sv._coerce_section_value(model, "name", 123) == 123


# ==================== 区块导入 ====================


class TestImportSectionSheet:
    def _model(self):
        return fake_model([
            ("total_population", "总人口", Integer()),
            ("total_households", "总户数", Integer()),
        ])

    def test_empty_sheet_returns_zero(self):
        # 1528->1529
        result = sv._import_section_sheet(FakeWS([]), self._model(), 1, 2024, MagicMock())
        assert result == {"imported": 0, "failed": 0}

    def test_header_not_found_marks_all_rows_failed(self):
        # 1546->1547
        ws = FakeWS([("无关", "列"), (1, 2), (3, 4)])
        result = sv._import_section_sheet(ws, self._model(), 1, 2024, MagicMock())
        assert result == {"imported": 0, "failed": 2}

    def test_blank_and_example_rows_skipped(self, monkeypatch):
        # 1552->1553 / 1554->1555 / 1560->1557
        save = MagicMock()
        monkeypatch.setattr(sv, "_save_section_data", save)
        ws = FakeWS([
            ("总人口", "总户数"),          # 表头（命中 ≥2 标签）
            (None, None),                   # 空行 → 跳过
            ("示例行", None),                # 示例行 → 跳过
            (None, 30),                     # coerced None 跳过 + 有值列入库
            (100, 20),                      # 正常行
        ])
        result = sv._import_section_sheet(ws, self._model(), 1, 2024, MagicMock())
        assert result["imported"] == 2
        assert result["failed"] == 0
        assert save.call_count == 2

    def test_row_without_valid_data_counts_failed(self, monkeypatch):
        # 1564->1565：整行无可转换数据 → failed
        monkeypatch.setattr(sv, "_save_section_data", MagicMock())
        ws = FakeWS([
            ("总人口", "总户数"),
            ("非数字", None),               # Integer 列转换失败 → data 为空
        ])
        result = sv._import_section_sheet(ws, self._model(), 1, 2024, MagicMock())
        assert result == {"imported": 0, "failed": 1}

    def test_header_scan_skips_none_cells(self, monkeypatch):
        # 1536->1537：表头候选行含空单元格时跳过该格
        save = MagicMock()
        monkeypatch.setattr(sv, "_save_section_data", save)
        ws = FakeWS([
            (None, "装饰列"),          # 空单元格 → continue（该行未命中表头）
            ("总人口", "总户数"),       # 真正的表头行
            (100, 20),
        ])
        result = sv._import_section_sheet(ws, self._model(), 1, 2024, MagicMock())
        assert result == {"imported": 1, "failed": 0}

    def test_save_error_counts_failed(self, monkeypatch):
        # 1570->1571：写库异常 → failed 计数
        monkeypatch.setattr(
            sv, "_save_section_data", MagicMock(side_effect=RuntimeError("db error"))
        )
        ws = FakeWS([
            ("总人口", "总户数"),
            (100, 20),
        ])
        result = sv._import_section_sheet(ws, self._model(), 1, 2024, MagicMock())
        assert result == {"imported": 0, "failed": 1}
