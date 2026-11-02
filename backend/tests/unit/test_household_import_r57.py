"""一户一档表格导入（R57）——模板/校验/写入端到端。"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.household import Household
from app.models.import_history import ImportMode
from app.models.organization import Organization
from app.models.supported_village import SupportedVillage
from app.models.user import User
from app.services.excel_importer_service import ExcelImporterService
from app.services.excel_template_service import ExcelTemplateService
from app.services.entity_import_validator import EntityImportValidator

HEADERS = [
    "帮扶村名称",
    "县/市",
    "乡镇",
    "户编号",
    "户主姓名",
    "户类型",
    "风险类型",
    "风险等级",
    "联系电话",
    "年收入(元)",
    "大病",
    "住房安全",
    "最近走访日期",
]


def _workbook(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def ctx(db):
    org = Organization(name="测试县", code="T001", is_active=True, path="/1")
    other = Organization(name="其他县", code="T002", is_active=True, path="/2")
    db.add_all([org, other])
    db.flush()
    user = User(
        username="admin",
        hashed_password="x",
        role="admin",
        is_superuser=False,
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.flush()
    village = SupportedVillage(
        village_name="测试村", county="测试县", township="测试镇",
        organization_id=org.id, is_active=True,
    )
    other_village = SupportedVillage(
        village_name="测试村", county="其他县", township="其他镇",
        organization_id=other.id, is_active=True,
    )
    db.add_all([village, other_village])
    db.commit()
    actor = SimpleNamespace(id=user.id, organization_id=org.id, role="admin", is_superuser=False)
    return SimpleNamespace(db=db, org=org, other=other, user=user, village=village,
                           other_village=other_village, actor=actor,
                           svc=ExcelImporterService(db, current_user=actor))


def _run(ctx, rows):
    content = _workbook(rows)
    return ctx.svc.import_data(
        content, "households.xlsx", len(content), ctx.user.id,
        ImportMode.INCREMENTAL, "household",
    )


def test_template_and_validator_declare_household():
    content = ExcelTemplateService().generate_household_template()
    assert content
    validator = EntityImportValidator("household")
    assert validator.get_required_fields() == ["village_name", "household_name"]
    assert validator.config["duplicate_key"] == "household_code"


def test_import_household_success_and_defaults(ctx):
    result = _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三", "脱贫户", "因病", "中",
                         "13800138000", 12000, "否", "是", "2026-10-01"]])
    assert result.success is True
    assert result.success_rows == 1
    household = ctx.db.query(Household).one()
    assert household.household_name == "张三"
    assert household.household_type == "poverty"
    assert household.risk_type == "illness"
    assert household.risk_level == "medium"
    assert household.housing_safe is True
    assert household.helper_phone == "13800138000"


def test_import_household_defaults_housing_safe_true_when_blank(ctx):
    result = _run(ctx, [["测试村", "测试县", "测试镇", "H002", "李四"]])
    assert result.success is True
    assert ctx.db.query(Household).one().housing_safe is True


def test_import_household_missing_village_records_row_error(ctx):
    result = _run(ctx, [["不存在村", "", "", "", "王五"]])
    assert result.success is False
    assert result.failed_rows == 1
    assert "未找到帮扶村" in result.errors[0].message


def test_import_household_ambiguous_village_requires_county(ctx):
    # 两个组织都有“测试村”，仅填村名应判定不唯一（外组织会被可达性过滤后仍剩本组织）
    result = _run(ctx, [["测试村", "", "", "", "王五"]])
    assert result.success is True  # 本组织只有一个可达的“测试村”
    # 本组织再建同名村 → 不唯一
    ctx.db.add(SupportedVillage(village_name="测试村", county="测试县", township="另一镇",
                                organization_id=ctx.org.id, is_active=True))
    ctx.db.commit()
    result = _run(ctx, [["测试村", "", "", "", "赵六"]])
    assert result.success is False
    assert "不唯一" in result.errors[0].message


def test_import_household_incremental_skips_duplicate_code(ctx):
    first = _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    assert first.success is True
    second = _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    assert second.success is True
    assert second.skipped_rows == 1
    assert ctx.db.query(Household).count() == 1


def test_import_household_full_mode_soft_deletes_previous(ctx):
    _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    content = _workbook([["测试村", "测试县", "测试镇", "H002", "李四"]])
    result = ctx.svc.import_data(
        content, "households.xlsx", len(content), ctx.user.id,
        ImportMode.FULL, "household",
    )
    assert result.success is True
    rows = ctx.db.query(Household).all()
    assert len(rows) == 2
    assert sum(1 for row in rows if row.is_active) == 1


def test_import_household_database_error_is_row_level(ctx, monkeypatch):
    original_flush = ctx.db.flush

    def boom(*args, **kwargs):
        if any(isinstance(obj, Household) for obj in ctx.db.new):
            raise RuntimeError("flush failed")
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(ctx.db, "flush", boom)
    result = _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    assert result.success is False
    assert result.failed_rows == 1
    assert "创建一户一档失败" in result.errors[0].message


def test_full_mode_empty_file_does_not_soft_delete_existing(ctx):
    _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    before = ctx.db.query(Household).filter(Household.is_active.is_(True)).count()
    empty = _workbook([])
    result = ctx.svc.import_data(
        empty, "empty.xlsx", len(empty), ctx.user.id, ImportMode.FULL, "household"
    )
    assert result.success is False
    assert result.total_rows == 0
    after = ctx.db.query(Household).filter(Household.is_active.is_(True)).count()
    assert after == before


def test_full_mode_partial_failure_rolls_back_soft_delete(ctx):
    _run(ctx, [["测试村", "测试县", "测试镇", "H001", "张三"]])
    before_ids = {h.id for h in ctx.db.query(Household).all()}
    content = _workbook([
        ["测试村", "测试县", "测试镇", "H002", "李四"],
        ["不存在村", "", "", "H003", "王五"],
    ])
    result = ctx.svc.import_data(
        content, "partial.xlsx", len(content), ctx.user.id, ImportMode.FULL, "household"
    )
    assert result.success is False
    assert result.success_rows == 0
    assert ctx.db.query(Household).count() == len(before_ids)
    assert ctx.db.query(Household).filter(Household.is_active.is_(True)).count() == len(before_ids)


def test_same_code_in_different_villages_is_allowed(ctx):
    ctx.db.add(SupportedVillage(village_name="另一村", county="测试县", township="测试镇",
                                organization_id=ctx.org.id, is_active=True))
    ctx.db.commit()
    result = _run(ctx, [
        ["测试村", "测试县", "测试镇", "H001", "张三"],
        ["另一村", "测试县", "测试镇", "H001", "李四"],
    ])
    assert result.success is True
    assert result.success_rows == 2
    assert ctx.db.query(Household).count() == 2
