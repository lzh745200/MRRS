"""汇报大屏 API（/bigscreen/filters + /bigscreen/overview）测试。

覆盖：
- filters：村/学校/单位三路数据域过滤、软删排除、单位四路并集与同名合并计数；
- overview：全局 / 村 / 学校 / 单位四种维度的 KPI、趋势、状态、排行、人物榜、
  对象档案（sections/tags）与明细结构；
- 数据域隔离（管理員 vs 组织 2 受限用户）、404（对象不存在/越权/软删）、
  400（非法维度/缺 ID/单位空名）、空库、未知状态/阶段回退、year 为空跳过、
  排序与金额口径、filters 查询异常 500 分支。
"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _user(**kw):
    base = dict(id=7, username="admin7", role="admin", organization_id=1, data_scope="all")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def api_client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base
    from app.models.user import User  # noqa: F401  FK 目标表注册
    from app.models.organization import Organization  # noqa: F401
    from app.models.supported_village import SupportedVillage  # noqa: F401
    from app.models.school import School  # noqa: F401
    from app.models.project import Project  # noqa: F401
    from app.models.fund import Fund  # noqa: F401
    from app.models.pairing import PairingRecord, VisitRecord  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    state = {"user": _user()}

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, session, state
    finally:
        app.dependency_overrides = original_overrides
        session.close()
        engine.dispose()


def _as(state, **kw):
    state["user"] = _user(**kw)


# ════════════════════════════════════════════════════════════════════
#  造数工具
# ════════════════════════════════════════════════════════════════════

def _mk_village(db, name="幸福村", org_id=1, created_by=7, active=True, **kw):
    from app.models.supported_village import SupportedVillage

    base = dict(
        village_name=name,
        organization_id=org_id,
        created_by=created_by,
        is_active=active,
        province="贵州省",
    )
    base.update(kw)
    row = SupportedVillage(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_school(db, name="希望小学", org_id=1, created_by=7, active=True, **kw):
    from app.models.school import School

    base = dict(
        name=name,
        organization_id=org_id,
        created_by=created_by,
        is_active=active,
        province="贵州省",
    )
    base.update(kw)
    row = School(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_project(db, name="项目一", **kw):
    from app.models.project import Project

    base = dict(
        name=name,
        organization_id=1,
        is_active=True,
        status="completed",
        actual_cost=0,
    )
    base.update(kw)
    row = Project(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_fund(db, amount=0, **kw):
    from app.models.fund import Fund

    base = dict(amount=amount, organization_id=1, is_active=True, status="approved")
    base.update(kw)
    row = Fund(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_pairing(db, **kw):
    from app.models.pairing import PairingRecord

    base = dict(
        subject_type="unit",
        subject_name="某部队单位",
        partner_type="village",
        title="结对事项",
        status="active",
        organization_id=1,
        created_by=7,
        is_active=True,
    )
    base.update(kw)
    row = PairingRecord(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_visit(db, pairing_id, **kw):
    from app.models.pairing import VisitRecord

    base = dict(
        pairing_id=pairing_id,
        visit_date=date(2026, 3, 1),
        visitors="甲",
        organization_id=1,
        created_by=7,
        is_active=True,
    )
    base.update(kw)
    row = VisitRecord(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_school_project(db, school_id, name="助学项目", **kw):
    from app.models.school import SchoolProject

    base = dict(school_id=school_id, name=name)
    base.update(kw)
    row = SchoolProject(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_scholarship(db, school_id, amount=0, **kw):
    from app.models.school import ScholarshipStudent

    base = dict(school_id=school_id, student_name="受助学生", amount=amount)
    base.update(kw)
    row = ScholarshipStudent(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_population(db, village_id, year, **kw):
    from app.models.supported_village import VillagePopulation

    row = VillagePopulation(supported_village_id=village_id, year=year, **kw)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_income(db, village_id, year, **kw):
    from app.models.supported_village import VillageIncome

    row = VillageIncome(supported_village_id=village_id, year=year, **kw)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mk_support(db, model, village_id, year, **kw):
    row = model(supported_village_id=village_id, year=year, **kw)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _seed(db):
    """主数据集：6 个有效村（另 1 个软删）+ 3 所学校（另 1 个软删）+ 项目/经费/结对。"""
    from app.models.school import ProjectPhase, SupportStatus
    from app.models.supported_village import (
        EducationSupport,
        IndustrySupport,
        InfrastructureImprovement,
        PartyBuildingSupport,
    )

    ns = SimpleNamespace()

    # ── 帮扶村 ──
    ns.v1 = _mk_village(
        db,
        name="幸福村",
        org_id=1,
        city="遵义市",
        county="桐梓县",
        township="花秋镇",
        support_unit="某部队单位",
        department="政治工作处",
        is_revitalization_tier=True,
        is_three_regions=True,
        is_ethnic_area=True,
        transition_status="in_transition",
        transition_fund_military_total=120.456,
        transition_fund_local_total=80.0,
    )
    ns.v2 = _mk_village(
        db,
        name="光明村",
        org_id=2,
        created_by=8,
        city="贵阳市",
        county="息烽县",
        support_unit="另一单位",
    )
    ns.v3 = _mk_village(db, name="已删村", org_id=1, active=False)
    ns.v4 = _mk_village(db, name="收入村", org_id=1, support_unit=None)
    ns.v5 = _mk_village(db, name="人口村", org_id=1)
    ns.v6 = _mk_village(db, name="空村", org_id=1)

    # ── 人口 / 收入 ──
    _mk_population(
        db,
        ns.v1.id,
        2024,
        total_population=1200,
        total_households=300,
        resident_population=900,
        poverty_population=120,
    )
    _mk_population(
        db,
        ns.v1.id,
        2025,
        total_population=1300,
        total_households=320,
        resident_population=1000,
        poverty_population=110,
    )
    _mk_income(db, ns.v1.id, 2025, per_capita_income=1.8512, collective_income=12.5)
    _mk_income(db, ns.v4.id, 2023, per_capita_income=1.2, collective_income=3.3)
    _mk_population(
        db,
        ns.v5.id,
        2022,
        total_population=1,
        total_households=10,
        resident_population=5,
        poverty_population=1,
    )
    # 历史脏数据：总人口为 NULL（ORM 写入会触发列默认值 0，故用参数化 UPDATE 模拟）
    from sqlalchemy import text

    db.execute(
        text("UPDATE village_population SET total_population = NULL WHERE supported_village_id = :vid"),
        {"vid": ns.v5.id},
    )
    db.commit()

    # ── 帮扶投入子表（v1：最新 2025；基础设施仅 2024，医疗缺失）──
    _mk_support(db, IndustrySupport, ns.v1.id, 2025, investment=30.0)
    _mk_support(db, InfrastructureImprovement, ns.v1.id, 2024, investment=20.0)
    _mk_support(db, PartyBuildingSupport, ns.v1.id, 2025)
    _mk_support(db, EducationSupport, ns.v1.id, 2025, investment=5.5)

    # ── 帮扶学校 ──
    ns.s1 = _mk_school(
        db,
        name="希望小学",
        org_id=1,
        city="遵义市",
        district="桐梓县",
        support_unit="某部队单位",
        student_count=320,
        teacher_count=24,
        class_count=8,
        established_year=1998,
        support_status=SupportStatus.ACTIVE,
        support_start_date=datetime(2022, 1, 1),
        support_end_date=None,
    )
    ns.s2 = _mk_school(
        db,
        name="育才中学",
        org_id=2,
        created_by=8,
        city="贵阳市",
        district="息烽县",
        student_count=100,
        teacher_count=10,
        class_count=3,
        support_status=SupportStatus.COMPLETED,
        support_start_date=datetime(2023, 1, 1),
        support_end_date=datetime(2024, 1, 1),
    )
    ns.s3 = _mk_school(db, name="已删学校", org_id=1, active=False)
    ns.s4 = _mk_school(db, name="结对小学", org_id=1)

    # ── 项目 ──
    ns.p1 = _mk_project(
        db,
        name="修路项目",
        village_id=ns.v1.id,
        responsible_unit="某部队单位",
        responsible_person="张干事",
        status="completed",
        actual_cost=500.5,
        start_date=date(2024, 3, 1),
    )
    ns.p2 = _mk_project(
        db,
        name="饮水项目",
        village_id=ns.v1.id,
        responsible_unit="某部队单位",
        leader="李科长",
        status="in_progress",
        actual_cost=300,
        start_date=None,
    )
    ns.p3 = _mk_project(
        db,
        name="助学项目",
        village_id=ns.v2.id,
        organization_id=2,
        responsible_unit="另一单位",
        responsible_person="王助理",
        status="approved",
        actual_cost=200,
        start_date=date(2023, 5, 1),
    )
    ns.p4 = _mk_project(
        db,
        name="历史项目",
        village_id=ns.v1.id,
        responsible_unit="某部队单位",
        status="archived",
        actual_cost=50,
        start_date=date(2025, 2, 1),
    )
    ns.p5 = _mk_project(
        db,
        name="已取消项目",
        village_id=ns.v1.id,
        responsible_unit="某部队单位",
        status="cancelled",
        actual_cost=999,
        start_date=date(2024, 1, 1),
    )
    ns.p6 = _mk_project(
        db,
        name="已删项目",
        village_id=ns.v1.id,
        responsible_unit="某部队单位",
        is_active=False,
        status="completed",
        actual_cost=888,
        start_date=date(2024, 1, 1),
    )
    ns.p7 = _mk_project(
        db,
        name="第三单位项目",
        village_id=None,
        responsible_unit="第三单位",
        status="pending",
        actual_cost=100,
        start_date=date(2023, 7, 1),
    )

    # ── 经费 ──
    ns.f1 = _mk_fund(
        db,
        amount=100,
        planned_amount=120,
        allocated_amount=110,
        village_id=ns.v1.id,
        status="allocated",
        name="修路资金",
        date=date(2024, 6, 1),
    )
    ns.f2 = _mk_fund(
        db,
        amount=50,
        planned_amount=60,
        allocated_amount=55,
        village_id=ns.v1.id,
        status="pending",
        name="助学资金",
        date=date(2025, 1, 1),
    )
    ns.f3 = _mk_fund(
        db,
        amount=25,
        village_id=ns.v1.id,
        status="mystery",
        name=None,
        date=None,
        application_date=None,
    )
    ns.f4 = _mk_fund(db, amount=999, village_id=ns.v1.id, is_active=False, date=date(2024, 1, 1))
    ns.f5 = _mk_fund(
        db,
        amount=88.8,
        planned_amount=90,
        allocated_amount=88.8,
        school_id=ns.s1.id,
        status="completed",
        name="学校修缮",
        date=date(2024, 9, 1),
    )
    ns.f6 = _mk_fund(db, amount=999, status="approved", date=date(2023, 1, 1))
    ns.f7 = _mk_fund(
        db,
        amount=12,
        project_id=ns.p1.id,
        status="approved",
        name="项目经费",
        date=date(2025, 3, 1),
    )
    ns.f8 = _mk_fund(
        db,
        amount=7.5,
        planned_amount=8,
        allocated_amount=7.5,
        village_id=ns.v4.id,
        status="planned",
        name="收入村经费",
        date=date(2025, 5, 1),
    )
    ns.f10 = _mk_fund(
        db,
        amount=33,
        project_id=ns.p7.id,
        status="approved",
        name="第三单位项目经费",
        date=date(2023, 8, 1),
    )

    # ── 结对 / 走访 ──
    ns.pr1 = _mk_pairing(db, subject_name="某部队单位", partner_type="village", village_id=ns.v1.id)
    ns.pr2 = _mk_pairing(
        db,
        subject_name="某部队单位",
        partner_type="school",
        school_id=ns.s1.id,
        status="ended",
        title="助学",
    )
    ns.pr3 = _mk_pairing(
        db,
        subject_name="另一单位",
        partner_type="village",
        village_id=ns.v2.id,
        organization_id=2,
        created_by=8,
    )
    ns.pr4 = _mk_pairing(
        db,
        subject_type="person",
        subject_name="王五",
        partner_type="village",
        village_id=ns.v1.id,
        status="ended",
        title="干部结对",
    )
    ns.pr5 = _mk_pairing(
        db,
        subject_name="某部队单位",
        partner_type="student",
        student_name="张三",
        title="助学结对",
    )
    ns.pr6 = _mk_pairing(
        db,
        subject_name="已删单位",
        partner_type="village",
        village_id=ns.v1.id,
        is_active=False,
    )
    ns.pr7 = _mk_pairing(db, subject_name="结对单位", partner_type="village", village_id=ns.v4.id)
    ns.pr8 = _mk_pairing(
        db,
        subject_name="助学单位",
        partner_type="school",
        school_id=ns.s1.id,
        title="学校结对",
    )
    ns.pr9 = _mk_pairing(db, subject_name="", partner_type="village", village_id=ns.v1.id)

    _mk_visit(db, ns.pr1.id)
    _mk_visit(db, ns.pr1.id)
    _mk_visit(db, ns.pr4.id)
    _mk_visit(db, ns.pr2.id)
    _mk_visit(db, ns.pr1.id, is_active=False)
    _mk_visit(db, ns.pr3.id, organization_id=2, created_by=8)
    _mk_visit(db, ns.pr5.id)

    # ── 资助学生 ──
    _mk_scholarship(db, ns.s1.id, amount=500.0, year=2024)
    _mk_scholarship(db, ns.s1.id, amount=300.5, year=2025)

    # ── 学校项目 ──
    ns.sp1 = _mk_school_project(
        db,
        ns.s1.id,
        name="教学楼改造",
        phase=ProjectPhase.IMPLEMENTATION,
        budget=200,
        actual_cost=150,
        category="基建",
        start_date=datetime(2024, 6, 1),
    )
    ns.sp2 = _mk_school_project(
        db,
        ns.s1.id,
        name="图书捐赠",
        phase=ProjectPhase.ACCEPTANCE,
        budget=20,
        actual_cost=18,
        category=None,
        start_date=datetime(2025, 2, 1),
    )
    ns.sp3 = _mk_school_project(
        db,
        ns.s1.id,
        name="未知阶段项目",
        phase=ProjectPhase.RESEARCH,
        budget=0,
        actual_cost=5,
        category="其他",
        start_date=None,
    )
    ns.sp4 = _mk_school_project(
        db,
        ns.s1.id,
        name="未设置阶段项目",
        phase=ProjectPhase.COMPLETED,
        budget=0,
        actual_cost=0,
        category=None,
        start_date=datetime(2023, 2, 1),
    )
    # 未知阶段（历史脏值）与空阶段：ORM 写入会触发枚举默认值/回读异常，
    # 故先用合法值入库，再以参数化 UPDATE 模拟历史脏数据
    ns.sp4b = _mk_school_project(
        db,
        ns.s1.id,
        name="未知脏值项目",
        phase=ProjectPhase.RESEARCH,
        budget=0,
        actual_cost=2,
        category=None,
        start_date=datetime(2023, 9, 1),
    )
    db.execute(
        text("UPDATE school_projects SET phase = 'frozen' WHERE id = :pid"), {"pid": ns.sp4b.id}
    )
    db.execute(
        text("UPDATE school_projects SET phase = NULL WHERE id = :pid"), {"pid": ns.sp4.id}
    )
    db.commit()

    ns.sp5 = _mk_school_project(
        db,
        ns.s2.id,
        name="育才项目",
        phase=ProjectPhase.RESEARCH,
        budget=30,
        actual_cost=10,
        start_date=datetime(2024, 4, 1),
    )
    return ns


def _kpi_map(data):
    return {item["key"]: item for item in data["kpis"]}


def _year_row(rows, year):
    for row in rows:
        if row["year"] == year:
            return row
    raise AssertionError(f"year {year} not found in {rows}")


def _status_map(data):
    return {item["key"]: item for item in data["project_status"]}


def _section(profile, title):
    for section in profile["sections"]:
        if section["title"] == title:
            return section
    raise AssertionError(f"section {title!r} not found: {[s['title'] for s in profile['sections']]}")


def _items(section):
    return {item["label"]: item["value"] for item in section["items"]}


# ════════════════════════════════════════════════════════════════════
#  格式化工具单测（直接覆盖回退分支）
# ════════════════════════════════════════════════════════════════════

class TestFormattingHelpers:
    def test_text_fallbacks(self):
        from app.api.v1.data.data.bigscreen import _text

        assert _text(None) == "—"
        assert _text("") == "—"
        assert _text(0) == "0"
        assert _text("单位") == "单位"

    def test_format_completeness(self):
        from app.api.v1.data.data.bigscreen import _format_completeness

        assert _format_completeness(None) == "—"
        assert _format_completeness(0.886) == "88.6%"
        assert _format_completeness(0) == "0.0%"

    def test_format_location_skips_missing(self):
        from app.api.v1.data.data.bigscreen import _format_location

        assert _format_location("贵州省", None, "桐梓县", "") == "贵州省桐梓县"
        assert _format_location(None, None) == ""

    def test_format_date_and_period(self):
        from app.api.v1.data.data.bigscreen import _format_date, _format_period

        assert _format_date(None) == "—"
        assert _format_date(datetime(2024, 1, 2, 3, 4)) == "2024-01-02"
        assert _format_period(None, None) == "—"
        assert _format_period(datetime(2024, 1, 2), None) == "2024-01-02 至 —"

    def test_format_yes_no(self):
        from app.api.v1.data.data.bigscreen import _format_yes_no

        assert _format_yes_no(True) == "是"
        assert _format_yes_no(False) == "否"

    def test_status_keys(self):
        from app.api.v1.data.data.bigscreen import _enum_key, _phase_key, _status_key
        from app.models.school import ProjectPhase

        assert _status_key(None) == "unset"
        assert _status_key("") == "unset"
        assert _status_key("pending") == "pending"
        assert _enum_key(ProjectPhase.RESEARCH) == "research"
        assert _enum_key("frozen") == "frozen"
        # 库内枚举名（大写）归一为小写值；未知脏值原样回退
        assert _phase_key("IMPLEMENTATION") == "implementation"
        assert _phase_key("frozen") == "frozen"
        assert _phase_key(None) == "unset"

    def test_label_fallbacks(self):
        from app.api.v1.data.data.bigscreen import (
            _fund_status_label,
            _project_status_label,
            _school_phase_label,
            _support_status_label,
            _transition_status_label,
        )

        assert _project_status_label("unset") == "未设置"
        assert _project_status_label("completed") == "已完成"
        assert _project_status_label("archived") == "archived"
        assert _school_phase_label("unset") == "未设置"
        assert _school_phase_label("implementation") == "实施"
        assert _school_phase_label("frozen") == "frozen"
        assert _fund_status_label("unset") == "未设置"
        assert _fund_status_label("allocated") == "已拨付"
        assert _fund_status_label("mystery") == "mystery"
        assert _support_status_label(None) == "未设置"
        assert _support_status_label("active") == "帮扶中"
        assert _support_status_label("unknown") == "unknown"
        assert _transition_status_label(None) == "未设置"
        assert _transition_status_label("in_transition") == "过渡期中"
        assert _transition_status_label("weird") == "weird"

    def test_row_value_and_row_int(self):
        from app.api.v1.data.data.bigscreen import _row_int, _row_value

        row = SimpleNamespace(total=12, rate=1.239, empty=None)
        assert _row_value(row, "total") == "12"
        assert _row_value(row, "rate") == "1.24"
        assert _row_value(row, "empty") == "—"
        assert _row_value(None, "total") == "—"
        assert _row_int(row, "total") == 12
        assert _row_int(row, "empty") == 0
        assert _row_int(None, "total") == 0

    def test_status_item_builders_include_unknown(self):
        from app.api.v1.data.data.bigscreen import (
            _project_status_items,
            _school_phase_items,
        )

        project_items = _project_status_items({"completed": 1, "archived": 2})
        assert [item["key"] for item in project_items[:4]] == [
            "completed",
            "approved",
            "in_progress",
            "pending",
        ]
        assert project_items[-1] == {"key": "archived", "label": "archived", "value": 2}

        phase_items = _school_phase_items({"research": 1, "frozen": 2, "unset": 3})
        keys = [item["key"] for item in phase_items]
        assert keys[:5] == ["research", "approval", "implementation", "acceptance", "completed"]
        assert keys[5:] == ["frozen", "unset"]
        assert phase_items[-1]["label"] == "未设置"

    def test_empty_status_counts_keep_known_keys(self):
        from app.api.v1.data.data.bigscreen import (
            _project_status_items,
            _school_phase_items,
        )

        assert len(_project_status_items({})) == 4
        assert len(_school_phase_items({})) == 5


# ════════════════════════════════════════════════════════════════════
#  filters
# ════════════════════════════════════════════════════════════════════

class TestFilters:
    def test_filters_admin(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        resp = client.get("/api/v1/bigscreen/filters")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]

        villages = data["villages"]
        assert [item["name"] for item in villages] == ["人口村", "光明村", "幸福村", "收入村", "空村"]
        v1_item = next(item for item in villages if item["name"] == "幸福村")
        assert v1_item["id"] == ns.v1.id
        assert v1_item["county"] == "桐梓县"
        assert v1_item["support_unit"] == "某部队单位"

        schools = data["schools"]
        assert [item["name"] for item in schools] == ["希望小学", "结对小学", "育才中学"]
        s1_item = next(item for item in schools if item["name"] == "希望小学")
        assert s1_item["district"] == "桐梓县"
        assert s1_item["support_unit"] == "某部队单位"

    def test_filters_unit_counts_merge_and_sort(self, api_client):
        _client, db, _state = api_client
        _seed(db)
        data = _client.get("/api/v1/bigscreen/filters").json()["data"]
        units = {item["name"]: item for item in data["units"]}

        assert units["某部队单位"] == {
            "name": "某部队单位",
            "village_count": 1,
            "school_count": 1,
            "project_count": 3,
            "pairing_count": 3,
        }
        assert units["另一单位"]["village_count"] == 1
        assert units["另一单位"]["project_count"] == 1
        assert units["另一单位"]["pairing_count"] == 1
        assert units["第三单位"] == {
            "name": "第三单位",
            "village_count": 0,
            "school_count": 0,
            "project_count": 1,
            "pairing_count": 0,
        }
        assert units["结对单位"]["pairing_count"] == 1
        assert units["助学单位"]["pairing_count"] == 1
        # 软删结对记录、空串单位名一律排除
        assert "已删单位" not in units
        assert "" not in units
        # 排序：命中总数降序，其次结对数降序，最后名称升序
        assert [item["name"] for item in data["units"]] == [
            "某部队单位",
            "另一单位",
            "第三单位",
            "助学单位",
            "结对单位",
        ]

    def test_filters_restricted_scope(self, api_client):
        client, db, state = api_client
        _seed(db)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        data = client.get("/api/v1/bigscreen/filters").json()["data"]
        assert [item["name"] for item in data["villages"]] == ["光明村"]
        assert [item["name"] for item in data["schools"]] == ["育才中学"]
        units = {item["name"]: item for item in data["units"]}
        assert units == {
            "另一单位": {
                "name": "另一单位",
                "village_count": 1,
                "school_count": 0,
                "project_count": 1,
                "pairing_count": 1,
            }
        }

    def test_filters_empty_db(self, api_client):
        client, _db, _state = api_client
        data = client.get("/api/v1/bigscreen/filters").json()["data"]
        assert data == {"villages": [], "schools": [], "units": []}

    def test_filters_error_returns_500(self, api_client):
        client, db, _state = api_client
        _seed(db)
        with patch(
            "app.api.v1.data.data.bigscreen._collect_unit_filters",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/v1/bigscreen/filters")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 500
        assert body["message"] == "筛选项查询失败，请稍后重试"


# ════════════════════════════════════════════════════════════════════
#  overview：全局
# ════════════════════════════════════════════════════════════════════

class TestOverviewAll:
    def test_overview_all(self, api_client):
        client, db, _state = api_client
        _seed(db)
        resp = client.get("/api/v1/bigscreen/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]

        assert data["scope"] == {
            "type": "all",
            "id": None,
            "name": "全局",
            "subtitle": "全部帮扶对象",
        }
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 5
        assert kpis["projects"]["value"] == 5
        assert kpis["schools"]["value"] == 3
        assert kpis["funds"]["value"] == 1315.3
        assert kpis["completeness"]["value"].endswith("%")
        assert len(data["kpis"]) == 5

        # fund_trend / yearly 复用 dashboard 年度趋势聚合
        now = datetime.now().year
        assert [row["year"] for row in data["fund_trend"]] == list(range(now - 4, now + 1))
        assert _year_row(data["fund_trend"], 2024)["planned"] == 210.0
        assert _year_row(data["fund_trend"], 2024)["actual"] == 198.8
        assert _year_row(data["fund_trend"], 2025)["planned"] == 68.0
        assert _year_row(data["yearly"], 2023)["project_count"] == 2
        assert _year_row(data["yearly"], 2024)["project_count"] == 1
        assert _year_row(data["yearly"], 2024)["fund_count"] == 2
        # year 为 None 的经费被跳过（不再让整条趋势降级为空）
        assert len(data["yearly"]) == 5

        statuses = _status_map(data)
        assert statuses["completed"]["value"] == 1
        assert statuses["approved"]["value"] == 1
        assert statuses["in_progress"]["value"] == 1
        assert statuses["pending"]["value"] == 1
        assert statuses["archived"] == {"key": "archived", "label": "archived", "value": 1}

        assert data["rankings"] == [
            {"name": "幸福村", "score": 165.0},
            {"name": "收入村", "score": 7.5},
        ]
        assert [item["name"] for item in data["leaders"]] == [
            "修路项目",
            "饮水项目",
            "助学项目",
            "第三单位项目",
            "历史项目",
        ]
        assert data["leaders"][0] == {
            "name": "修路项目",
            "person": "张干事",
            "unit": "某部队单位",
        }
        assert data["leaders"][1]["person"] == "李科长"  # responsible_person 为空时回退 leader
        assert data["leaders"][3]["person"] == ""
        assert data["profile"] is None
        assert data["details"] is None

    def test_overview_all_years_param(self, api_client):
        client, db, _state = api_client
        _seed(db)
        data = client.get("/api/v1/bigscreen/overview", params={"years": 2}).json()["data"]
        assert len(data["fund_trend"]) == 2
        assert len(data["yearly"]) == 2

    def test_overview_all_empty_db(self, api_client):
        client, _db, _state = api_client
        data = client.get("/api/v1/bigscreen/overview").json()["data"]
        kpis = _kpi_map(data)
        assert [kpis[key]["value"] for key in ("villages", "projects", "schools")] == [0, 0, 0]
        assert kpis["completeness"]["value"] == "0.0%"
        assert kpis["funds"]["value"] == 0.0
        assert data["rankings"] == []
        assert data["leaders"] == []
        assert all(row["planned"] == 0.0 and row["actual"] == 0.0 for row in data["fund_trend"])
        assert all(row["project_count"] == 0 for row in data["yearly"])
        assert [item["value"] for item in data["project_status"]] == [0, 0, 0, 0]
        assert data["profile"] is None and data["details"] is None

    def test_dashboard_yearly_trends_endpoint_unchanged(self, api_client):
        """dashboard 端点复用抽取后的 helper，行为与响应结构保持不变。"""
        client, db, _state = api_client
        _seed(db)
        data = client.get("/api/v1/dashboard/yearly-trends?years=3").json()["data"]
        assert set(data) == {"years", "villages", "population", "income", "trends"}
        assert len(data["years"]) == 3
        assert len(data["trends"]) == 3
        assert _year_row(data["trends"], 2024)["fund_count"] == 2


# ════════════════════════════════════════════════════════════════════
#  overview：村
# ════════════════════════════════════════════════════════════════════

class TestOverviewVillage:
    def _get(self, client, village_id, **params):
        return client.get(
            "/api/v1/bigscreen/overview",
            params={"scope_type": "village", "scope_id": village_id, **params},
        )

    def test_village_overview_full(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        resp = self._get(client, ns.v1.id)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["scope"] == {
            "type": "village",
            "id": ns.v1.id,
            "name": "幸福村",
            "subtitle": "贵州省遵义市桐梓县花秋镇",
        }
        kpis = _kpi_map(data)
        assert kpis["population"]["value"] == 1300
        assert kpis["households"]["value"] == 320
        assert kpis["projects"]["value"] == 3
        assert kpis["funds"]["value"] == 175.0
        assert kpis["visits"]["value"] == 3

        assert _year_row(data["fund_trend"], 2024) == {"year": 2024, "planned": 120.0, "actual": 110.0}
        assert _year_row(data["fund_trend"], 2025) == {"year": 2025, "planned": 60.0, "actual": 55.0}
        assert _year_row(data["yearly"], 2024) == {"year": 2024, "project_count": 1, "fund_count": 1}
        assert _year_row(data["yearly"], 2025) == {"year": 2025, "project_count": 1, "fund_count": 1}

        statuses = _status_map(data)
        assert statuses["completed"]["value"] == 1
        assert statuses["in_progress"]["value"] == 1
        assert statuses["archived"]["value"] == 1
        assert statuses["approved"]["value"] == 0

        assert data["rankings"] == [
            {"name": "修路项目", "score": 500.5},
            {"name": "饮水项目", "score": 300.0},
            {"name": "历史项目", "score": 50.0},
        ]
        assert [item["person"] for item in data["leaders"]] == ["张干事", "李科长", ""]

        profile = data["profile"]
        assert profile["title"] == "幸福村 · 对象档案"
        basic = _items(_section(profile, "基础信息"))
        assert basic == {
            "所属区域": "贵州省遵义市桐梓县花秋镇",
            "帮扶单位": "某部队单位",
            "部门单位": "政治工作处",
            "振兴梯队": "是",
            "过渡状态": "过渡期中",
        }
        population = _items(_section(profile, "人口与收入（2025年）"))
        assert population == {
            "总户数": "320",
            "总人口": "1300",
            "常住人口": "1000",
            "脱贫人口": "110",
            "村人均纯收入(万元)": "1.85",
            "村集体收入(万元)": "12.5",
        }
        investment = _items(_section(profile, "帮扶投入（2025年）"))
        assert investment == {
            "专项投入(万元)": "120.46",
            "协调地方投入(万元)": "80.0",
            "产业投入(万元)": "30.0",
            "基础设施投入(万元)": "—",
            "党建投入(万元)": "0.0",
            "医疗投入(万元)": "—",
            "教育投入(万元)": "5.5",
        }
        pairing = _items(_section(profile, "结对与走访"))
        assert pairing == {"结对记录数": "3", "进行中": "2", "走访次数": "3"}
        assert profile["tags"] == [{"label": "区域标记", "items": ["三区三州", "民族地区"]}]

        details = data["details"]
        assert details["projects"][0] == {
            "name": "修路项目",
            "status": "completed",
            "label": "已完成",
            "amount": 500.5,
            "person": "张干事",
        }
        assert details["projects"][-1]["label"] == "archived"
        assert details["funds"] == [
            {
                "name": "助学资金",
                "year": 2025,
                "status": "pending",
                "label": "待审批",
                "amount": 50.0,
            },
            {
                "name": "修路资金",
                "year": 2024,
                "status": "allocated",
                "label": "已拨付",
                "amount": 100.0,
            },
            {
                "name": "—",
                "year": None,
                "status": "mystery",
                "label": "mystery",
                "amount": 25.0,
            },
        ]
        assert details["pairing"] == {"total": 3, "active": 2, "visits": 3}

    def test_village_income_only_profile(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        data = self._get(client, ns.v4.id).json()["data"]
        profile = data["profile"]
        assert profile["title"] == "收入村 · 对象档案"
        population = _items(_section(profile, "人口与收入（2023年）"))
        assert population["总人口"] == "—"
        assert population["村人均纯收入(万元)"] == "1.2"
        investment = _section(profile, "帮扶投入")
        assert [item["label"] for item in investment["items"]] == [
            "专项投入(万元)",
            "协调地方投入(万元)",
        ]
        assert profile["tags"] == []
        assert _kpi_map(data)["funds"]["value"] == 7.5
        assert data["rankings"] == []

    def test_village_population_only_profile(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        data = self._get(client, ns.v5.id).json()["data"]
        profile = data["profile"]
        population = _items(_section(profile, "人口与收入（2022年）"))
        assert population["总户数"] == "10"
        assert population["总人口"] == "—"
        assert population["常住人口"] == "5"
        assert population["脱贫人口"] == "1"
        assert population["村人均纯收入(万元)"] == "—"
        kpis = _kpi_map(data)
        assert kpis["population"]["value"] == 0
        assert kpis["households"]["value"] == 10

    def test_village_empty_data_profile(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        data = self._get(client, ns.v6.id).json()["data"]
        profile = data["profile"]
        titles = [section["title"] for section in profile["sections"]]
        assert titles == ["基础信息", "帮扶投入", "结对与走访"]
        assert profile["tags"] == []
        assert _kpi_map(data)["projects"]["value"] == 0
        assert data["rankings"] == []
        assert data["leaders"] == []
        assert data["details"]["projects"] == []
        assert data["details"]["funds"] == []
        assert data["details"]["pairing"] == {"total": 0, "active": 0, "visits": 0}

    def test_village_not_found(self, api_client):
        client, db, _state = api_client
        _seed(db)
        resp = self._get(client, 99999)
        assert resp.status_code == 404
        assert resp.json()["message"] == "帮扶村不存在"

    def test_village_soft_deleted_not_found(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        assert self._get(client, ns.v3.id).status_code == 404

    def test_village_cross_scope_not_found(self, api_client):
        client, db, state = api_client
        ns = _seed(db)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert self._get(client, ns.v1.id).status_code == 404

    def test_village_restricted_scope_ok(self, api_client):
        client, db, state = api_client
        ns = _seed(db)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        resp = self._get(client, ns.v2.id)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["scope"]["name"] == "光明村"
        kpis = _kpi_map(data)
        assert kpis["projects"]["value"] == 1
        assert kpis["visits"]["value"] == 1
        assert [item["name"] for item in data["rankings"]] == ["助学项目"]
        assert data["details"]["pairing"]["total"] == 1

    def test_village_missing_id_bad_request(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/bigscreen/overview", params={"scope_type": "village"})
        assert resp.status_code == 400
        assert resp.json()["message"] == "缺少对象 ID"


# ════════════════════════════════════════════════════════════════════
#  overview：学校
# ════════════════════════════════════════════════════════════════════

class TestOverviewSchool:
    def _get(self, client, school_id, **params):
        return client.get(
            "/api/v1/bigscreen/overview",
            params={"scope_type": "school", "scope_id": school_id, **params},
        )

    def test_school_overview_full(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        resp = self._get(client, ns.s1.id)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["scope"] == {
            "type": "school",
            "id": ns.s1.id,
            "name": "希望小学",
            "subtitle": "贵州省遵义市桐梓县",
        }
        kpis = _kpi_map(data)
        assert kpis["students"]["value"] == 320
        assert kpis["teachers"]["value"] == 24
        assert kpis["classes"]["value"] == 8
        assert kpis["projects"]["value"] == 5
        assert kpis["funds"]["value"] == 88.8

        assert _year_row(data["fund_trend"], 2024) == {"year": 2024, "planned": 90.0, "actual": 88.8}
        assert _year_row(data["yearly"], 2023)["project_count"] == 2
        assert _year_row(data["yearly"], 2024)["project_count"] == 1
        assert _year_row(data["yearly"], 2025)["project_count"] == 1

        statuses = _status_map(data)
        assert statuses["implementation"]["value"] == 1
        assert statuses["acceptance"]["value"] == 1
        assert statuses["research"]["value"] == 1
        assert statuses["completed"]["value"] == 0
        assert statuses["approval"]["value"] == 0
        assert statuses["frozen"] == {"key": "frozen", "label": "frozen", "value": 1}
        assert statuses["unset"] == {"key": "unset", "label": "未设置", "value": 1}

        assert data["rankings"] == [
            {"name": "教学楼改造", "score": 150.0},
            {"name": "图书捐赠", "score": 18.0},
            {"name": "未知阶段项目", "score": 5.0},
            {"name": "未知脏值项目", "score": 2.0},
            {"name": "未设置阶段项目", "score": 0.0},
        ]
        assert data["leaders"] == [
            {"name": "教学楼改造", "person": "基建", "unit": None},
            {"name": "图书捐赠", "person": "", "unit": None},
            {"name": "未知阶段项目", "person": "其他", "unit": None},
            {"name": "未知脏值项目", "person": "", "unit": None},
            {"name": "未设置阶段项目", "person": "", "unit": None},
        ]

        profile = data["profile"]
        assert profile["title"] == "希望小学 · 对象档案"
        assert profile["tags"] == []
        basic = _items(_section(profile, "基础信息"))
        assert basic == {
            "所属区域": "贵州省遵义市桐梓县",
            "帮扶单位": "某部队单位",
            "帮扶状态": "帮扶中",
            "帮扶起止日期": "2022-01-01 至 —",
        }
        scale = _items(_section(profile, "办学规模"))
        assert scale == {"学生人数": "320", "教师人数": "24", "班级数量": "8", "建校年份": "1998"}
        support = _items(_section(profile, "助学帮扶"))
        assert support == {
            "学校项目数": "5",
            "预算合计(万元)": "220.0",
            "实际投入合计(万元)": "175.0",
            "资助学生数": "2",
            "资助金额合计(元)": "800.5",
        }
        assert _items(_section(profile, "结对与走访")) == {
            "结对记录数": "2",
            "进行中": "1",
            "走访次数": "1",
        }

        details = data["details"]
        assert len(details["projects"]) == 5
        assert details["projects"][0] == {
            "name": "教学楼改造",
            "status": "implementation",
            "label": "实施",
            "amount": 150.0,
            "person": "基建",
        }
        assert details["projects"][-1]["label"] == "未设置"
        assert details["funds"] == [
            {
                "name": "学校修缮",
                "year": 2024,
                "status": "completed",
                "label": "已完成",
                "amount": 88.8,
            }
        ]
        assert details["pairing"] == {"total": 2, "active": 1, "visits": 1}

    def test_school_empty_data(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        data = self._get(client, ns.s4.id).json()["data"]
        kpis = _kpi_map(data)
        assert [kpis[key]["value"] for key in ("students", "teachers", "classes", "projects")] == [
            0,
            0,
            0,
            0,
        ]
        assert kpis["funds"]["value"] == 0.0
        assert data["rankings"] == []
        assert data["leaders"] == []
        assert [item["value"] for item in data["project_status"]] == [0, 0, 0, 0, 0]
        assert data["details"]["projects"] == []
        assert data["details"]["funds"] == []
        assert data["details"]["pairing"] == {"total": 0, "active": 0, "visits": 0}
        profile = data["profile"]
        basic = _items(_section(profile, "基础信息"))
        assert basic["所属区域"] == "贵州省"
        assert basic["帮扶单位"] == "—"
        assert basic["帮扶状态"] == "未帮扶"
        assert basic["帮扶起止日期"] == "—"
        scale = _items(_section(profile, "办学规模"))
        assert scale == {"学生人数": "0", "教师人数": "0", "班级数量": "0", "建校年份": "—"}
        support = _items(_section(profile, "助学帮扶"))
        assert support == {
            "学校项目数": "0",
            "预算合计(万元)": "0.0",
            "实际投入合计(万元)": "0.0",
            "资助学生数": "0",
            "资助金额合计(元)": "0.0",
        }
        assert profile["tags"] == []

    def test_school_restricted_scope(self, api_client):
        client, db, state = api_client
        ns = _seed(db)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert self._get(client, ns.s1.id).status_code == 404
        resp = self._get(client, ns.s2.id)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["scope"]["name"] == "育才中学"
        kpis = _kpi_map(data)
        assert kpis["projects"]["value"] == 1
        assert kpis["students"]["value"] == 100
        basic = _items(_section(data["profile"], "基础信息"))
        assert basic["帮扶状态"] == "已完成"
        assert basic["帮扶起止日期"] == "2023-01-01 至 2024-01-01"
        assert [item["name"] for item in data["rankings"]] == ["育才项目"]

    def test_school_not_found(self, api_client):
        client, db, _state = api_client
        _seed(db)
        resp = self._get(client, 99999)
        assert resp.status_code == 404
        assert resp.json()["message"] == "帮扶学校不存在"

    def test_school_soft_deleted_not_found(self, api_client):
        client, db, _state = api_client
        ns = _seed(db)
        assert self._get(client, ns.s3.id).status_code == 404

    def test_school_missing_id_bad_request(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/bigscreen/overview", params={"scope_type": "school"})
        assert resp.status_code == 400
        assert resp.json()["message"] == "缺少对象 ID"


# ════════════════════════════════════════════════════════════════════
#  overview：单位
# ════════════════════════════════════════════════════════════════════

class TestOverviewUnit:
    def _get(self, client, name, **params):
        return client.get(
            "/api/v1/bigscreen/overview",
            params={"scope_type": "unit", "scope_name": name, **params},
        )

    def test_unit_overview_village_and_school_hits(self, api_client):
        client, db, _state = api_client
        _seed(db)
        resp = self._get(client, "某部队单位")
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["scope"]["type"] == "unit"
        assert data["scope"]["id"] is None
        assert data["scope"]["name"] == "某部队单位"
        assert data["scope"]["subtitle"] == "覆盖 1 个帮扶村 / 1 所帮扶学校"
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 1
        assert kpis["schools"]["value"] == 1
        assert kpis["projects"]["value"] == 3
        assert kpis["funds"]["value"] == 275.8
        assert kpis["visits"]["value"] == 4

        assert _year_row(data["fund_trend"], 2024) == {"year": 2024, "planned": 210.0, "actual": 198.8}
        assert _year_row(data["fund_trend"], 2025) == {"year": 2025, "planned": 60.0, "actual": 55.0}
        assert _year_row(data["yearly"], 2024)["project_count"] == 1
        statuses = _status_map(data)
        assert statuses["completed"]["value"] == 1
        assert statuses["in_progress"]["value"] == 1
        assert statuses["archived"]["value"] == 1
        assert statuses["pending"]["value"] == 0

        assert data["rankings"] == [{"name": "幸福村", "score": 165.0}]
        assert [item["name"] for item in data["leaders"]] == ["修路项目", "饮水项目", "历史项目"]

        profile = data["profile"]
        assert profile["title"] == "某部队单位 · 帮扶档案"
        overview = _items(_section(profile, "单位概况"))
        assert overview == {
            "覆盖帮扶村": "1",
            "覆盖帮扶学校": "1",
            "帮扶项目": "3",
            "经费投入(万元)": "275.8",
            "结对记录": "3",
            "走访次数": "4",
        }
        assert profile["tags"] == [
            {"label": "覆盖帮扶村", "items": ["幸福村"]},
            {"label": "覆盖帮扶学校", "items": ["希望小学"]},
        ]

        details = data["details"]
        assert [item["name"] for item in details["projects"]] == [
            "修路项目",
            "饮水项目",
            "历史项目",
        ]
        assert [item["name"] for item in details["funds"]] == [
            "项目经费",
            "助学资金",
            "学校修缮",
            "修路资金",
            "—",
        ]
        assert details["pairing"] == {"total": 3, "active": 2, "visits": 4}

    def test_unit_school_only_pairing(self, api_client):
        """仅由结对记录命中的学校（村/项目均为空）。"""
        client, db, _state = api_client
        _seed(db)
        data = self._get(client, "助学单位").json()["data"]
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 0
        assert kpis["schools"]["value"] == 1
        assert kpis["projects"]["value"] == 0
        assert kpis["funds"]["value"] == 88.8
        assert data["rankings"] == []
        assert data["leaders"] == []
        assert data["details"]["projects"] == []
        profile = data["profile"]
        assert _items(_section(profile, "单位概况"))["覆盖帮扶学校"] == "1"
        assert profile["tags"] == [{"label": "覆盖帮扶学校", "items": ["希望小学"]}]

    def test_unit_village_only_pairing(self, api_client):
        """仅由结对记录命中的村：rankings 走村经费排行分支。"""
        client, db, _state = api_client
        _seed(db)
        data = self._get(client, "结对单位").json()["data"]
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 1
        assert kpis["schools"]["value"] == 0
        assert kpis["projects"]["value"] == 0
        assert kpis["funds"]["value"] == 7.5
        assert data["rankings"] == [{"name": "收入村", "score": 7.5}]
        profile = data["profile"]
        assert profile["tags"] == [{"label": "覆盖帮扶村", "items": ["收入村"]}]

    def test_unit_project_only(self, api_client):
        """无村无校、仅 responsible_unit 命中项目：rankings 回退项目排行。"""
        client, db, _state = api_client
        _seed(db)
        data = self._get(client, "第三单位").json()["data"]
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 0
        assert kpis["schools"]["value"] == 0
        assert kpis["projects"]["value"] == 1
        assert kpis["funds"]["value"] == 33
        assert data["rankings"] == [{"name": "第三单位项目", "score": 100.0}]
        assert data["details"]["pairing"] == {"total": 0, "active": 0, "visits": 0}

    def test_unit_unknown_returns_empty_overview(self, api_client):
        client, db, _state = api_client
        _seed(db)
        resp = self._get(client, "不存在的单位")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["scope"]["name"] == "不存在的单位"
        assert [item["value"] for item in data["kpis"]] == [0, 0, 0, 0.0, 0]
        assert data["rankings"] == []
        assert data["details"] == {
            "projects": [],
            "funds": [],
            "pairing": {"total": 0, "active": 0, "visits": 0},
        }
        assert data["profile"]["tags"] == []

    def test_unit_name_stripped(self, api_client):
        client, db, _state = api_client
        _seed(db)
        data = self._get(client, "  某部队单位  ").json()["data"]
        assert data["scope"]["name"] == "某部队单位"
        assert _kpi_map(data)["villages"]["value"] == 1

    def test_unit_restricted_scope_hides_other_org(self, api_client):
        client, db, state = api_client
        ns = _seed(db)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        # org1 的单位在受限用户视角下无任何覆盖
        data = self._get(client, "某部队单位").json()["data"]
        assert [item["value"] for item in data["kpis"]] == [0, 0, 0, 0.0, 0]
        # 本组织的单位正常可见
        data = self._get(client, "另一单位").json()["data"]
        kpis = _kpi_map(data)
        assert kpis["villages"]["value"] == 1
        assert kpis["projects"]["value"] == 1
        assert [item["name"] for item in data["details"]["projects"]] == ["助学项目"]
        assert ns.v2.id  # 数据确实已入库

    def test_unit_missing_or_blank_name_bad_request(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/bigscreen/overview", params={"scope_type": "unit"})
        assert resp.status_code == 400
        assert resp.json()["message"] == "单位名称不能为空"
        resp = client.get(
            "/api/v1/bigscreen/overview", params={"scope_type": "unit", "scope_name": "   "}
        )
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
#  参数校验
# ════════════════════════════════════════════════════════════════════

class TestOverviewValidation:
    def test_invalid_scope_type_bad_request(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/bigscreen/overview", params={"scope_type": "country"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 400
        assert "不支持的筛选维度" in body["message"]

    def test_years_out_of_range_rejected(self, api_client):
        client, _db, _state = api_client
        assert client.get("/api/v1/bigscreen/overview", params={"years": 0}).status_code == 422
        assert client.get("/api/v1/bigscreen/overview", params={"years": 11}).status_code == 422
