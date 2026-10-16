"""R28 · H6 回归：公文报告导出（report_export_service）数据域隔离。

背景（R27 报告 H6）：
    ``generate_*_report_data`` 六个数据构建方法只接收 ``db``/``year``，
    服务层直接聚合**全库**，仅靠端点上的 ``require_admin`` 把关。部门级管理员
    （``role="admin"`` 且非超管）因此可借 ``/export/report-word``、
    ``/export/report-pdf`` 读到**跨组织**的总量与金额，与同一模块
    ``/export/funds``、``/export/comprehensive`` 的 ``scoped_filter`` 口径不一致，
    违反军事审计导出隔离红线 S2。

R28 修复：
    1. 六个方法强制 ``current_user`` 位置参数（无默认值）——漏传在调用点直接
       ``TypeError``（fail-closed），不会静默退回全库口径；
    2. 内部经服务层统一入口 ``app.services.data_scope_query.scoped_filter``
       追加数据域过滤（判定真源仍是 ``app.core.data_permission``）。

本文件用**真实 SQLite**（conftest ``real_db_session``，非 mock）双向锁定：
部门级 admin 只拿到本组织，超管拿到全量；并锁定 fail-closed 签名契约。
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.models.fund import Fund
from app.models.organization import Organization
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.services.report_export_service import ReportExportService

YEAR = 2024

# 两组织各一条记录；甲单位为当前登录的部门级 admin 所属组织。
ORG_A, ORG_B = 1, 2


@pytest.fixture
def scoped_db(real_db_session):
    """真实 SQLite：甲/乙两单位各 1 村、1 校、1 项目、1 笔经费（同年度）。"""
    db = real_db_session
    db.add_all([Organization(id=ORG_A, name="甲单位"), Organization(id=ORG_B, name="乙单位")])
    db.add_all(
        [
            SupportedVillage(name="甲村", organization_id=ORG_A, created_by=11),
            SupportedVillage(name="乙村", organization_id=ORG_B, created_by=22),
        ]
    )
    db.add_all(
        [
            School(
                name="甲校", organization_id=ORG_A, created_by=11,
                student_count=100, teacher_count=10,
            ),
            School(
                name="乙校", organization_id=ORG_B, created_by=22,
                student_count=200, teacher_count=20,
            ),
        ]
    )
    db.add_all(
        [
            Project(
                name="甲项目", organization_id=ORG_A, created_by=11, status="completed",
                progress=100, budget=1000, actual_cost=900, start_date=date(YEAR, 1, 1),
            ),
            Project(
                name="乙项目", organization_id=ORG_B, created_by=22, status="completed",
                progress=50, budget=1000, actual_cost=500, start_date=date(YEAR, 1, 1),
            ),
        ]
    )
    db.add_all(
        [
            Fund(
                name="甲经费", organization_id=ORG_A, created_by=11, fund_type="产业扶持",
                date=date(YEAR, 3, 1), amount=1000,
            ),
            Fund(
                name="乙经费", organization_id=ORG_B, created_by=22, fund_type="产业扶持",
                date=date(YEAR, 3, 1), amount=5000,
            ),
        ]
    )
    db.commit()
    return db


@pytest.fixture
def dept_admin():
    """部门级管理员（role=admin 且非超管）→ OWN_DEPT，仅本组织。"""
    return SimpleNamespace(id=11, username="dept-a", role="admin", is_superuser=False, organization_id=ORG_A)


@pytest.fixture
def super_admin():
    """超管 → DataScope.ALL，不过滤。"""
    return SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=None)


@pytest.fixture
def svc():
    return ReportExportService()


# ────────────────────── 双向隔离（真实库） ──────────────────────


class TestVillageSummaryScope:
    def test_dept_admin_sees_own_org_only(self, svc, scoped_db, dept_admin):
        data = svc.generate_village_summary_report_data(scoped_db, YEAR, dept_admin)
        assert data["total_villages"] == 1
        assert any("1" in p for p in data["sections"][0]["paragraphs"])

    def test_super_admin_sees_all(self, svc, scoped_db, super_admin):
        data = svc.generate_village_summary_report_data(scoped_db, YEAR, super_admin)
        assert data["total_villages"] == 2


class TestSchoolStatisticsScope:
    def test_dept_admin_sees_own_org_only(self, svc, scoped_db, dept_admin):
        data = svc.generate_school_statistics_report_data(scoped_db, YEAR, dept_admin)
        assert data["total_schools"] == 1
        assert data["total_students"] == 100
        assert data["total_teachers"] == 10

    def test_super_admin_sees_all(self, svc, scoped_db, super_admin):
        data = svc.generate_school_statistics_report_data(scoped_db, YEAR, super_admin)
        assert data["total_schools"] == 2
        assert data["total_students"] == 300
        assert data["total_teachers"] == 30


class TestProjectProgressScope:
    def test_dept_admin_sees_own_org_only(self, svc, scoped_db, dept_admin):
        data = svc.generate_project_progress_report_data(scoped_db, YEAR, dept_admin)
        rows = data["sections"][0]["table"]["rows"]
        body = {row[0]: row for row in rows}
        assert body["合计"][1] == "1"
        assert body["合计"][3] == "1,000.00"

    def test_super_admin_sees_all(self, svc, scoped_db, super_admin):
        data = svc.generate_project_progress_report_data(scoped_db, YEAR, super_admin)
        body = {row[0]: row for row in data["sections"][0]["table"]["rows"]}
        assert body["合计"][1] == "2"
        assert body["合计"][3] == "2,000.00"


class TestFundDetailScope:
    def test_dept_admin_sees_own_org_only(self, svc, scoped_db, dept_admin):
        data = svc.generate_fund_detail_report_data(scoped_db, YEAR, dept_admin)
        body = {row[0]: row for row in data["sections"][0]["table"]["rows"]}
        # 乙单位 5,000 不得计入
        assert body["合计"][2] == "1,000.00"

    def test_super_admin_sees_all(self, svc, scoped_db, super_admin):
        data = svc.generate_fund_detail_report_data(scoped_db, YEAR, super_admin)
        body = {row[0]: row for row in data["sections"][0]["table"]["rows"]}
        assert body["合计"][2] == "6,000.00"


class TestMergedReportsScope:
    def test_summary_report_is_scoped(self, svc, scoped_db, dept_admin):
        data = svc.generate_summary_report_data(scoped_db, YEAR, dept_admin)
        # 一、帮扶村概况
        assert any("共 1 个" in p for p in data["sections"][0]["paragraphs"])
        # 二、帮扶学校概况
        assert any("1 所" in p and "100 人" in p for p in data["sections"][1]["paragraphs"])
        # 四、帮扶资金执行（合计 1,000，乙单位 5,000 不得出现）
        fund_rows = data["sections"][3]["table"]["rows"]
        assert fund_rows[-1][2] == "1,000.00"

    def test_annual_summary_is_scoped(self, svc, scoped_db, dept_admin):
        data = svc.generate_annual_summary_report_data(scoped_db, YEAR, dept_admin)
        assert data["village_summary"]["total_villages"] == 1
        assert data["school_statistics"]["total_schools"] == 1
        assert data["fund_detail"]["sections"][0]["table"]["rows"][-1][2] == "1,000.00"

    def test_super_admin_summary_covers_all(self, svc, scoped_db, super_admin):
        data = svc.generate_summary_report_data(scoped_db, YEAR, super_admin)
        assert any("共 2 个" in p for p in data["sections"][0]["paragraphs"])


# ────────────────────── fail-closed 签名契约 ──────────────────────


class TestFailClosedSignature:
    """漏传 current_user 必须在调用点 TypeError，而不是静默回退全库口径。"""

    @pytest.mark.parametrize(
        "method",
        [
            "generate_summary_report_data",
            "generate_fund_detail_report_data",
            "generate_project_progress_report_data",
            "generate_school_statistics_report_data",
            "generate_village_summary_report_data",
            "generate_annual_summary_report_data",
        ],
    )
    def test_missing_current_user_raises_type_error(self, svc, scoped_db, method):
        with pytest.raises(TypeError):
            getattr(svc, method)(scoped_db, YEAR)


def test_scoped_helper_applies_scope_filter(scoped_db, dept_admin):
    """_scoped 经服务层统一入口过滤（单点验证，避免各方法重复断言）。"""
    total = ReportExportService._scoped(
        scoped_db.query(SupportedVillage), SupportedVillage, dept_admin
    ).count()
    assert total == 1
