"""分支覆盖补齐（Group A）：policy.py / reports.py / data_reports.py / dashboard.py / analytics.py

每个用例针对 coverage.py 报告的一条缺失分支弧（行号->行号），直调目标函数，
用最小 mock 构造未覆盖分支的真实语义场景。断言均写行为语义（返回值/副作用）。

覆盖弧清单：
- policy.py:        742->744, 750->752, 759->757, 1255->1257,
                    1278->1288, 1308->1312, 1643->1646
- reports.py:       727->732, 733->747, 735->737, 737->747, 741->747,
                    818->823, 845->858
- data_reports.py:  202->205, 369->378, 406->412, 432->436, 484->488, 491->499
- dashboard.py:     131->136, 230->232, 393->416
- analytics.py:     323->322, 335->334, 347->346
"""

import os
import tempfile
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.responses import StreamingResponse
from sqlalchemy import select

import app.api.v1.data.data.analytics as analytics_mod
import app.api.v1.data.data.dashboard as dash
import app.api.v1.data.data.data_reports as dr
import app.api.v1.data.data.reports as reports_mod
import app.api.v1.policy as policy_mod
from app.models.supported_village import SupportedVillage


# ==================== 公共设施 ====================


def q(**kw):
    """通用查询链 mock：链式调用自返回，scalar/first/all 可配。"""
    m = MagicMock()
    for attr in ("filter", "order_by", "limit", "offset", "group_by", "select_from", "subquery"):
        getattr(m, attr).return_value = m
    m.scalar.return_value = kw.get("scalar")
    m.first.return_value = kw.get("first")
    m.all.return_value = kw.get("all", [])
    return m


def db_of(*queries):
    """db.query 按调用顺序依次返回给定查询链。"""
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


def scope(full_access=True, org_ids=None, org_names=None):
    """OrgScopeFilter mock：filter_by_org_ids 透传查询。"""
    s = MagicMock()
    s.has_full_access = MagicMock(return_value=full_access)
    s.org_ids = org_ids if org_ids is not None else []
    s.org_names = org_names if org_names is not None else []
    s.filter_by_org_ids = MagicMock(side_effect=lambda query, *a, **k: query)
    return s


def admin_user(**extra):
    u = SimpleNamespace(
        id=1, username="admin", full_name="管理员", role="super_admin",
        is_superuser=True, organization_id=None, org_id=99,
    )
    for k, v in extra.items():
        setattr(u, k, v)
    return u


def staff_user(**extra):
    """非管理员：is_superuser=False 且 role 不在 ADMIN_ROLES。"""
    u = SimpleNamespace(
        id=7, username="staff", full_name="普通用户", role="staff",
        is_superuser=False, organization_id=None, org_id=99,
    )
    for k, v in extra.items():
        setattr(u, k, v)
    return u


def make_policy(**extra):
    """构造覆盖 _policy_to_frontend / PDF 导出全部读取属性的策略对象。"""
    p = SimpleNamespace(
        id=1, title="测试政策", code="C-2024-001", summary=None, keywords=None,
        category=None, level="", status="active", issue_date=None,
        effective_date=None, issuing_authority=None, content="", file_type=None,
        view_count=0, download_count=0, created_at=None, updated_at=None,
        attachment_urls=None, file_path=None,
    )
    for k, v in extra.items():
        setattr(p, k, v)
    return p


def make_report(**extra):
    """构造覆盖 DataReportResponse 必需字段的上报对象。"""
    r = SimpleNamespace(
        id=1, title="一季度上报", report_type="monthly", status="submitted",
        source_org_id=1, target_org_id=2, created_at=None, updated_at=None,
        report_code="DR-2024-001", description=None, submitted_at=None,
        package_id=5, reviewed_by=None, reviewed_at=None, comment=None,
    )
    for k, v in extra.items():
        setattr(r, k, v)
    return r


# ==================== policy.py ====================


class TestPolicyBranchGaps:
    def test_build_policies_pdf_empty_code_meta_and_blank_paragraphs(self):
        """742->744 / 750->752 / 759->757：code 为空、meta 全空、正文去标签后无有效段落。"""
        p = make_policy(
            code="",                       # 742 if p.code 为假 -> 744
            issuing_authority=None,
            issue_date=None,
            effective_date=None,           # meta_parts 为空 -> 750->752
            content="<p></p><div></div>",  # strip 后非空，但去标签后全空行 -> 759->757
            file_path=None,
        )
        data = policy_mod._build_policies_pdf([p])
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_build_policies_pdf_escapes_html_metachars(self):
        """R20：标题/正文含 < & > 时 reportlab mini-HTML 解析不得抛异常。

        修复前 `Paragraph(f"{idx}. {p.title}")` 直接拼未转义文本，标题含
        `<`/`&`（如"关于<重点>帮扶&振兴的通知"）会触发 500。此处直接调用
        `_build_policies_pdf` 断言不抛异常且返回非空 PDF 字节流（%PDF 魔数）。
        """
        p = make_policy(
            title="关于<重点>帮扶&振兴的通知",
            content="<p>支出 &lt; 100 &gt; 50</p><p>第二段含 A & B</p>",
            file_path=None,
        )
        data = policy_mod._build_policies_pdf([p])
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data[:4] == b"%PDF"

    async def test_get_related_policies_without_category(self):
        """1255->1257：源政策 category 为空，跳过 category 过滤仍返回相关政策。"""
        policy = make_policy(category=None)
        db = db_of(
            q(first=policy),  # 源政策查询
            q(all=[]),        # 相关政策查询
        )
        resp = await policy_mod.get_related_policies(
            1, limit=5, current_user=admin_user(), db=db
        )
        assert resp["code"] == 200
        assert resp["data"] == []

    async def test_search_policies_empty_results_non_admin(self, monkeypatch):
        """1278->1288：非管理员且 FTS 检索结果为空，跳过可见性过滤直接返回。"""
        monkeypatch.setattr(
            "app.services.policy_fts_service.search_policies_fts",
            lambda db, kw, limit=None, offset=None: [],
        )
        db = MagicMock()
        resp = await policy_mod.search_policies(
            q="不存在的关键词", limit=20, offset=0, db=db, current_user=staff_user()
        )
        assert resp["code"] == 200
        assert resp["data"]["items"] == []
        assert resp["data"]["total"] == 0

    async def test_get_policy_active_visible_to_non_admin(self):
        """1308->1312：非管理员访问 active 政策放行（不抛 403），浏览量原子递增。"""
        policy = make_policy(status="active", created_by=999)
        db = db_of(
            q(first=policy),  # 详情查询
            q(),              # view_count update 查询
        )
        resp = await policy_mod.get_policy(1, current_user=staff_user(), db=db)
        assert resp["code"] == 200
        assert resp["data"]["id"] == 1
        # 副作用：递增 update 已执行
        assert db.query.call_count == 2

    def test_attachment_urls_parsed_list_without_valid_strings(self):
        """1643->1646：attachment_urls 解析为列表但无合法字符串项，回退 file_path 逻辑。"""
        p = make_policy(attachment_urls="[1, 2]", file_path=None)
        assert policy_mod._attachment_urls_of(p) == []


# ==================== dashboard.py ====================


class TestDashboardBranchGaps:
    def test_query_village_stats_population_row_none(self):
        """131->136：有村庄且有最新年份但人口汇总行查询为 None，人口/户数保持 0。"""
        db = db_of(
            q(),                                        # 村庄范围查询
            q(scalar=2),                                # total_villages
            q(scalar=2026),                             # latest_year
            q(first=None),                              # 人口汇总行（外层）
            select(SupportedVillage.id).scalar_subquery(),  # in_() 内层子查询
            q(first=(2, 1, 50, 5)),                     # 学校统计行
        )
        result = dash._query_village_stats(db, scope(True))
        assert result["total_villages"] == 2
        assert result["total_population"] == 0
        assert result["total_households"] == 0
        assert result["total_schools"] == 2

    def test_compute_trends_no_population_year(self):
        """393->416：无人口数据年份（max 为 None），跳过人口/收入同比，其余趋势正常。"""
        db = db_of(*[
            q(scalar=v) for v in (5, 2, 8, 3, 6, 2, 1000, 800, None)
        ])
        trends = dash._compute_trends(db, scope(True))
        assert trends == {
            "villages": 150.0,
            "projects": 166.7,
            "schools": 200.0,
            "funds": 25.0,
        }
        assert "population_yoy" not in trends
        assert "income_yoy" not in trends

    def test_apply_project_scope_org_names_project_without_responsible_unit(self, monkeypatch):
        """230->232：Project 无 responsible_unit 属性时按 department 兜底判断为假条件。

        真实 Project 模型恒有 responsible_unit（hasattr 恒真），故以模块级替身
        模拟无该属性的模型形态；同时无 organization_id 走 org_names 文本回退路径。
        """
        monkeypatch.setattr(dash, "Project", type("_BareProject", (), {}))
        query = MagicMock()
        result = dash._apply_project_scope(
            query, scope(full_access=False, org_ids=[], org_names=["农业农村局"])
        )
        # 名称长度 >= 2 但两个属性均不存在 -> conditions 为空 -> filter(False) 兜底
        assert result is query.filter.return_value


# ==================== analytics.py ====================


class TestAnalyticsBranchGaps:
    async def test_cross_org_comparison_rows_outside_org_map(self):
        """323->322 / 335->334 / 347->346：GROUP BY 行的组织不在组织映射内时跳过聚合。"""
        db = db_of(
            q(all=[(1, "教育局")]),   # 活跃组织
            q(all=[(99, 5)]),         # 村庄计数行：org 99 不在映射内
            q(all=[(98, 4, 2)]),      # 项目计数行：org 98 不在映射内
            q(all=[(97, 123.45)]),    # 资金行：org 97 不在映射内
        )
        resp = await analytics_mod.get_cross_org_comparison(
            db=db, current_user=admin_user()
        )
        assert resp.success is True
        items = resp.data["items"]
        assert len(items) == 1
        item = items[0]
        # 映射外组织行不污染映射内组织的聚合结果
        assert item["organization_id"] == 1
        assert item["villages"] == 0
        assert item["projects_total"] == 0
        assert item["projects_completed"] == 0
        assert item["completion_rate"] == 0.0
        assert item["funds_total"] == 0.0


# ==================== reports.py ====================


class TestReportsBranchGaps:
    async def test_generate_report_subscription_missing_admin(self):
        """727->732 / 733->747：管理员跳过属主过滤；订阅不存在时沿用请求参数。"""
        request = reports_mod.ReportGenerateRequest(
            subscription_id=3, report_type="summary", year=2026,
            village_ids=[7], format="json",
        )
        service = MagicMock()
        service.db = db_of(q(first=None))  # 订阅查询无结果
        resp = await reports_mod.generate_report(
            request, current_user=admin_user(), service=service
        )
        assert resp["code"] == 200
        assert resp["data"]["report_type"] == "summary"
        assert resp["data"]["parameters"]["year"] == 2026
        assert resp["data"]["parameters"]["village_ids"] == [7]

    async def test_generate_report_subscription_keeps_request_params(self):
        """735->737 / 737->747：请求已带年份/村列表时不被订阅值覆盖，仅类型取订阅值。"""
        request = reports_mod.ReportGenerateRequest(
            subscription_id=3, report_type="summary", year=2025,
            village_ids=[1, 2], format="json",
        )
        sub = SimpleNamespace(report_type="funds", year=2024, village_ids="[1]")
        service = MagicMock()
        service.db = db_of(q(first=sub))
        resp = await reports_mod.generate_report(
            request, current_user=admin_user(), service=service
        )
        assert resp["code"] == 200
        # 订阅类型生效
        assert resp["data"]["report_type"] == "funds"
        # 请求自带年份/村列表优先于订阅配置
        assert resp["data"]["parameters"]["year"] == 2025
        assert resp["data"]["parameters"]["village_ids"] == [1, 2]

    async def test_generate_report_subscription_village_ids_not_list(self):
        """741->747：订阅 village_ids JSON 解析结果非列表（如字符串），忽略之。"""
        request = reports_mod.ReportGenerateRequest(
            subscription_id=3, report_type="summary", year=None,
            village_ids=None, format="json",
        )
        sub = SimpleNamespace(report_type="summary", year=2023, village_ids='"1998"')
        service = MagicMock()
        service.db = db_of(q(first=sub))
        resp = await reports_mod.generate_report(
            request, current_user=admin_user(), service=service
        )
        assert resp["code"] == 200
        # 年份从订阅补齐，village_ids 保持 None
        assert resp["data"]["parameters"]["year"] == 2023
        assert resp["data"]["parameters"]["village_ids"] is None

    async def test_download_generated_report_unsupported_format_falls_back(self):
        """818->823 / 845->858：管理员跳过属主过滤；订阅存在但格式非 json/excel 走兜底 JSON。"""
        sub = SimpleNamespace(id=3, name="季度报表", report_type="summary", year=2024)
        service = MagicMock()
        service.db = db_of(q(first=sub))
        resp = await reports_mod.download_generated_report(
            9, format="pdf", current_user=admin_user(), service=service
        )
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "application/json"


# ==================== data_reports.py ====================


class TestDataReportsBranchGaps:
    async def test_get_data_report_outsider_with_permission(self):
        """202->205：用户不属于源/目标组织但经权限服务授权可访问，正常返回详情。"""
        report = make_report()
        service = MagicMock()
        service.get_report.return_value = report
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        user = SimpleNamespace(id=9, organization_id=None, org_id=99)
        resp = await dr.get_data_report(
            1, current_user=user, service=service, permission_service=perm
        )
        assert isinstance(resp, dr.DataReportResponse)
        assert resp.id == 1
        perm.can_access_organization.assert_called_once_with(9, report.source_org_id)

    async def test_approve_report_without_package(self):
        """369->378：上报关联的数据包不存在，跳过导入直接批准。"""
        from app.models.data_report import ReportStatus

        report = make_report(status=ReportStatus.SUBMITTED.value)
        service = MagicMock()
        service.db = db_of(
            q(first=report),   # 上报查询
            q(first=None),     # 数据包查询 -> None
        )
        user = SimpleNamespace(id=9, organization_id=None, org_id=2)  # 目标组织
        resp = await dr.approve_data_report(
            1, comment="同意", current_user=user, service=service
        )
        assert resp.status == ReportStatus.APPROVED.value
        assert report.reviewed_by == 9
        assert report.comment == "同意"

    async def test_get_report_package_outsider_with_permission(self):
        """406->412：非源/目标组织用户经权限服务授权可查看数据包信息。"""
        report = make_report(package_id=5)
        service = MagicMock()
        service.get_report.return_value = report
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        user = SimpleNamespace(id=9, organization_id=None, org_id=99)
        resp = await dr.get_report_package(
            1, current_user=user, service=service, permission_service=perm
        )
        assert resp["code"] == 200
        assert resp["data"]["report_id"] == 1
        assert resp["data"]["package_id"] == 5

    async def test_preview_report_outsider_with_permission_no_package(self):
        """432->436：非源/目标组织用户经授权可预览；无数据包时出站不含 package 节。"""
        report = make_report()
        service = MagicMock()
        service.get_report.return_value = report
        service.db = db_of(q(first=None))  # 数据包查询 -> None
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        user = SimpleNamespace(id=9, organization_id=None, org_id=99)
        resp = await dr.preview_data_report(
            1, current_user=user, service=service, permission_service=perm
        )
        assert resp["code"] == 200
        assert resp["data"]["report_id"] == 1
        assert "package" not in resp["data"]

    async def test_download_report_missing_physical_file(self):
        """484->488 / 491->499：经授权访问；数据包 file_path 指向不存在文件时回退 JSON 摘要。"""
        report = make_report()
        missing_path = os.path.join(
            tempfile.gettempdir(), f"mrrs_missing_{uuid.uuid4().hex}.dat"
        )
        assert not os.path.exists(missing_path)
        package = SimpleNamespace(file_path=missing_path, file_name=None)
        service = MagicMock()
        service.get_report.return_value = report
        service.db = db_of(q(first=package))
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        user = SimpleNamespace(id=9, organization_id=None, org_id=99)
        resp = await dr.download_data_report(
            1, current_user=user, service=service, permission_service=perm
        )
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "application/json"
