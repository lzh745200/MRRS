"""深审 #60/#61/#62/#63：smart_conflict_resolver 导入安全性修复回归。

- #60 时间比较：字符串/naive-vs-aware 不再抛 TypeError
- #61 setattr 白名单：非映射键与受保护列（id/organization_id/updated_at…）不被写入
- #62 KEEP_BOTH：外键经 id_mapping 重映射
- #63 租户收敛：organization_id 参与冲突检测 + 强制覆盖导入记录的租户列
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.smart_conflict_resolver import (
    ConflictStrategy,
    DataConflict,
    SmartConflictResolver,
    _to_datetime,
)
from app.models.project import Project  # noqa: F401 — 供 _model_columns 解析映射列


def _resolver(db=None, org_id=None):
    return SmartConflictResolver(db or MagicMock(), organization_id=org_id)


class TestToDatetime:
    def test_naive_datetime_gets_utc(self):
        dt = _to_datetime(datetime(2026, 1, 1))
        assert dt.tzinfo is timezone.utc

    def test_aware_datetime_preserved(self):
        dt = _to_datetime(datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert dt.tzinfo is not None

    def test_iso_string_with_z(self):
        assert _to_datetime("2026-01-01T00:00:00Z").year == 2026

    def test_iso_string_without_tz_treated_as_utc(self):
        assert _to_datetime("2026-01-01T00:00:00").tzinfo is timezone.utc

    @pytest.mark.parametrize("bad", [None, 123, "not-a-date", object()])
    def test_unparseable_returns_none(self, bad):
        assert _to_datetime(bad) is None


class TestImportIsNewerNoTypeError:
    """#60：naive vs aware / str vs datetime 混合比较不得抛 TypeError。"""

    def test_naive_string_vs_aware_datetime(self):
        local = SimpleNamespace(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        rec = {"updated_at": "2026-06-01T00:00:00"}  # naive 字符串
        assert _resolver()._import_is_newer(rec, local) is True

    def test_aware_datetime_vs_naive_datetime(self):
        local = SimpleNamespace(updated_at=datetime(2026, 1, 1))  # naive
        rec = {"updated_at": datetime(2026, 6, 1, tzinfo=timezone.utc)}  # aware
        assert _resolver()._import_is_newer(rec, local) is True

    @pytest.mark.parametrize("import_v,local_v", [
        ("garbage", datetime(2026, 1, 1)),
        (datetime(2026, 1, 1), "garbage"),
        (None, datetime(2026, 1, 1)),
    ])
    def test_unparseable_yields_false_not_raise(self, import_v, local_v):
        local = SimpleNamespace(updated_at=local_v)
        assert _resolver()._import_is_newer({"updated_at": import_v}, local) is False

    def test_merge_survives_mixed_time_types(self):
        """MERGE 分支在混合时间类型下不得中断（原实现会 TypeError）。"""
        local = SimpleNamespace(id=1, name="本地", updated_at=datetime(2026, 1, 1))
        rec = {"id": 9, "code": "C1", "name": "导入", "updated_at": "2026-06-01T00:00:00"}
        conflict = DataConflict("projects", {"code": "C1"}, local, rec, ["name"])

        out = _resolver().resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)

        assert out == {"projects": {9: 1}}
        assert local.name == "导入"  # 导入更新 → 覆盖


class TestWritableItemsFilter:
    """#61：只写模型真实列，排除受保护列。"""

    def test_protected_columns_excluded(self):
        rec = {
            "id": 9, "code": "C1", "name": "X",
            "organization_id": 999, "created_at": "2020-01-01",
            "updated_at": "2020-01-01", "created_by": 7, "updated_by": 8,
        }
        items = dict(_resolver()._writable_items(Project, rec))
        assert "code" in items and "name" in items
        for banned in ("id", "organization_id", "created_at", "updated_at", "created_by", "updated_by"):
            assert banned not in items

    def test_non_column_keys_excluded(self):
        """扁平化/派生键（如 village_name_flat、_imported_at）不得进入模型 kwargs。"""
        rec = {"code": "C1", "name": "X", "village_code": "V1", "totally_bogus": 1}
        items = dict(_resolver()._writable_items(Project, rec))
        assert "totally_bogus" not in items
        assert "village_code" not in items

    def test_overwrite_does_not_touch_organization_id(self):
        """OVERWRITE 不得把本地记录改到别的组织（越权写）。"""
        local = SimpleNamespace(id=1, name="本地", organization_id=5)
        rec = {"id": 9, "code": "C1", "name": "导入", "organization_id": 999}
        conflict = DataConflict("projects", {"code": "C1"}, local, rec, ["name"])

        _resolver().resolve_conflicts_with_strategy([conflict], ConflictStrategy.OVERWRITE)

        assert local.name == "导入"
        assert local.organization_id == 5  # 未被覆盖

    def test_overwrite_ignores_bogus_key(self):
        local = SimpleNamespace(id=1, name="本地")
        rec = {"id": 9, "code": "C1", "name": "导入", "bogus": "x"}
        conflict = DataConflict("projects", {"code": "C1"}, local, rec, ["name"])

        _resolver().resolve_conflicts_with_strategy([conflict], ConflictStrategy.OVERWRITE)

        assert not hasattr(local, "bogus")


class TestKeepBothForeignKeyRemap:
    """#62：KEEP_BOTH 新行外键必须重映射到本机 ID。"""

    def test_fund_project_id_remapped(self):
        db = MagicMock()
        db.add.side_effect = lambda obj: setattr(obj, "id", 555)

        local = SimpleNamespace(id=1, code="F1")
        rec = {"id": 9, "code": "F1", "name": "经费", "project_id": 77}
        conflict = DataConflict("funds", {"code": "F1"}, local, rec, ["name"])

        r = SmartConflictResolver(db)
        # 预置既有映射：projects 源 id 77 → 本机 777
        mapping = {"projects": {77: 777}, "funds": {}}
        r._keep_both(conflict, mapping)

        assert mapping["funds"] == {9: 555}
        created = db.add.call_args_list[0][0][0]
        assert created.project_id == 777  # 已重映射，不再是 77

    def test_unmapped_fk_untouched(self):
        """id_mapping 中没有该源 id 时保持原值（不臆造映射）。"""
        db = MagicMock()
        db.add.side_effect = lambda obj: setattr(obj, "id", 1)
        local = SimpleNamespace(id=1, code="F1")
        rec = {"id": 9, "code": "F1", "project_id": 77}
        conflict = DataConflict("funds", {"code": "F1"}, local, rec, ["name"])

        SmartConflictResolver(db)._keep_both(conflict, {})
        assert db.add.call_args_list[0][0][0].project_id == 77

    def test_remap_via_real_import_order(self):
        """端到端：先导入 villages/projects，再以 KEEP_BOTH 导入同 code 的 funds。"""
        db = MagicMock()
        seq = iter([101, 202, 303])
        db.add.side_effect = lambda obj: setattr(obj, "id", next(seq))
        db.flush = MagicMock()
        # 所有业务键查询 miss → 全部走"新记录"路径，旧 id 被记录进 id_mapping
        db.query.return_value.filter.return_value.first.return_value = None

        r = SmartConflictResolver(db)
        data = {
            "villages": [{"id": 1, "village_name": "V", "name": "V"}],
            "projects": [{"id": 2, "code": "P", "name": "P", "village_id": 1}],
            "funds": [{"id": 3, "code": "F", "name": "F", "project_id": 2}],
        }
        mapping = r.import_with_id_mapping(data, ConflictStrategy.SKIP)

        assert mapping["villages"] == {1: 101}
        assert mapping["projects"] == {2: 202}
        assert mapping["funds"] == {3: 303}
        # funds 的 project_id 已从源 2 重映射到本机 202
        funds_obj = db.add.call_args_list[2][0][0]
        assert funds_obj.project_id == 202


class TestTenantScoping:
    """#63：organization_id 参与冲突检测，且导入记录租户列被强制覆盖。"""

    def test_tenant_condition_added_to_query(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        SmartConflictResolver(db, organization_id=42).detect_conflicts_by_business_key(
            [{"code": "C1", "name": "X"}], "projects"
        )

        # filter(*conditions) → 只有一个组合条件，编译成 SQL 后应含 organization_id
        cond = db.query.return_value.filter.call_args.args[0]
        assert "organization_id" in str(cond.compile(compile_kwargs={"literal_binds": True}))

    def test_no_tenant_condition_when_org_is_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        SmartConflictResolver(db).detect_conflicts_by_business_key(
            [{"code": "C1", "name": "X"}], "projects"
        )

        cond = db.query.return_value.filter.call_args.args[0]
        assert "organization_id" not in str(cond.compile(compile_kwargs={"literal_binds": True}))

    def test_import_forces_tenant_column(self):
        db = MagicMock()
        r = SmartConflictResolver(db, organization_id=42)
        r.detect_conflicts_by_business_key = MagicMock(
            return_value=MagicMock(new_records=[], conflict_records=[], no_conflict_records=[])
        )
        data = {"projects": [{"id": 1, "code": "C1", "organization_id": 999}]}

        r.import_with_id_mapping(data, ConflictStrategy.SKIP)

        assert data["projects"][0]["organization_id"] == 42

    def test_tenant_preserved_when_not_configured(self):
        db = MagicMock()
        r = SmartConflictResolver(db)
        r.detect_conflicts_by_business_key = MagicMock(
            return_value=MagicMock(new_records=[], conflict_records=[], no_conflict_records=[])
        )
        data = {"projects": [{"id": 1, "code": "C1", "organization_id": 999}]}

        r.import_with_id_mapping(data, ConflictStrategy.SKIP)

        assert data["projects"][0]["organization_id"] == 999


class TestAutoStrategyMixedTypes:
    """#60：AUTO 决策在混合时间类型下退回 MERGE 而非抛异常。"""

    def test_auto_with_unparseable_timestamps_merges(self):
        local = SimpleNamespace(id=1, name="本地", updated_at="garbage")
        rec = {"id": 9, "code": "C1", "name": "导入", "updated_at": "also-bad"}
        conflict = DataConflict("projects", {"code": "C1"}, local, rec, ["name", "type", "budget"])

        out = _resolver().resolve_conflicts_with_strategy([conflict], ConflictStrategy.AUTO)
        assert out == {"projects": {9: 1}}


class TestImportNewRecordsFiltering:
    """#61 延伸到 _import_new_records（新记录插入路径）。"""

    def test_bogus_keys_do_not_reach_model_kwargs(self):
        """用 Project 的真实映射列做过滤，但以替身承接实例化以捕获 kwargs。

        替身必须让 `_model_columns` 仍解析到 **Project** 的列集合，
        故直接 patch `_writable_items` 之外的最短路径：patch DATA_TYPE_MODELS
        指向一个带上 Project 列集的探针。
        """
        db = MagicMock()
        r = SmartConflictResolver(db)
        captured = {}

        real_cols = {c.key for c in Project.__mapper__.column_attrs}

        class _Probe:
            __mapper__ = Project.__mapper__  # 让 _model_columns 拿到真实列集

            def __init__(self, **kwargs):
                captured.update(kwargs)

            def __getattr__(self, name):
                return 1

        with patch.dict(
            "app.services.smart_conflict_resolver.DATA_TYPE_MODELS",
            {"projects": _Probe},
        ):
            r._import_new_records(
                [{"id": 1, "code": "C1", "name": "X", "bogus_key": "y", "organization_id": 9}],
                "projects",
                {},
            )

        assert real_cols  # 前置断言：确实解析到了列集
        assert "bogus_key" not in captured
        assert "organization_id" not in captured
        assert captured["code"] == "C1"
