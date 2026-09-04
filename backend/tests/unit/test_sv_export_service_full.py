"""app.services.supported_village_export_service 覆盖补充测试（真实 SQLite 会话）。

覆盖 _query_villages（各过滤分支）、_collect_export_data、_collect_module_data
（config None / model None / fk None / year 过滤 / 去重）、_generate_statistics、
_coerce_cell（全类型分支）、_build_excel、_build_csv、export（xlsx + csv）。
"""
import datetime as _dt
import enum
from decimal import Decimal

import pytest

from app.models.supported_village import (
    SupportedVillage,
    VillageIncome,
    VillagePopulation,
)
from app.services.supported_village_export_service import (
    SupportedVillageExportService,
)


@pytest.fixture
def svc(real_db_session):
    return SupportedVillageExportService(real_db_session, current_user=None)


def _mkvillage(db, name, **kw):
    kw.setdefault("is_active", True)
    v = SupportedVillage(village_name=name, **kw)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


class TestQueryVillages:
    def test_filters(self, svc, real_db_session):
        v1 = _mkvillage(real_db_session, "甲村", county="A县", department="D1",
                        support_unit="U1", is_revitalization_tier=True)
        _mkvillage(real_db_session, "乙村", county="B县", is_revitalization_tier=False)
        assert len(svc._query_villages()) == 2
        assert len(svc._query_villages(keyword="甲")) == 1
        assert len(svc._query_villages(county="B县")) == 1
        assert len(svc._query_villages(is_revitalization_tier=True)) == 1
        assert len(svc._query_villages(village_ids=[v1.id])) == 1
        assert len(svc._query_villages(department="D1")) == 1
        assert len(svc._query_villages(support_unit="U1")) == 1

    def test_tiered_level_maps_to_bool(self, svc, real_db_session):
        _mkvillage(real_db_session, "示范村", is_revitalization_tier=True)
        _mkvillage(real_db_session, "基础村", is_revitalization_tier=False)
        assert len(svc._query_villages(tiered_level="示范级")) == 1
        assert len(svc._query_villages(tiered_level="基础级")) == 1

    def test_scope_filter_applied_when_user(self, real_db_session):
        _mkvillage(real_db_session, "村")
        user = object()
        svc = SupportedVillageExportService(real_db_session, current_user=user)
        with pytest.MonkeyPatch.context() as mp:
            import app.core.data_scope_adapter as dsa
            mp.setattr(dsa, "apply_scope_filter",
                       lambda q, u, m, db=None: q)
            assert len(svc._query_villages()) == 1

    def test_soft_deleted_excluded(self, svc, real_db_session):
        _mkvillage(real_db_session, "活跃村", is_active=True)
        _mkvillage(real_db_session, "删除村", is_active=False)
        names = [v.village_name for v in svc._query_villages()]
        assert "删除村" not in names


class TestCollectModuleData:
    def test_empty_villages(self, svc):
        assert svc._collect_module_data([], "population") == []

    def test_unknown_module_returns_basic(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "村X", county="C")
        out = svc._collect_module_data([v], "totally_unknown")
        assert out[0]["village_name"] == "村X"
        assert out[0]["module"] == "totally_unknown"

    def test_model_class_missing(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "村Y")
        svc._MODULE_CONFIG = {**SupportedVillageExportService._MODULE_CONFIG,
                              "fakemod": ("NoSuchModel", {})}
        out = svc._collect_module_data([v], "fakemod")
        assert out[0]["village_name"] == "村Y"

    def test_fk_column_missing(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "村Z")
        svc._MODULE_CONFIG = {**SupportedVillageExportService._MODULE_CONFIG,
                              "nofk": ("SupportedVillage", {})}
        out = svc._collect_module_data([v], "nofk")
        assert out[0]["village_name"] == "村Z"

    def test_population_with_year_and_dedup(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "人口村")
        # (supported_village_id, year) 唯一约束：同村同年只能一行，
        # setdefault 去重逻辑对每行执行即可覆盖
        real_db_session.add(
            VillagePopulation(supported_village_id=v.id, year=2024,
                              total_households=10, total_population=100,
                              labor_force=50),
        )
        real_db_session.commit()
        out = svc._collect_module_data([v], "population", year=2024)
        assert out[0]["households"] == 10
        assert out[0]["total_population"] == 100

    def test_module_without_year_field(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "收入村")
        real_db_session.add(VillageIncome(supported_village_id=v.id, year=2024,
                                          collective_income=5.5,
                                          per_capita_income=1.2))
        real_db_session.commit()
        out = svc._collect_module_data([v], "income", year=2024)
        assert out[0]["collective_income"] == 5.5

    def test_village_without_row_yields_none(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "空村")
        out = svc._collect_module_data([v], "population")
        assert out[0]["households"] is None

    def test_collect_export_data_default_modules(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "村")
        data = svc._collect_export_data([v])
        assert "population" in data and "income" in data

    def test_collect_export_data_specific_modules(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "村")
        data = svc._collect_export_data([v], modules=["population"])
        assert list(data.keys()) == ["population"]


class TestGenerateStatistics:
    def test_stats(self, svc):
        data = {"population": [{"a": 1}, {"a": 2}], "income": []}
        stats = svc._generate_statistics(data)
        assert stats["total_villages"] == 2
        assert stats["population_count"] == 2
        assert stats["income_count"] == 0
        assert set(stats["modules_exported"]) == {"population", "income"}


class TestCoerceCell:
    def test_all_types(self, svc):
        c = SupportedVillageExportService._coerce_cell
        assert c(None) is None
        assert c(True) is True
        assert c(5) == 5
        assert c(1.5) == 1.5
        assert c("s") == "s"
        d = _dt.datetime(2026, 1, 1)
        assert c(d) == d
        assert c(Decimal("3.14")) == 3.14

        class Color(enum.Enum):
            RED = "red"

        assert c(Color.RED) == "red"
        assert c(object())  # 兜底转字符串

    def test_date_and_time(self, svc):
        c = SupportedVillageExportService._coerce_cell
        assert c(_dt.date(2026, 1, 1)) == _dt.date(2026, 1, 1)
        assert c(_dt.time(12, 0)) == _dt.time(12, 0)


class TestBuildExcelAndCsv:
    def test_build_excel_with_and_without_rows(self, svc):
        data = {"population": [{"id": 1, "village_name": "村"}], "income": []}
        stats = {"total_villages": 1}
        content = svc._build_excel(data, stats)
        assert content.startswith(b"PK")  # xlsx zip 魔数

    def test_build_csv_first_nonempty_module(self, svc):
        data = {"population": [], "income": [{"id": 1, "collective_income": 5.5}]}
        content = svc._build_csv(data)
        assert b"collective_income" in content

    def test_build_csv_all_empty(self, svc):
        # utf-8-sig 对空字符串仍产出 BOM 头
        assert svc._build_csv({"population": []}) == b"\xef\xbb\xbf"


class TestExport:
    def test_export_xlsx(self, svc, real_db_session):
        v = _mkvillage(real_db_session, "导出村", county="C")
        real_db_session.add(VillagePopulation(supported_village_id=v.id, year=2024,
                                              total_households=3))
        real_db_session.commit()
        content, filename, stats = svc.export(modules=["population"])
        assert filename.endswith(".xlsx")
        assert content.startswith(b"PK")
        assert stats["total_villages"] >= 1

    def test_export_csv(self, svc, real_db_session):
        _mkvillage(real_db_session, "CSV村")
        content, filename, stats = svc.export(format="csv", modules=["population"])
        assert filename.endswith(".csv")
        assert isinstance(content, bytes)
